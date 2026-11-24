"""Storeys, mass source, seismic loads, diaphragms and rigid links live in ``BuildingController``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QMessageBox

from opensees_studio.commands import AddNodesCommand
from opensees_studio.core import Node
from opensees_studio.views.controllers.building import BuildingController

pytestmark = pytest.mark.gui

DECLARED = {
    "define.storeys": "_act_storeys",
    "define.mass_source": "_act_mass_source",
    "define.seismic_loads": "_act_seismic_loads",
    "assign.diaphragm": "_act_assign_diaphragm",
    "assign.rigid_link": "_act_assign_rigid_link",
    "assign.remove_constraints": "_act_remove_constraints",
}


@pytest.fixture
def window(qtbot):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    vm = mw._vm
    vm.new_project(ndm=3, ndf=6)
    vm.apply_command(
        AddNodesCommand(
            vm,
            [
                Node(id=1, coords=(0, 0, 3)),
                Node(id=2, coords=(4, 0, 3)),
                Node(id=3, coords=(4, 4, 3)),
            ],
        )
    )
    yield mw
    mw._help_controller.uninstall()


def test_the_window_owns_one_controller_and_the_commands_point_at_it(window) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(window.building, BuildingController)
    assert window.building.parent() is window
    # The names the ribbon, the icons and the help table use still find them.
    for action_id, attribute in DECLARED.items():
        assert getattr(window, attribute) is window.action(action_id), action_id


def test_the_commands_follow_the_project_and_the_selected_joints(window) -> None:  # type: ignore[no-untyped-def]
    def enabled() -> set[str]:
        window._refresh_action_enablement()
        return {i for i in DECLARED if window.action(i).isEnabled()}

    always = {"define.storeys", "define.mass_source", "define.seismic_loads", "assign.diaphragm"}
    window._canvas.selection.clear()
    assert enabled() == always
    window._canvas.selection.set_selection({1}, set())
    assert enabled() == always | {"assign.remove_constraints"}
    window._canvas.selection.set_selection({1, 2}, set())
    assert enabled() == always | {"assign.remove_constraints", "assign.rigid_link"}
    window._canvas.selection.set_selection({1, 2, 3}, set())
    assert enabled() == always | {"assign.remove_constraints"}


def test_a_rigid_link_asks_for_two_joints_and_adds_nothing_otherwise(window, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    steps = window._vm.undo_stack.count()
    window._canvas.selection.set_selection({1}, set())
    window.building.assign_rigid_link()
    assert told == ["Select exactly two nodes first."]
    assert window._vm.project.rigid_links == []
    assert window._vm.undo_stack.count() == steps


def test_remove_constraints_without_joints_is_not_an_undo_step(window) -> None:  # type: ignore[no-untyped-def]
    steps = window._vm.undo_stack.count()
    window._canvas.selection.clear()
    window.building.remove_constraints()
    assert window._vm.undo_stack.count() == steps
