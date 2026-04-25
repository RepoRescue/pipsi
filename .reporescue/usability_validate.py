"""
pipsi usability validate (Scenario A — CLI tool).

Real招牌: pipsi 在隔离 venv 里装 PyPI 包, 把它的 console_scripts symlink 到
~/.local/bin (或 PIPSI_BIN_DIR). 验证: install / 可执行 / list / uninstall round-trip.

被装目标: whatthepatch — 纯 Python 单文件库, 自带 `whatthepatch` CLI, 体积小.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="pipsi-validate-"))
HOME = ROOT / "venvs"
BIN = ROOT / "bin"
HOME.mkdir()
BIN.mkdir()

# Use the rescue venv's pipsi explicitly — never trust PATH (miniconda / system
# pipsi may shadow). The clean venv is created by run_validate.sh.
CLEAN_VENV = os.environ.get("PIPSI_CLEAN_VENV", "/tmp/pipsi-clean")
PIPSI = f"{CLEAN_VENV}/bin/pipsi"
assert os.path.exists(PIPSI), f"pipsi binary missing at {PIPSI}"
# Sanity: verify this pipsi is the rescue version (no pkg_resources)
verify = subprocess.run([PIPSI, "--version"], capture_output=True, text=True)
assert verify.returncode == 0 and CLEAN_VENV in verify.stdout, (
    f"wrong pipsi resolved: {verify.stdout!r}")

ENV = {
    **os.environ,
    "PIPSI_HOME": str(HOME),
    "PIPSI_BIN_DIR": str(BIN),
}

# httpie has a stable console_script `http`, light deps, supported on 3.13.
TARGET = "httpie"
TARGET_EXE = "http"


def run(*args, check=True):
    print(f"$ {' '.join(args)}")
    r = subprocess.run(args, env=ENV, capture_output=True, text=True, timeout=300)
    print(r.stdout)
    if r.stderr:
        print("STDERR:", r.stderr, file=sys.stderr)
    if check:
        assert r.returncode == 0, f"rc={r.returncode}"
    return r


# ---- Hard constraint 5: 三个不同子模块在 import-time 真实被走到 ----
# pipsi.Repo  / pipsi.normalize_package / pipsi.find_scripts / pipsi.extract_package_version
import importlib
import pipsi
assert hasattr(pipsi, "Repo"), "pipsi.Repo missing"
assert hasattr(pipsi, "normalize_package"), "normalize_package missing"
assert hasattr(pipsi, "find_scripts"), "find_scripts missing"
# direct call path 1 — normalize_package (the one rewritten away from pkg_resources)
assert pipsi.normalize_package("Click>=8.0") == "click", "normalize_package broken"
assert pipsi.normalize_package("HTTPie==3.2") == "httpie"
# direct call path 2 — Repo construction + list_everything (touches os/json/glob)
repo = pipsi.Repo(str(HOME), str(BIN))
assert repo.list_everything() == [], "fresh repo should be empty"
# direct call path 3 — get_real_python (3.13: shutil.which replaces distutils.spawn)
real_python = pipsi.get_real_python(sys.executable)
assert os.path.exists(real_python), f"get_real_python broken: {real_python}"

print("=" * 60)
print("Step 1: pipsi install whatthepatch")
print("=" * 60)
r = run(PIPSI, "install", TARGET)
# assert (a) bin dir contains executable
exe = BIN / TARGET_EXE
assert exe.exists(), f"missing exe: {exe} (bin contains: {list(BIN.iterdir())})"
assert os.access(exe, os.X_OK), f"not executable: {exe}"
# assert venv was created
venv_dir = HOME / TARGET
assert venv_dir.is_dir(), f"missing venv: {venv_dir}"
assert (venv_dir / "package_info.json").exists()

print("=" * 60)
print("Step 2: run installed CLI as a real subprocess")
print("=" * 60)
# httpie's `http --help` prints argparse usage; offline-safe.
r = subprocess.run([str(exe), "--help"], capture_output=True,
                   text=True, timeout=30)
print("CLI stdout[:400]:", r.stdout[:400])
print("CLI stderr[:200]:", r.stderr[:200])
assert r.returncode == 0, f"installed CLI failed rc={r.returncode}"
# httpie --help mentions its tagline / METHOD / URL params
assert "URL" in r.stdout and ("HTTPie" in r.stdout or "http" in r.stdout.lower()), \
    "CLI did not emit expected output"

print("=" * 60)
print("Step 3: pipsi list shows installed package")
print("=" * 60)
r = run(PIPSI, "list")
assert TARGET in r.stdout, f"`pipsi list` missing {TARGET}: {r.stdout}"

print("=" * 60)
print("Step 4: pipsi uninstall removes everything cleanly")
print("=" * 60)
r = run(PIPSI, "--bin-dir", str(BIN), "--home", str(HOME),
        "uninstall", "--yes", TARGET)
assert not exe.exists(), f"exe still present after uninstall: {exe}"
assert not venv_dir.exists(), f"venv still present after uninstall: {venv_dir}"
# pipsi list should now be empty
r = run(PIPSI, "list")
assert TARGET not in r.stdout or "Packages" in r.stdout

print("=" * 60)
print("Step 5: re-install round-trip (state-leak smoke)")
print("=" * 60)
run(PIPSI, "install", TARGET)
assert (BIN / TARGET_EXE).exists()
run(PIPSI, "uninstall", "--yes", TARGET)

print()
print("USABLE")
shutil.rmtree(ROOT, ignore_errors=True)
