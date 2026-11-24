"""Time series, load patterns and ground excitation live in ``PatternsController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox

from opensees_studio.core import LinearTimeSeries, Node, PlainLoadPattern, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.patterns import PatternsController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import LinearTimeSeriesDialog, PlainPatternDialog

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
ALWAYS = {
    "define.linear_ts": "_act_add_linear_ts",
    "define.path_ts": "_act_add_path_ts",
    "define.function_ts": "_act_add_function_ts",
    "define.constant_ts": "_act_constant_ts",
}
WITH_A_SERIES = {
    "define.plain_pattern": "_act_add_plain_pattern",
    "define.uniform_excitation": "_act_add_uniform_excitation",
}
ON_JOINTS = {"define.multi_support": "_act_add_multi_support"}
DECLARED = ALWAYS | WITH_A_SERIES | ON_JOINTS


def _controller(qtbot, project: Project | None, selected: list[int] | None = None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    if project is not None:
        vm.adopt(project)
    log: list[str] = []
    started: list[str] = []

    def new_project() -> None:
        started.append("new")
        vm.new_project(ndm=3, ndf=6)

    canvas = SimpleNamespace(selection=SimpleNamespace(nodes=selected or [], elements=[]))
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    return PatternsController(shell, new_project=new_project), vm, log, started


def _accept(monkeypatch, dialog: type, **answers) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dialog, "exec", lambda self: int(QDialog.DialogCode.Accepted))
    for name, value in answers.items():
        monkeypatch.setattr(dialog, name, lambda self, value=value: value)


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6)
    assert isinstance(mw.patterns, PatternsController)
    assert mw.patterns.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id

    def enabled() -> set[str]:
        mw._refresh_action_enablement()
        return {i for i in DECLARED if mw.action(i).isEnabled()}

    project = mw._vm.project
    project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    project.time_series.clear()
    mw._canvas.selection.clear()
    # A pattern refers to a series: it waits for one.
    assert enabled() == set(ALWAYS)
    project.time_series.append(LinearTimeSeries(id=1, name="Ramp"))
    assert enabled() == set(ALWAYS) | set(WITH_A_SERIES)
    mw._canvas.selection.set_selection({1}, set())
    assert enabled() == set(DECLARED)
    mw._help_controller.uninstall()


def test_a_series_with_no_project_starts_one(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, started = _controller(qtbot, None)
    ramp = LinearTimeSeries(id=7, name="Ramp", factor=2.0)
    _accept(monkeypatch, LinearTimeSeriesDialog, time_series=ramp)
    controller.add_linear_ts()
    assert started == ["new"]
    assert ramp in vm.project.time_series
    assert log == ["Added LinearTimeSeries #7 'Ramp' (factor=2)."]
    vm.undo_stack.undo()
    assert ramp not in vm.project.time_series


def test_a_pattern_without_a_series_says_what_to_define_first(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log, started = _controller(qtbot, Project(ndm=3, ndf=6))
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, title, _text, *a, **k: warned.append(title)
    )
    controller.add_plain_pattern()
    controller.add_uniform_excitation()
    assert warned == ["Add Plain Load Pattern", "Add Uniform Excitation"]
    assert started == []
    assert vm.undo_stack.count() == 0


def test_a_plain_pattern_is_one_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project = Project(ndm=3, ndf=6)
    project.time_series.append(LinearTimeSeries(id=1, name="Ramp"))
    controller, vm, log, _started = _controller(qtbot, project)
    pattern = PlainLoadPattern(id=3, name="Wind", time_series_id=1)
    _accept(monkeypatch, PlainPatternDialog, pattern=pattern)
    controller.add_plain_pattern()
    assert pattern in vm.project.load_patterns
    assert log == ["Added PlainLoadPattern #3 'Wind' (series #1)."]
    assert vm.undo_stack.count() == 1
    vm.undo_stack.undo()
    assert pattern not in vm.project.load_patterns


def test_a_multi_support_excitation_asks_for_the_supports_first(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project = Project(ndm=3, ndf=6)
    project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    controller, vm, _log, _started = _controller(qtbot, project)
    controller.add_multi_support()
    controller, vm, _log, _started = _controller(qtbot, project, selected=[1])
    controller.add_multi_support()
    assert told == [
        "Select the supports to drive first.",
        "Define a displacement time series first (Define → Add Path TimeSeries…).",
    ]
    assert vm.undo_stack.count() == 0
