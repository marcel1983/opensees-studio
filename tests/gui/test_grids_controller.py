"""Coordinate systems and their grid lines live in ``GridsController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMainWindow

from opensees_studio.core import CoordinateGridSystem, GridSystem, Project, make_grid_lines
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.grids import GridsController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import CoordinateGridSystemsDialog

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {"define.grid": "_act_grid", "define.grid_wizard": "_act_grid_wizard"}


def _system(name: str) -> CoordinateGridSystem:
    return CoordinateGridSystem(
        name=name,
        grid=GridSystem(
            x_grid_lines=make_grid_lines("X", [0.0, 4.0]),
            y_grid_lines=make_grid_lines("Y", [0.0]),
            z_grid_lines=make_grid_lines("Z", [0.0, 3.0]),
        ),
    )


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    if project is not None:
        vm.adopt(project)
    log: list[str] = []
    calls: list[str] = []

    def new_project() -> None:
        calls.append("new")
        vm.new_project(ndm=3, ndf=6)

    canvas = SimpleNamespace(selection=SimpleNamespace(nodes=[], elements=[]))
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    controller = GridsController(
        shell, new_project=new_project, sync_actions=lambda: calls.append("sync")
    )
    return controller, vm, log, calls


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.grids, GridsController)
    assert mw.grids.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    assert mw.action("define.grid").shortcut().toString() == "Ctrl+G"
    # Both are offered with no project open: they start one.
    mw._refresh_action_enablement()
    assert all(mw.action(i).isEnabled() for i in DECLARED)

    # View → Show Grids goes through the controller and is ticked back by the window.
    mw._vm.new_project(ndm=3, ndf=6)
    mw._vm.project.coord_systems[:] = [_system("Global")]
    mw._sync_grid_actions()
    assert mw._act_show_grids.isChecked()
    mw._act_show_grids.trigger()
    assert all(cs.grid.hide_all for cs in mw._vm.project.coord_systems)
    assert not mw._act_show_grids.isChecked()
    mw._vm.undo_stack.undo()
    assert not any(cs.grid.hide_all for cs in mw._vm.project.coord_systems)
    mw._help_controller.uninstall()


def test_the_grid_dialog_with_no_project_starts_one(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, calls = _controller(qtbot, None)
    systems = [_system("Global"), _system("Annex")]
    monkeypatch.setattr(
        CoordinateGridSystemsDialog, "exec", lambda self: int(QDialog.DialogCode.Accepted)
    )
    monkeypatch.setattr(CoordinateGridSystemsDialog, "result_systems", lambda self: systems)
    controller.define()
    assert calls == ["new"]
    assert [cs.name for cs in vm.project.coord_systems] == ["Global", "Annex"]
    assert log == ["Coordinate/Grid Systems updated: Global, Annex."]
    vm.undo_stack.undo()
    assert [cs.name for cs in vm.project.coord_systems] != ["Global", "Annex"]


def test_hiding_one_grid_is_an_undo_step_and_ticks_the_command_again(qtbot) -> None:  # type: ignore[no-untyped-def]
    project = Project(ndm=3, ndf=6)
    project.coord_systems[:] = [_system("Global"), _system("B")]
    controller, vm, _log, calls = _controller(qtbot, project)

    controller.set_shown(False, "B")
    assert [cs.grid.hide_all for cs in vm.project.coord_systems] == [False, True]
    assert (vm.undo_stack.count(), calls) == (1, ["sync"])
    # Asking for what is already so is not an undo step.
    controller.set_shown(False, "B")
    assert vm.undo_stack.count() == 1

    controller.set_labels_shown(False)
    assert not any(cs.grid.show_labels for cs in vm.project.coord_systems)
    assert vm.undo_stack.count() == 2
    controller.set_shown(True)
    assert not any(cs.grid.hide_all for cs in vm.project.coord_systems)
