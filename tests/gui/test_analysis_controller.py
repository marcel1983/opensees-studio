"""The Analyze menu lives in ``AnalysisController`` and runs with no ``MainWindow``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QMainWindow, QMessageBox

from opensees_studio.core import (
    LinearTimeSeries,
    Node,
    PlainLoadPattern,
    Project,
    StaticCase,
)
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.viewmodels.results_session import ResultsSession
from opensees_studio.views.controllers.analysis import AnalysisController
from opensees_studio.views.controllers.shell import Shell

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "analyze.case_manager": "_act_case_manager",
    "analyze.check_model": "_act_check_model",
    "analyze.check_stability": "_act_check_stability",
    "analyze.run": "_act_run",
    "analyze.run_all": "_act_run_all",
    "analyze.run_selected": "_act_run_selected",
}
SHORTCUTS = {
    "analyze.case_manager": "Ctrl+Shift+A",
    "analyze.check_model": "F6",
    "analyze.run": "F5",
    "analyze.run_all": "Shift+F5",
}


class _Runner:
    """The window's ``AnalysisRunner``, as far as the controller uses it."""

    def __init__(self) -> None:
        self.is_running = False
        self.last_exit_code: int | None = 3
        self.started: list[tuple[list[int], object]] = []

    def run_cases(self, _project, cases, *, project_path=None) -> None:  # type: ignore[no-untyped-def]
        self.started.append(([case.id for case in cases], project_path))


class _Stability:
    """The window's ``StabilityChecker``: what it was asked to check."""

    def __init__(self) -> None:
        self.checked: list[object] = []

    def check(self, project, _path) -> None:  # type: ignore[no-untyped-def]
        self.checked.append(project)


def _project(*, cases: bool = True) -> Project:
    project = Project(ndm=3, ndf=6)
    project.nodes.append(Node(id=1, coords=(0, 0, 0), restraint=(True,) * 6))
    if cases:
        project.time_series.append(LinearTimeSeries(id=1, name="Ramp"))
        project.load_patterns.append(PlainLoadPattern(id=1, name="DEAD", time_series_id=1))
        project.analyses.extend(
            [
                StaticCase(id=1, name="DEAD", pattern_ids=[1]),
                StaticCase(id=2, name="LIVE", pattern_ids=[1]),
            ]
        )
    return project


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: a recording runner and stability checker."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel(parent)
    if project is not None:
        vm.adopt(project)
    runner, stability = _Runner(), _Stability()
    log: list[str] = []
    console: list[str] = []
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: None,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    controller = AnalysisController(
        shell,
        runner=runner,  # type: ignore[arg-type]
        stability=stability,  # type: ignore[arg-type]
        results=ResultsSession(),
        finished=lambda _results: None,
        new_project=lambda: None,
        select_rows=lambda _nodes, _elements: None,
        show_mechanism=lambda _finding: None,
        console=console.append,
    )
    return controller, runner, stability, log, console, parent


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.analysis, AnalysisController)
    assert mw.analysis.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    shortcuts = {i: mw.action(i).shortcut().toString() for i in DECLARED}
    assert {i: keys for i, keys in shortcuts.items() if keys} == SHORTCUTS
    # Cases… starts a project when there is none; the checks need one.
    mw._refresh_action_enablement()
    assert mw.action("analyze.case_manager").isEnabled()
    assert not mw.action("analyze.check_model").isEnabled()
    assert not mw.action("analyze.check_stability").isEnabled()
    assert not mw.action("analyze.run_all").isEnabled()
    mw._vm.new_project(ndm=3, ndf=6)
    mw._refresh_action_enablement()
    assert mw.action("analyze.check_model").isEnabled()
    assert (mw.analysis.run_dialog, mw.analysis.error_box, mw.analysis.stability_box) == (
        None,
        None,
        None,
    )
    mw._help_controller.uninstall()


def test_run_says_what_is_missing(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    controller, _runner, stability, _log, _console, _parent = _controller(qtbot, None)
    controller.run()
    controller.check_model()
    controller.check_stability()  # no project: nothing to say
    assert told == ["Open or create a project first."] * 2

    controller, _runner, stability, _log, _console, _parent = _controller(
        qtbot, Project(ndm=3, ndf=6)
    )
    controller.run()
    controller.check_stability()
    assert told[2:] == [
        "No analysis cases defined. Open Analyze → Cases…",
        "The model has no joints yet.",
    ]
    assert controller.run_dialog is None and stability.checked == []


def test_the_stability_check_gets_the_project(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, _runner, stability, log, _console, _parent = _controller(qtbot, _project())
    controller.check_stability()
    assert len(stability.checked) == 1
    controller.on_stability_progress("build", "assembling")
    assert log[-1] == "Stability [build]: assembling"


def test_run_all_cases_hands_every_case_to_the_runner_once(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, runner, _stability, log, _console, _parent = _controller(
        qtbot, _project(cases=False)
    )
    controller.run_all()
    controller.run_selected()
    assert runner.started == []
    assert log == ["No analysis cases. Define one in Analyze → Cases…"] * 2

    controller, runner, _stability, log, _console, _parent = _controller(qtbot, _project())
    controller.run_all()
    assert runner.started == [([1, 2], None)]
    assert log == ["Running all 2 case(s)."]
    # A run under way is not started again.
    runner.is_running = True
    controller.run_all()
    controller.run_selected()
    assert len(runner.started) == 1


def test_a_failed_run_is_reported_without_blocking(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, runner, _stability, log, console, parent = _controller(qtbot, _project())
    controller.on_failed("exit code 3\nlast error: singular matrix")
    box = controller.error_box
    assert box is not None and not box.isModal()
    # With no Run dialog open the report belongs to the window.
    assert box.parent() is parent
    assert box.text() == "Analysis process exited with code 3."
    assert box.detailedText().endswith("singular matrix")
    assert console == ["exit code 3\nlast error: singular matrix"]
    assert log[-1] == "Analysis process exited with code 3."

    # Closed, the report is forgotten (Qt deletes it).
    box.done(0)
    assert controller.error_box is None
    controller.keep_failure_report_alive(parent)  # nothing to keep: must not raise

    runner.last_exit_code = None
    controller.on_failed("no exit code")
    assert controller.error_box is not None
    assert controller.error_box.text() == "Analysis failed."
    controller.error_box.done(0)
