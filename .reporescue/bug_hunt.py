"""
Step 7 — bug-hunt against the rescue (sonnet) version of pipsi.

Probes:
  H1. Package name with a dash: PyPI normalizes "python-dateutil" / "Click-8.0".
      Does pipsi.normalize_package preserve the dash *exactly* (so 'pipsi
      uninstall' matches the venv dir)?
  H2. Reinstall over an existing install — does it cleanly reject?
  H3. Unicode / spaces in PIPSI_HOME path — POSIX symlink behaviour.
  H4. Concurrent installs of the *same* package — race on the same venv dir.

These do NOT block USABLE; they're documented in REPORT.md per skill SKILL.md
Step 7.
"""
import os, shutil, subprocess, sys, tempfile, threading
from pathlib import Path

CLEAN_VENV = os.environ.get("PIPSI_CLEAN_VENV", "/tmp/pipsi-clean")
PIPSI = f"{CLEAN_VENV}/bin/pipsi"

import pipsi  # the rescued source
findings: list[str] = []


# H1 -- dash + mixed case + version specifier ---------------------------------
cases = {
    "python-dateutil":     "python-dateutil",
    "Click>=8.0":          "click",
    "HTTPie==3.2":         "httpie",
    "  Whitespace_Pkg  ":  "whitespace_pkg",
    "weird.dot.name":      "weird.dot.name",
    "":                    None,        # should raise
    "###bad":              None,
}
for inp, expected in cases.items():
    try:
        got = pipsi.normalize_package(inp)
    except Exception as e:
        got = f"<raised {type(e).__name__}>"
    ok = (expected is None and "raised" in str(got)) or (got == expected)
    line = f"H1 normalize_package({inp!r}) -> {got!r} expected {expected!r} {'OK' if ok else 'BUG'}"
    print(line)
    if not ok:
        findings.append(line)


# H2 -- duplicate install (state leak) ----------------------------------------
ROOT = Path(tempfile.mkdtemp(prefix="pipsi-bughunt-"))
HOME, BIN = ROOT / "venvs", ROOT / "bin"
HOME.mkdir(); BIN.mkdir()
ENV = {**os.environ, "PIPSI_HOME": str(HOME), "PIPSI_BIN_DIR": str(BIN)}

def pipsi_run(args, env=ENV, timeout=300):
    return subprocess.run([PIPSI, *args], env=env, capture_output=True,
                          text=True, timeout=timeout)

r1 = pipsi_run(["install", "httpie"])
print(f"H2.first install: rc={r1.returncode}")
r2 = pipsi_run(["install", "httpie"])
print(f"H2.dup install:   rc={r2.returncode}, stdout[:80]={r2.stdout[:80]!r}")
# Acceptable: rc != 0 and complains about already installed.
if r2.returncode == 0:
    findings.append("H2 BUG: duplicate install silently re-succeeded")
elif "already installed" not in (r2.stdout + r2.stderr).lower():
    print("H2 note: rejected but message not 'already installed':", r2.stderr[:200])
pipsi_run(["uninstall", "--yes", "httpie"])


# H3 -- unicode / space path --------------------------------------------------
SPACED = Path(tempfile.mkdtemp(prefix="pipsi spaces 中"))
HOME3, BIN3 = SPACED / "venvs", SPACED / "bin"
HOME3.mkdir(); BIN3.mkdir()
ENV3 = {**os.environ, "PIPSI_HOME": str(HOME3), "PIPSI_BIN_DIR": str(BIN3)}
r = pipsi_run(["install", "httpie"], env=ENV3, timeout=300)
print(f"H3.unicode-path install: rc={r.returncode}")
if r.returncode != 0:
    findings.append(f"H3 BUG: install fails with unicode/space path: {r.stderr[:200]}")
else:
    exe = BIN3 / "http"
    if not exe.exists():
        findings.append(f"H3 BUG: exe not linked in {BIN3}")
    else:
        # actually run it
        rr = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=15)
        if rr.returncode != 0:
            findings.append(f"H3 BUG: exe under unicode path won't execute: {rr.stderr[:200]}")
    pipsi_run(["uninstall", "--yes", "httpie"], env=ENV3)
shutil.rmtree(SPACED, ignore_errors=True)


# H4 -- concurrent install of the same package -------------------------------
ROOT4 = Path(tempfile.mkdtemp(prefix="pipsi-conc-"))
HOME4, BIN4 = ROOT4 / "venvs", ROOT4 / "bin"
HOME4.mkdir(); BIN4.mkdir()
ENV4 = {**os.environ, "PIPSI_HOME": str(HOME4), "PIPSI_BIN_DIR": str(BIN4)}

results = {}
def worker(tag):
    results[tag] = pipsi_run(["install", "httpie"], env=ENV4, timeout=300)
threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
for t in threads: t.start()
for t in threads: t.join()
rcs = [results[i].returncode for i in (0, 1)]
print(f"H4.concurrent rcs={rcs}")
# Healthy outcome: exactly one succeeds, the other rejects with non-zero.
# Pathological: both rc=0 (race overwrote venv) or both rc!=0.
if rcs == [0, 0]:
    findings.append("H4 BUG: concurrent install both rc=0 — likely race/overwrite")
elif rcs.count(0) == 0:
    findings.append(f"H4 BUG: concurrent install both failed: rcs={rcs}")
# verify resulting state is at least consistent
exe = BIN4 / "http"
if not exe.exists():
    findings.append("H4 BUG: post-race exe missing")
shutil.rmtree(ROOT4, ignore_errors=True)


# ---- summary ---------------------------------------------------------------
print()
print("=" * 60)
print("BUG HUNT SUMMARY")
print("=" * 60)
if findings:
    print(f"{len(findings)} findings:")
    for f in findings:
        print(" -", f)
else:
    print("No bugs found across H1-H4 probes.")
shutil.rmtree(ROOT, ignore_errors=True)
