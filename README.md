# pipsi (RepoRescue edition)

> **pipsi** = **pip** **s**cript **i**nstaller — install a PyPI package into
> its own isolated virtualenv and expose its `console_scripts` on
> `~/.local/bin`. The pre-`pipx` way of keeping CLI tools out of your system
> Python.

This fork is a **RepoRescue rescue artifact**: the upstream pipsi (last commit
2018, archived) was patched just enough to run on **Python 3.13 + the current
PyPI dependency set** (Click 8.3.x, virtualenv 21.x). Source-level test PASS,
end-to-end install/uninstall round-trip PASS, real CLI binaries (`http`,
`cookiecutter`) actually launch from the spawned venvs.

---

## ⚠️ Read this before you install

**pipsi has been superseded by [pipx](https://github.com/pypa/pipx).**
For any new setup, **install pipx instead.** pipx has feature parity
with pipsi, an active maintainer, file locking, parallel-install safety,
shell completion, `pipx run`, ephemeral envs, and is on every major distro.

This rescue exists for two narrow reasons:

1. **Nostalgia / archaeology** — pipsi was the dominant 2017–2019 way to
   install command-line Python tools without `sudo pip`. If you're maintaining
   a tutorial, dotfiles, or a corporate provisioning script that still says
   `curl get-pipsi.py | python`, this fork keeps that script working on
   modern interpreters.
2. **Frozen-in-time setups** — bootstrap scripts inside an old VM image, an
   internal training course, or a docker base image that hard-codes
   `pipsi install …`. Migrating those to pipx is the right answer; this rescue
   is a stopgap so they don't break the moment the box upgrades to Python
   3.12+.

If neither of those describes you: **`pip install pipx` and stop reading.**

---

## Install

```bash
pip install git+https://github.com/<org>/pipsi.git
```

`setup.py` pins `Click>=8.3.1` and `virtualenv>=21.2.0` because earlier
releases of either dependency don't build / run on Python 3.13.

## Quick start

```bash
# install a CLI tool into its own venv
pipsi install httpie
http --version              # ← the binary appears on $PATH

# list everything pipsi manages
pipsi list

# remove cleanly (drops the venv + every symlink)
pipsi uninstall --yes httpie
```

By default the venv goes to `~/.local/venvs/<pkg>/` and the symlinks land in
`~/.local/bin/`. Override with `PIPSI_HOME` / `PIPSI_BIN_DIR` or
`pipsi --home … --bin-dir … <cmd>`.

---

## What was changed for Python 3.13

The original pipsi source pulls in three stdlib / setuptools APIs that no
longer exist on 3.13. This fork patches them at the source level — no
behavioural changes, just modern equivalents.

| # | Original (broken) | Replacement | Where |
|---|---|---|---|
| 1 | `from pkg_resources import Requirement` to parse package specs | regex-based `normalize_package()` | `pipsi/__init__.py:69-74` (used in `:289`) |
| 2 | `from distutils.spawn import find_executable` | `shutil.which(...)` | `pipsi/__init__.py:12, 327` |
| 3 | version lookup via `pkg_resources` | `from importlib.metadata import version as package_version` | `pipsi/__init__.py:13, 479` |
| 4 | unbounded `virtualenv` dep (older versions blow up on 3.13) | `virtualenv>=21.2.0` pin | `setup.py:23` |

These four are the only edits that mattered. Everything else in pipsi —
the `Repo` class, `find_scripts`, `publish_script`, the symlink dance — runs
unchanged.

## Validation evidence

This rescue ships with the validation harness that produced the **USABLE**
verdict (see `artifacts/pipsi/REPORT.md` in the RepoRescue tree):

- **`.reporescue/usability_validate.py`** — `pipsi install httpie` → real
  subprocess invocation of the spawned `http --help` → `pipsi list` →
  `pipsi uninstall` → re-install / uninstall round-trip. Also exercises
  three independent in-process call paths (`normalize_package`,
  `Repo.list_everything`, `get_real_python`) so all four 3.13 surfaces are
  hit.
- **`.reporescue/scenario_validate.py`** — Path B scenario: a "new joiner
  workstation bootstrap" that pipsi-installs a curated wishlist
  (`httpie` + `cookiecutter`), probes each binary actually runs (`--version`),
  emits a JSON manifest for downstream audit, then tears everything down and
  asserts `pipsi list` is empty. Result: **`SCENARIO_PASS`**.
- **`.reporescue/bug_hunt.py`** — adversarial probes (dashed names, mixed
  case, version specifiers, duplicate install, unicode + spaces in
  `PIPSI_HOME`, concurrent installs of the same package).

### Known issue (not introduced by the rescue)

The bug hunt found one **pre-existing race**: two concurrent
`pipsi install <pkg>` invocations against the same `PIPSI_HOME` both return
`rc=0`, and the second silently overwrites the first one's venv. pipsi has
**no file lock** around its venv directory. This race exists in upstream
pipsi 0.9 unchanged — the rescue did not introduce it and did not fix it.
**pipx, by contrast, locks correctly.** This is one more reason to use pipx.

---

## Disclaimer

This package is provided **as-is, unmaintained, and explicitly deprecated**.
It exists as a corpus artifact for the RepoRescue benchmark — proof that a
2018-era abandoned Python project can be brought back to life on Python 3.13
with surgical edits — and as a courtesy to anyone whose old setup script
still depends on the `pipsi` entry point. **Do not build new tooling on
top of it.** For active development, switch to
[pipx](https://github.com/pypa/pipx).

## License

Original pipsi: BSD-3-Clause, © 2014 Armin Ronacher and contributors.
Rescue patches inherit the same license. See `LICENSE`.
