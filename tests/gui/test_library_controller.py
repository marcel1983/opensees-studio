"""Materials, friction models, records and sections live in ``LibraryController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMainWindow

from opensees_studio.core import ElasticSection, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.library import LibraryController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import MaterialLibraryDialog

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "define.material_library": "_act_material_library",
    "define.default_materials": "_act_default_materials",
    "define.mc2010": "_act_mc2010",
    "define.friction_library": "_act_friction_library",
    "define.material_tester": "_act_material_tester",
    "define.ground_motions": "_act_ground_motions",
    "define.section_library": "_act_section_library",
    "define.concrete_section": "_act_concrete_section",
    "define.steel_deck": "_act_steel_deck",
    "define.section_designer": "_act_section_designer",
}
SHORTCUTS = {
    "define.material_library": "Ctrl+Shift+M",
    "define.material_tester": "Ctrl+Shift+T",
    "define.ground_motions": "Ctrl+Shift+W",
    "define.section_library": "Ctrl+Shift+E",
}


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
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

    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: SimpleNamespace(),  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    return LibraryController(shell, new_project=new_project), vm, log, started, parent


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.library, LibraryController)
    assert mw.library.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
        assert mw.action(action_id).shortcut().toString() == SHORTCUTS.get(action_id, "")
    assert "A36" in mw.action("define.default_materials").toolTip()
    # A library opens with no project (it starts one); the default materials need one.
    mw._refresh_action_enablement()
    assert mw.action("define.material_library").isEnabled()
    assert mw.action("define.section_library").isEnabled()
    assert not mw.action("define.default_materials").isEnabled()
    mw._vm.new_project(ndm=3, ndf=6)
    mw._refresh_action_enablement()
    assert mw.action("define.default_materials").isEnabled()
    mw._help_controller.uninstall()


def test_a_library_with_no_project_starts_one(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log, started, _parent = _controller(qtbot, None)
    opened: list[object] = []
    monkeypatch.setattr(
        MaterialLibraryDialog, "exec", lambda self: opened.append(self) or int(QDialog.Rejected)
    )
    controller.material_library()
    assert started == ["new"]
    assert vm.project is not None
    assert len(opened) == 1


def test_default_materials_are_added_once(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, _started, parent = _controller(qtbot, Project(ndm=3, ndf=6))
    controller.add_default_materials()
    added = len(vm.project.materials)
    assert added > 0
    assert len(log) == 1 and log[0].startswith("Default materials added: ")
    assert vm.undo_stack.count() == 1
    # Nothing is missing now: it says so and pushes no undo step.
    controller.add_default_materials()
    assert len(vm.project.materials) == added
    assert vm.undo_stack.count() == 1
    assert "already has every default material" in parent.statusBar().currentMessage()
    vm.undo_stack.undo()
    assert vm.project.materials == []


def test_a_wizard_adds_materials_and_sections_in_one_undo_step(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, _started, _parent = _controller(qtbot, Project(ndm=3, ndf=6))
    section = ElasticSection(id=4, name="W", E=200e9, A=0.01, Iz=1e-5, Iy=1e-5, G=80e9, J=1e-6)
    controller._add_materials_and_sections("Designed section", [], [section])
    assert vm.project.sections == [section]
    assert log == ["Designed section: added 0 material(s) and section(s) #4 W."]
    vm.undo_stack.undo()
    assert vm.project.sections == []
