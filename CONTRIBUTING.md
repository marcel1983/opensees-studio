# Contributing

Thanks for your interest. This project is in an early phase; the bar for
incoming changes is on architecture cleanliness rather than feature
breadth.

## Contributing without code

Most of what helps is not code. Open an issue from a
[template](https://github.com/marcel1983/opensees-studio/issues/new/choose):

| I want to… | Template |
|---|---|
| Contribute an example with a known answer (textbook, paper, hand calculation, an OpenSees script, another program) | **Validation case** |
| Report that a number or a design check is wrong | **Calculation error** |
| Report a crash or something that does not work | **Bug report** |
| Ask for a new feature | **Feature request** |

Questions go to
[Discussions](https://github.com/marcel1983/opensees-studio/discussions).
Translations (`data/i18n/`), help pages (`data/help/`), tutorials and testing
new releases on your system help too. The templates are in English and
Spanish; write in either.

## Where to contribute

This repository is the development lane of OpenSees Studio: new features land
here first and are released from here, then merged into the main repository,
[ogunc/opensees-studio](https://github.com/ogunc/opensees-studio), which is open
to everyone. Issues and pull requests are welcome in either; open them here when
they concern a release downloaded from this repository or a feature that is not
in the main repository yet.

## Branches and pull request target

- `main` is the integration branch. Ordinary feature and fix pull requests
  target `main`; start every change from an up-to-date `main`.
- `develop` is the maintainer's personal, experimental branch. It is not
  the general integration target: do not base work on it or open pull
  requests against it. Changes from it reach `main` through selected,
  reviewed pull requests.

In a fork, with this repository added as the `upstream` remote:

```bash
git fetch upstream
git switch -c fix/short-name upstream/main
```

Before you ask for review, bring in the latest `main` (merge it, or rebase
your own branch on it) so the pull request shows only your change. One pull
request does one thing; say in the description when one depends on another.

## Dev setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[gui,dev]"     # `[dev]` alone has no Qt: the app will not start
pre-commit install
```

Building the end-user bundle instead (or as well) needs the packaging extra:
`pip install -e ".[gui,dev,packaging]"`, then `python packaging/build.py`.
See [`packaging/README.md`](packaging/README.md).

## Before opening a PR

```bash
ruff check src tests
ruff format --check src tests
python tools/typecheck.py       # the same mypy ratchet CI enforces
lint-imports                    # the layering, also enforced in CI
pytest tests/unit tests/integration tests/tools
pytest tests/gui                # one process; check the exit code, not only the count
```

Fast loop while working on one area: `pytest -m "not slow"` skips the
tests that spawn extra interpreters (`tests/integration/test_cli_result_parity.py`).
CI does not skip them.

A pull request's CI runs only the required checks: `lint` and
`test (ubuntu-latest, 3.12)`. The GUI suite, the headless unit run, Windows,
macOS, Python 3.13/3.14 and CodeQL run after the merge on `main`, weekly and
on demand (Actions → CI → Run workflow), so run `pytest tests/gui` yourself
before opening a PR that touches the interface.

### The mypy ratchet

`[tool.mypy]` is strict, and the codebase has a backlog of errors, so the
check is a budget rather than a clean run: `tools/mypy-budget.txt` holds the
number of errors tolerated today and **may only go down**. Fixing errors and
lowering the number in the same commit is always welcome; raising it is not.

If a mypy or typeshed upgrade moves the count on its own, update the budget
in that commit and say so in the message. The budget is measured with the
mypy version pinned in `.github/workflows/ci.yml`.

## Architectural rules (enforced in review)

1. `core/` may not import Qt or `openseespy`. Period.
2. `services/` may not import Qt.
3. `views/` may not import `openseespy` directly — go through a service.
4. Public functions and methods need type hints and a docstring.
5. New domain entities go through Pydantic validation.
6. Long-running operations (>50 ms) run off the GUI thread.

`CLAUDE.md` collects the gotchas that are easy to break by accident (the
unsaved-changes prompt, the grid guard, how the analysis child is spawned,
the generated catalog, the eigen-determinism rule). Read it before touching
those areas.

## Commit style

Conventional Commits — `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
`chore:`, `ci:`.

## Releases

Tag `v*` on the branch that should ship. `.github/workflows/desktop.yml`
builds the Linux, Windows and macOS bundles, smoke-tests each one and
attaches the archives to the GitHub release.
