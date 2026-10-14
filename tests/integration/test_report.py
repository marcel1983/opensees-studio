"""The report page built from a solved model."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

pytest.importorskip("openseespy.opensees")

from opensees_studio.services.opensees_runner import OpenSeesRunner
from opensees_studio.services.persistence import load_project
from opensees_studio.services.report import MAX_ROWS, build_report

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_report_of_a_solved_frame(tmp_path: Path) -> None:
    project = load_project(EXAMPLES / "building_3storey_diaphragm.osmodel")
    runner = OpenSeesRunner(project)
    results = [runner.run(case, results_dir=tmp_path / str(case.id)) for case in project.analyses]
    page = build_report(project, results, now=dt.datetime(2026, 1, 2, 3, 4))
    assert page.startswith("<!doctype html>") and page.endswith("</body></html>")
    assert "2026-01-02 03:04" in page
    assert project.meta.name in page
    assert "Results — " in page and "Peak displacements" in page
    assert "(supports)" in page and ">Sum<" in page


def test_report_without_results_says_so() -> None:
    project = load_project(EXAMPLES / "building_3storey_diaphragm.osmodel")
    assert "No results for the model as it is now" in build_report(project)
    assert MAX_ROWS > 0
