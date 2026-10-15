"""The mypy ratchet fails when mypy did not run, instead of counting zero errors.

``tools/typecheck.py`` counts ``: error:`` lines. Without a check on how mypy
exited, a missing mypy (``No module named mypy``, exit 1) or a crash (exit 2)
printed "0 error(s)" and passed.
"""

from __future__ import annotations

import subprocess

import pytest

from tools import typecheck

ERROR = "src/opensees_studio/core/x.py:1: error: Something  [misc]"


def _mypy(monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str, budget: int = 5) -> None:
    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(typecheck.subprocess, "run", fake_run)
    monkeypatch.setattr(typecheck, "budget", lambda: budget)


def test_mypy_not_installed_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mypy(monkeypatch, 1, "/usr/bin/python: No module named mypy\n")
    assert typecheck.main() == 2


def test_a_mypy_crash_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mypy(monkeypatch, 2, "error: Invalid config\n")
    assert typecheck.main() == 2


def test_errors_within_the_budget_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    _mypy(monkeypatch, 1, f"{ERROR}\n{ERROR}\nFound 2 errors in 1 file\n")
    assert typecheck.main() == 0


def test_errors_over_the_budget_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    _mypy(monkeypatch, 1, f"{ERROR}\n{ERROR}\nFound 2 errors in 1 file\n", budget=1)
    assert typecheck.main() == 1


def test_a_clean_run_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _mypy(monkeypatch, 0, "Success: no issues found in 3 source files\n")
    assert typecheck.main() == 0
