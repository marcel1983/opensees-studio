"""Assigning and deleting loads lives in ``LoadsController``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QMessageBox

from opensees_studio.commands import AddElementsCommand, AddNodesCommand, AddSectionsCommand
from opensees_studio.core import ElasticBeamColumn, ElasticSection, Node
from opensees_studio.views.controllers.loads import LoadsController

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "edit.delete_loads": "_act_delete_loads",
    "define.joint_patterns": "_act_joint_patterns",
    "assign.load": "_act_assign_load",
    "assign.imposed_displacement": "_act_assign_imposed_displacement",
    "assign.joint_pattern": "_act_assign_joint_pattern",
    "assign.distributed_load": "_act_assign_distributed_load",
    "assign.trapezoidal_load": "_act_assign_trapezoidal_load",
    "assign.frame_point_load": "_act_assign_frame_point_load",
    "assign.temperature_load": "_act_assign_temperature_load",
    "assign.tendon": "_act_assign_tendon",
    "assign.surface_load": "_act_assign_surface_load",
    "assign.floor_load": "_act_assign_floor_load",
}
ALWAYS = {"edit.delete_loads", "define.joint_patterns"}
ON_JOINTS = {"assign.load", "assign.imposed_displacement", "assign.joint_pattern"}
ON_ELEMENTS = {
    "assign.distributed_load",
    "assign.trapezoidal_load",
    "assign.frame_point_load",
    "assign.temperature_load",
    "assign.tendon",
    "assign.surface_load",
}


def _window(qtbot, ndm: int = 3):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    vm = mw._vm
    vm.new_project(ndm=ndm, ndf=6 if ndm == 3 else 3)
    section = ElasticSection(id=1, name="S", E=200e9, A=0.01, Iz=1e-5, Iy=1e-5, G=80e9, J=1e-6)
    vm.apply_command(AddSectionsCommand(vm, [section]))
    vm.apply_command(
        AddNodesCommand(vm, [Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0))])
    )
    vm.apply_command(AddElementsCommand(vm, [ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1)]))
    return mw


def _enabled(mw) -> set[str]:  # type: ignore[no-untyped-def]
    mw._refresh_action_enablement()
    return {i for i in DECLARED if mw.action(i).isEnabled()}


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    assert isinstance(mw.loads, LoadsController)
    assert mw.loads.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    assert mw.action("assign.load").shortcut().toString() == "Ctrl+L"
    mw._help_controller.uninstall()


def test_each_command_follows_what_it_loads(qtbot) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    mw._canvas.selection.clear()
    assert _enabled(mw) == ALWAYS
    mw._canvas.selection.set_selection({1}, set())
    # A floor load goes on the joints of a floor, in a 3D model only.
    assert _enabled(mw) == ALWAYS | ON_JOINTS | {"assign.floor_load"}
    mw._canvas.selection.set_selection(set(), {1})
    assert _enabled(mw) == ALWAYS | ON_ELEMENTS
    mw._help_controller.uninstall()


def test_a_floor_load_is_not_offered_in_a_plane_model(qtbot) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot, ndm=2)
    mw._canvas.selection.set_selection({1}, set())
    assert _enabled(mw) == ALWAYS | ON_JOINTS
    mw._help_controller.uninstall()


def test_a_frame_load_on_nothing_says_so_and_is_not_an_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    told: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text, *a, **k: told.append((title, text)),
    )
    steps = mw._vm.undo_stack.count()
    mw._canvas.selection.clear()
    mw.loads.assign_trapezoidal_load()
    mw.loads.assign_distributed_load()
    mw.loads.assign_nodal_load()
    assert told == [
        ("Frame Trapezoidal Load", "Select one or more frame elements first."),
        ("Assign Distributed Load", "Select one or more elements first."),
        ("Assign Load", "Select one or more nodes first."),
    ]
    assert mw._vm.undo_stack.count() == steps
    mw._help_controller.uninstall()
