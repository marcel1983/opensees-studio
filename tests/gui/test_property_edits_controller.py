"""What the Properties dock changes goes through ``PropertyEditsController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QMainWindow, QMessageBox

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    ElasticUniaxial,
    Node,
    Project,
)
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.property_edits import PropertyEditsController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.docks.property_editor import MultiElementEdit

pytestmark = pytest.mark.gui

#: Callback of the dock -> the method of the controller it is set to.
CALLBACKS = {
    "on_apply_mass": "apply_mass",
    "on_change_element_type": "change_element_type",
    "on_change_element_material": "change_element_material",
    "on_change_element_section": "change_element_section",
    "on_change_element_fields": "change_element_fields",
    "on_assign_node_restraints": "assign_node_restraints",
    "on_assign_node_masses": "assign_node_masses",
    "on_assign_elements": "assign_elements",
}


def _section(section_id: int) -> ElasticSection:
    return ElasticSection(id=section_id, name=f"S{section_id}", E=1, A=1, Iz=1, Iy=1, G=1, J=1)


def _controller(qtbot, *, material: bool = False):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no dock, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    project = Project(ndm=3, ndf=6)
    project.nodes.extend(Node(id=i, coords=(float(i), 0, 0)) for i in (1, 2, 3))
    project.sections.extend(_section(i) for i in (1, 2))
    if material:
        project.materials.append(ElasticUniaxial(id=5, name="steel", E=2e11))
    project.elements.extend(ElasticBeamColumn(id=i, nodes=(i, i + 1), section_id=1) for i in (1, 2))
    vm = ProjectViewModel()
    vm.adopt(project)
    log: list[str] = []
    canvas = SimpleNamespace(selection=SimpleNamespace(nodes=[], elements=[]))
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    return PropertyEditsController(shell), vm, log


def test_the_dock_of_the_window_calls_the_controller(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.property_edits, PropertyEditsController)
    assert mw.property_edits.parent() is mw
    for callback, method in CALLBACKS.items():
        assert getattr(mw._props, callback) == getattr(mw.property_edits, method), callback
    mw._help_controller.uninstall()


def test_a_mass_and_a_section_are_one_undo_step_each(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log = _controller(qtbot)
    mass = (3.0, 3.0, 3.0, 0.0, 0.0, 0.0)
    controller.apply_mass(2, mass)
    assert vm.project.node(2).mass == mass
    controller.change_element_section(1, 2)
    assert [e.section_id for e in vm.project.elements] == [2, 1]
    assert vm.undo_stack.count() == 2
    vm.undo_stack.undo()
    vm.undo_stack.undo()
    assert [e.section_id for e in vm.project.elements] == [1, 1]
    assert not any(vm.project.node(2).mass)


def test_the_restraints_of_several_joints_are_one_undo_step(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log = _controller(qtbot)
    fixed, pinned = (True,) * 6, (True, True, True, False, False, False)
    controller.assign_node_restraints({1: fixed, 2: pinned, 3: fixed})
    assert [vm.project.node(i).restraint for i in (1, 2, 3)] == [fixed, pinned, fixed]
    assert vm.undo_stack.count() == 1
    assert vm.undo_stack.undoText() == "Edit restraints of 3 joint(s)"
    vm.undo_stack.undo()
    assert not any(any(vm.project.node(i).restraint) for i in (1, 2, 3))


def test_a_truss_needs_a_material_to_convert_to(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, text, *a, **k: warned.append(text)
    )
    controller, vm, log = _controller(qtbot)
    controller.change_element_type(1, "Truss")
    assert warned == ["Define a material before converting to a truss type."]
    assert vm.undo_stack.count() == 0

    controller, vm, log = _controller(qtbot, material=True)
    controller.change_element_type(1, "Truss")
    truss = vm.project.element(1)
    assert (truss.type, truss.material_id, truss.area) == ("Truss", 5, 0.001)
    assert log == ["Element 1 → Truss."]
    vm.undo_stack.undo()
    assert vm.project.element(1).type == "ElasticBeamColumn"


def test_several_elements_take_type_and_section_in_one_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log = _controller(qtbot)
    edit = MultiElementEdit(element_ids={1, 2})
    edit.section_id = 2
    controller.assign_elements(edit)
    assert [e.section_id for e in vm.project.elements] == [2, 2]
    assert log == ["Edited 2 element(s) from the Properties panel."]
    assert vm.undo_stack.count() == 1
    vm.undo_stack.undo()
    assert [e.section_id for e in vm.project.elements] == [1, 1]

    # A type it cannot convert to changes nothing and is not an undo step.
    edit = MultiElementEdit(element_ids={1, 2})
    edit.new_type = "Truss"
    edit.section_id = 2
    refused: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: refused.append("warned"))
    controller.assign_elements(edit)
    assert refused == ["warned"]
    assert [e.section_id for e in vm.project.elements] == [1, 1]
