"""The file-size budget: a long source file may only get shorter.

`views/main_window.py` reached 9,500 lines because nothing said "this file is
full". `tools/file-size-budget.txt` says it: every Python file of the package
has a ceiling (1,500 lines unless the file was already longer when the budget
was recorded), and this test fails when one goes over. It also fails when a
listed file has shrunk well under its ceiling, so the ceiling follows the file
down instead of leaving room to grow back.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "opensees_studio"
BUDGET_FILE = ROOT / "tools" / "file-size-budget.txt"

#: The ceiling of a file the budget does not list.
DEFAULT_CEILING = 1500
#: A listed file this far under its ceiling must have the ceiling lowered.
SLACK = 150


def _budget() -> tuple[dict[str, int], set[str]]:
    """Parse ``path ceiling`` and ``path exempt`` lines, ignoring comments and blanks."""
    ceilings: dict[str, int] = {}
    exempt: set[str] = set()
    for line in BUDGET_FILE.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if not entry:
            continue
        path, value = entry.split()
        if value == "exempt":
            exempt.add(path)
        else:
            ceilings[path] = int(value)
    return ceilings, exempt


def _lengths() -> dict[str, int]:
    """Lines of every Python file of the package, by path from the package root."""
    return {
        path.relative_to(PACKAGE).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for path in sorted(PACKAGE.rglob("*.py"))
    }


def test_no_file_is_longer_than_its_ceiling() -> None:
    ceilings, exempt = _budget()
    too_long = [
        f"{path}: {lines} lines > {ceilings.get(path, DEFAULT_CEILING)}"
        for path, lines in _lengths().items()
        if path not in exempt and lines > ceilings.get(path, DEFAULT_CEILING)
    ]
    assert not too_long, (
        "File-size budget exceeded (split the file; do not raise the ceiling):\n"
        + "\n".join(too_long)
    )


def test_every_ceiling_is_still_needed_and_follows_its_file_down() -> None:
    ceilings, exempt = _budget()
    lengths = _lengths()
    stale: list[str] = []
    for path in sorted(exempt | set(ceilings)):
        if path not in lengths:
            stale.append(f"{path}: no such file, delete its line")
    for path, ceiling in ceilings.items():
        lines = lengths.get(path)
        if lines is None:
            continue
        if lines <= DEFAULT_CEILING:
            stale.append(f"{path}: {lines} lines fit under {DEFAULT_CEILING}, delete its line")
        elif ceiling - lines >= SLACK:
            stale.append(f"{path}: {lines} lines, lower its ceiling of {ceiling}")
    assert not stale, "tools/file-size-budget.txt is out of date:\n" + "\n".join(stale)


def test_a_file_is_listed_once_and_no_ceiling_is_under_the_default() -> None:
    entries = [
        line.split("#", 1)[0].split()[0]
        for line in BUDGET_FILE.read_text(encoding="utf-8").splitlines()
        if line.split("#", 1)[0].strip()
    ]
    assert len(entries) == len(set(entries))
    ceilings, _exempt = _budget()
    assert [path for path, ceiling in ceilings.items() if ceiling <= DEFAULT_CEILING] == []
