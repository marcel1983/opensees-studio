"""What a member is made of and how it is modelled lives in ``MembersController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QInputDialog, QMainWindow, QMessageBox

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    FrameModifiers,
    Node,
    Project,
    TrussElement,
)
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.members import MembersController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    AssignSectionDialog,
    FrameEndOffsetsDialog,
    FrameModifiersDialog,
)

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "assign.section": "_act_assign_section",
    "assign.material": "_act_assign_material",
    "assign.geom_transf": "_act_assign_geom_transf",
    "assign.local_axes": "_act_assign_local_axes",
    "assign.integration": "_act_assign_integration",
    "assign.releases": "_act_assign_releases",
    "assign.end_offsets": "_act_assign_end_offsets",
    "assign.insertion": "_act_assign_insertion",
    "assign.modifiers": "_act_assign_modifiers",
    "assign.auto_mesh": "_act_assign_auto_mesh",
    "assign.hinge": "_act_assign_hinge",
    "assign.wall": "_act_assign_wall",
    "assign.pile": "_act_assign_pile",
}


def _project() -> Project:
    """A beam (1) and a truss (2) on three joints, with two sections to choose from."""
    project = Project(ndm=3, ndf=6)
    for i in (1, 2):
        project.sections.append(
            ElasticSection(
                id=i, name=f"S{i}", E=200e9, A=0.01 * i, Iz=1e-5, Iy=1e-5, G=80e9, J=1e-6
            )
        )
    project.nodes.extend(
        [Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0)), Node(id=3, coords=(4, 0, 3))]
    )
    project.elements.append(ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1))
    project.elements.append(TrussElement(id=2, nodes=(2, 3), area=0.001, material_id=1))
    return project


def _controller(qtbot, selected: set[int]):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    vm.adopt(_project())
    log: list[str] = []
    canvas = SimpleNamespace(selection=SimpleNamespace(elements=selected))
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    return MembersController(shell), vm, log


def _accept(monkeypatch, dialog: type, **answers) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dialog, "exec", lambda self: int(QDialog.DialogCode.Accepted))
    for name, value in answers.items():
        monkeypatch.setattr(dialog, name, lambda self, value=value: value)


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6)
    assert isinstance(mw.members, MembersController)
    assert mw.members.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    # Every one of them works on the selected elements.
    mw._canvas.selection.clear()
    mw._refresh_action_enablement()
    assert not any(mw.action(i).isEnabled() for i in DECLARED)
    mw._vm.project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    mw._canvas.selection.set_selection({1}, set())
    mw._refresh_action_enablement()
    assert not any(mw.action(i).isEnabled() for i in DECLARED)
    mw._canvas.selection.set_selection(set(), {7})
    mw._refresh_action_enablement()
    assert all(mw.action(i).isEnabled() for i in DECLARED)
    mw._help_controller.uninstall()


def test_a_section_goes_on_the_selection_in_one_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log = _controller(qtbot, {1})
    _accept(monkeypatch, AssignSectionDialog, section_id=2)
    controller.assign_section()
    assert vm.project.element(1).section_id == 2
    vm.undo_stack.undo()
    assert vm.project.element(1).section_id == 1


def test_a_frame_option_goes_on_the_frames_and_leaves_the_truss_alone(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log = _controller(qtbot, {1, 2})
    cracked = FrameModifiers(i33=0.35)
    seen: list[tuple[int, object]] = []
    real_init = FrameModifiersDialog.__init__

    def init(self, count, current, parent=None):  # type: ignore[no-untyped-def]
        seen.append((count, current))
        real_init(self, count, current, parent)

    monkeypatch.setattr(FrameModifiersDialog, "__init__", init)
    _accept(monkeypatch, FrameModifiersDialog, modifiers=cracked)
    before = vm.project.element(2)
    controller.assign_modifiers()
    # One frame of the two selected elements, and the value it has now.
    assert seen == [(1, FrameModifiers())]
    assert vm.project.element(1).modifiers == cracked
    assert vm.project.element(2) == before
    assert len(log) == 1 and log[0].startswith("Frame Property Modifiers:")
    assert log[0].endswith("on 1 element(s).")
    vm.undo_stack.undo()
    assert vm.project.element(1).modifiers == FrameModifiers()


def test_auto_mesh_takes_frames_and_trusses(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log = _controller(qtbot, {1, 2})
    asked: list[tuple[str, int]] = []

    def get_item(_parent, _title, label, items, current, _editable):  # type: ignore[no-untyped-def]
        asked.append((label, current))
        return items[1], True

    monkeypatch.setattr(QInputDialog, "getItem", get_item)
    controller.assign_auto_mesh()
    # Both divide today, so the first choice is the one shown.
    assert asked == [("2 member(s):", 0)]
    assert [vm.project.element(i).auto_mesh for i in (1, 2)] == [False, False]
    assert vm.undo_stack.count() == 1


def test_a_cancelled_dialog_is_not_an_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log = _controller(qtbot, {1})
    monkeypatch.setattr(
        FrameEndOffsetsDialog, "exec", lambda self: int(QDialog.DialogCode.Rejected)
    )
    controller.assign_end_offsets()
    assert vm.undo_stack.count() == 0
    assert log == []


def test_nothing_that_fits_says_so_and_is_not_an_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Only the truss is selected: it has no releases, no transformation, no integration.
    controller, vm, _log = _controller(qtbot, {2})
    told: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text, *a, **k: told.append((title, text)),
    )
    controller.assign_releases()
    controller.assign_geom_transf()
    controller.assign_integration()
    assert told == [
        ("Frame Releases", "Select one or more frame elements first."),
        ("Geometric Transformation", "Select one or more frame elements first."),
        (
            "Beam Integration",
            "Select one or more force or displacement beam-column elements first.",
        ),
    ]
    assert vm.undo_stack.count() == 0


def test_a_hinge_needs_a_selection_and_a_section(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log = _controller(qtbot, set())
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    controller.assign_hinge()
    controller.assign_wall()
    controller.assign_pile()
    assert told == [
        "Select one or more elements first.",
        "Select the vertical members of the wall first.",
        "Select the pile's members first.",
    ]
    controller, vm, _log = _controller(qtbot, {1})
    vm.project.sections.clear()
    controller.assign_hinge()
    assert told[-1] == "No sections defined. Add a section before assigning hinges."
    assert vm.undo_stack.count() == 0


def test_a_hinge_turns_the_member_into_a_beam_with_hinges(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.dialogs import AssignHingeDialog

    controller, vm, log = _controller(qtbot, {1})
    values = {
        "section_i_id": 1,
        "section_j_id": 2,
        "lp_i": 0.3,
        "lp_j": 0.4,
        "E": 200e9,
        "A": 0.01,
        "Iz": 1e-5,
        "Iy": 1e-5,
        "G": 80e9,
        "J": 1e-6,
    }
    _accept(monkeypatch, AssignHingeDialog, values=values)
    controller.assign_hinge()
    hinged = vm.project.element(1)
    assert hinged.type == "BeamWithHinges"
    assert (hinged.nodes, hinged.section_i_id, hinged.section_j_id) == ((1, 2), 1, 2)
    assert (hinged.lp_i, hinged.lp_j) == (0.3, 0.4)
    assert log == ["Converted 1 element(s) to BeamWithHinges."]
    vm.undo_stack.undo()
    assert vm.project.element(1).type == "ElasticBeamColumn"
