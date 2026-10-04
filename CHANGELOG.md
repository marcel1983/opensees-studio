# Changelog

Notable changes per release. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html), with the caveat
that this is pre-alpha: minor and patch releases may change the `.osmodel`
schema (it carries a `schema_version`, and a file from a newer build is now
refused instead of silently downgraded).

## [0.0.2] — 2026-10-04

The first release with a desktop bundle: download, unpack, run — no Python,
Qt, VTK or OpenSees to install. Built by
`.github/workflows/desktop.yml` for Linux, Windows and macOS.

### Added

- **Packaging for end users** (`packaging/`): a PyInstaller spec and a build
  script that produces `dist/OpenSeesStudio`, plus a smoke test that solves a
  bundled example through the frozen executable and starts the GUI before an
  artifact is published.
- **Frozen-bundle analysis child** (`child_cli.py`): a bundle has no
  `python -m`, so the executable re-enters itself as the analysis CLI. Both
  spawn sites use it; on Windows the child is created without a console
  window.
- **mypy ratchet** (`tools/typecheck.py`, `tools/mypy-budget.txt`): CI now
  fails when the number of type errors grows above the recorded budget.
- **Codegen drift test**: the committed catalog is compared byte for byte
  against a fresh codegen run, so a hand edit or a stale regeneration fails
  CI.
- Coverage floor (75%) and a coverage artifact on the Ubuntu job; Python
  3.13 and 3.14 in the Linux test matrix.
- `CHANGELOG.md`, `.github/dependabot.yml` (pip and GitHub Actions).

### Fixed

- **Not losing unsaved work**: closing, `File → New` and `File → Open` now
  confirm before discarding a modified project. Only a user-initiated close
  asks; a programmatic close during shutdown does not.
- **Draw tools on an empty project**: arming Draw Node / Frame / Truss with
  no grid defined now offers to define one instead of doing nothing.
- **Material Library crash**: a material with no registered form
  (`Hysteretic`, `HystereticSM`) showed a `KeyError`; it now gets a read-only
  placeholder, as the section forms already did.
- **Atomic saves**: `.osmodel` is written through a temporary file and a
  rename, so a failure mid-write no longer truncates the previous file.
- **Future schema refused**: a project written by a newer build is rejected
  with a clear message instead of being loaded and rewritten one version
  down.
- The About box said MIT; the licence is AGPL-3.0.
- The Run dialog is destroyed when it closes, instead of staying alive and
  appended to on every later run.
- Throwaway results directories of finished analyses are removed; transient
  results keep theirs.

### Changed

- The version lives in one place (`src/opensees_studio/__init__.py`);
  `pyproject.toml` reads it with `[tool.hatch.version]`.
- `.github/workflows/ci.yml.disabled`, a stale duplicate of `ci.yml`, is gone.
- `CONTRIBUTING.md` installs `.[gui,dev]`; `[dev]` alone has no Qt.
