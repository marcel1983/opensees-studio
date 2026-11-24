"""Restraints, masses, springs and what joins two joints live in ``JointsController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox

from opensees_studio.core import Node, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.joints import JointsController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    AssignEqualDOFDialog,
    AssignMassesDialog,
    AssignSupportDialog,
)

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
ON_JOINTS = {
    "assign.support": "_act_assign_support",
    "assign.masses": "_act_assign_masses",
    "assign.springs": "_act_assign_springs",
}
ON_TWO_JOINTS = {
    "assign.equal_dof": "_act_assign_equal_dof",
    "assign.zero_length": "_act_assign_zero_length",
    "assign.zls": "_act_assign_zls",
    "assign.bearing": "_act_assign_bearing",
    "assign.link": "_act_assign_link",
}
DECLARED = ON_JOINTS | ON_TWO_JOINTS


def _controller(qtbot, selected: list[int]):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    project = Project(ndm=3, ndf=6)
    project.nodes.extend(Node(id=i, coords=(float(i), 0, 0)) for i in (1, 2, 3))
    vm = ProjectViewModel()
    vm.adopt(project)
    log: list[str] = []
    canvas = SimpleNamespace(selection=SimpleNamespace(nodes=selected, elements=[]))
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    return JointsController(shell), vm, log


def _accept(monkeypatch, dialog: type, **answers) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dialog, "exec", lambda self: int(QDialog.DialogCode.Accepted))
    for name, value in answers.items():
        monkeypatch.setattr(dialog, name, lambda self, value=value: value)


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6)
    assert isinstance(mw.joints, JointsController)
    assert mw.joints.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    assert mw.action("assign.support").shortcut().toString() == "Ctrl+R"

    def enabled() -> set[str]:
        mw._refresh_action_enablement()
        return {i for i in DECLARED if mw.action(i).isEnabled()}

    mw._canvas.selection.clear()
    assert enabled() == set()
    mw._canvas.selection.set_selection({1}, set())
    assert enabled() == set(ON_JOINTS)
    # What joins two joints is offered for exactly two.
    mw._canvas.selection.set_selection({1, 2}, set())
    assert enabled() == set(DECLARED)
    mw._canvas.selection.set_selection({1, 2, 3}, set())
    assert enabled() == set(ON_JOINTS)
    mw._canvas.selection.set_selection(set(), {1})
    assert enabled() == set()
    mw._help_controller.uninstall()


def test_a_restraint_and_a_mass_go_on_every_selected_joint(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log = _controller(qtbot, [1, 3])
    fixed = (True,) * 6
    _accept(monkeypatch, AssignSupportDialog, restraint=fixed)
    controller.assign_support()
    assert [vm.project.node(i).restraint for i in (1, 2, 3)] == [fixed, (False,) * 6, fixed]
    mass = (2.0, 2.0, 2.0, 0.0, 0.0, 0.0)
    _accept(monkeypatch, AssignMassesDialog, mass_vector=mass)
    controller.assign_masses()
    assert [vm.project.node(i).mass == mass for i in (1, 2, 3)] == [True, False, True]
    assert log == ["Assigned mass to 2 node(s)."]
    # One undo step each.
    assert vm.undo_stack.count() == 2
    vm.undo_stack.undo()
    vm.undo_stack.undo()
    assert not any(any(vm.project.node(i).restraint) for i in (1, 2, 3))


def test_an_equal_dof_joins_the_two_selected_joints(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log = _controller(qtbot, [2, 1])

    def tick_ux(dialog: AssignEqualDOFDialog) -> int:
        dialog._dof_boxes[0].setChecked(True)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(AssignEqualDOFDialog, "exec", tick_ux)
    controller.assign_equal_dof()
    (constraint,) = vm.project.mp_constraints
    assert (constraint.retained_node, constraint.constrained_node) == (1, 2)
    assert constraint.dofs == (1,)
    assert log == ["Added equalDOF constraint between nodes 1 and 2."]
    vm.undo_stack.undo()
    assert vm.project.mp_constraints == []


def test_the_wrong_number_of_joints_says_so_and_is_not_an_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log = _controller(qtbot, [1, 2, 3])
    told: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text, *a, **k: told.append((title, text)),
    )
    controller.assign_equal_dof()
    controller.assign_zero_length()
    controller.assign_zls()
    controller.assign_bearing()
    controller.assign_link()
    assert told == [
        ("Assign EqualDOF", "Select exactly two nodes first."),
        ("Assign Zero-Length Element", "Select exactly two coincident joints first."),
        ("Assign Zero-Length Section", "Select exactly two coincident nodes first."),
        ("Assign Bearing", "Select exactly two nodes first (bottom, then top)."),
        ("Assign Link", "Select exactly two joints first."),
    ]
    assert vm.undo_stack.count() == 0


def test_a_zero_length_element_refuses_joints_that_are_apart(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log = _controller(qtbot, [1, 2])
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, text, *a, **k: warned.append(text)
    )
    controller.assign_zero_length()
    assert warned == [
        "Joints 1 and 2 are not coincident. Move one onto the other before creating the element."
    ]
    assert vm.project.elements == []
