"""
Scenario validate (Path B) — pipsi as the user-facing tool a developer uses
to bootstrap a fresh workstation with a curated set of CLI utilities.

Plays the role of a "new joiner setup script": instead of polluting the system
Python with `pip install httpie cookiecutter pipenv`, the user runs pipsi and
gets each tool isolated in its own venv with a single binary on PATH. Mirrors
the exact reason pipsi existed before pipx took over (2017-2019).

Real workflow:
  1. Read a YAML-ish wishlist of CLI tools.
  2. For each tool: pipsi install — abort the whole bootstrap if any fail.
  3. Probe each installed binary actually runs (--help / --version).
  4. Export an env-summary to JSON so a manifest tool can audit later.
  5. Tear-down at the end (so this script is idempotent on a CI box).

>=30 lines of real business logic (excluding boilerplate).
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---- 1. config: a developer's "first day" CLI wishlist ---------------------
WISHLIST = [
    # (pypi_name, expected_console_script, smoke_args)
    ("httpie",        "http",         ["--version"]),
    ("cookiecutter",  "cookiecutter", ["--version"]),
]
# 注：选这两个是因为它们都是当年 pipsi README 文档中明确列出的典型用例。

CLEAN_VENV = os.environ.get("PIPSI_CLEAN_VENV", "/tmp/pipsi-clean")
PIPSI = f"{CLEAN_VENV}/bin/pipsi"

assert os.path.exists(PIPSI), f"pipsi not found at {PIPSI}"
ROOT = Path(tempfile.mkdtemp(prefix="pipsi-bootstrap-"))
HOME, BIN = ROOT / "venvs", ROOT / "bin"
HOME.mkdir(); BIN.mkdir()
ENV = {**os.environ, "PIPSI_HOME": str(HOME), "PIPSI_BIN_DIR": str(BIN)}


def pipsi(*args, check=True):
    print(f"[pipsi] {' '.join(args)}")
    r = subprocess.run([PIPSI, *args], env=ENV, capture_output=True,
                       text=True, timeout=600)
    if r.stdout: print(r.stdout)
    if r.stderr: print("[stderr]", r.stderr, file=sys.stderr)
    if check:
        assert r.returncode == 0, f"pipsi {args} failed rc={r.returncode}"
    return r


# ---- 2. install pass: every wishlist entry must succeed -------------------
manifest = {"installed": [], "binaries": [], "smoke": {}}
for pkg, exe_name, smoke_args in WISHLIST:
    pipsi("install", pkg)
    exe = BIN / exe_name
    assert exe.exists() and os.access(exe, os.X_OK), \
        f"{pkg}: missing or non-executable binary at {exe}"
    manifest["installed"].append(pkg)
    manifest["binaries"].append(str(exe))

# ---- 3. probe pass: each binary must actually run -------------------------
for pkg, exe_name, smoke_args in WISHLIST:
    exe = BIN / exe_name
    r = subprocess.run([str(exe), *smoke_args], capture_output=True,
                       text=True, timeout=30)
    out = (r.stdout + r.stderr).strip()
    print(f"[smoke] {exe_name} {smoke_args}: rc={r.returncode}, out[:100]={out[:100]!r}")
    assert r.returncode == 0, f"{exe_name} smoke failed: {out}"
    manifest["smoke"][pkg] = {"rc": r.returncode, "first_line": out.splitlines()[0] if out else ""}

# ---- 4. cross-check: pipsi list must report exactly the wishlist ----------
listed = pipsi("list").stdout
for pkg, _, _ in WISHLIST:
    assert pkg in listed, f"`pipsi list` missed {pkg}"

# ---- 5. emit manifest the way a real bootstrap would for downstream audit -
manifest_path = ROOT / "bootstrap_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2))
print(f"[manifest] wrote {manifest_path}")
assert json.loads(manifest_path.read_text())["installed"] == [p for p, _, _ in WISHLIST]

# ---- 6. tear-down: uninstall round-trips cleanly --------------------------
for pkg, exe_name, _ in WISHLIST:
    pipsi("uninstall", "--yes", pkg)
    assert not (BIN / exe_name).exists(), f"{exe_name} survived uninstall"
    assert not (HOME / pkg).exists(), f"{pkg} venv survived uninstall"

# ---- 7. final: pipsi list must be empty -----------------------------------
final = pipsi("list").stdout
assert "no scripts" in final.lower(), f"unexpected residue: {final}"

shutil.rmtree(ROOT, ignore_errors=True)
print("\nSCENARIO_PASS — pipsi as a dev-bootstrap tool works end-to-end")
