"""Define → materials, friction models, ground motions and sections."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog

from opensees_studio.commands import AddMaterialsCommand, AddSectionsCommand
from opensees_studio.core.default_materials import missing_default_materials
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    FrictionLibraryDialog,
    GroundMotionsDialog,
    MaterialLibraryDialog,
    MaterialTesterDialog,
    SectionLibraryDialog,
)
from opensees_studio.views.i18n import tr


class LibraryController(QObject):
    """What a model is made of: its materials, friction models, records and sections.

    A library can be opened with no project, so the window hands over
    new_project (File → New) and the command starts one. The Material
    Tester and Ground Motions are windows of their own, kept and raised again
    on a second call (material_tester_dialog, ground_motions_dialog);
    the section wizards add their materials and sections in one undo step.
    """

    def __init__(self, shell: Shell, *, new_project: Callable[[], None]) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._new_project = new_project
        self.material_tester_dialog: MaterialTesterDialog | None = None
        self.ground_motions_dialog: GroundMotionsDialog | None = None

    def material_library(self) -> None:
        if self._vm.project is None:
            self._new_project()
        MaterialLibraryDialog(self._vm, self._window).exec()

    def add_default_materials(self) -> None:
        """Define → Add Default Materials: the default steels, concretes and masonry it lacks."""
        project = self._vm.project
        if project is None:
            return
        missing = missing_default_materials(project, project.meta.units)
        if not missing:
            self._window.statusBar().showMessage(
                tr("The project already has every default material."), 6000
            )
            return
        self._vm.apply_command(AddMaterialsCommand(self._vm, missing))
        self._shell.log(f"Default materials added: {', '.join(m.name for m in missing)}.")

    def mc2010_concrete(self) -> None:
        """Define → Concrete Creep & Shrinkage: a TDConcreteMC10 material from the mix."""
        from opensees_studio.views.dialogs.mc2010_concrete import Mc2010ConcreteDialog

        if self._vm.project is None:
            self._new_project()
        project = self._vm.project
        if project is None:
            return
        dialog = Mc2010ConcreteDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        material = dialog.material()
        self._vm.apply_command(AddMaterialsCommand(self._vm, [material]))
        self._shell.log(
            f"Material {material.id} ({material.name}): TDConcreteMC10 after fib MC2010."
        )

    def friction_library(self) -> None:
        """Define > Friction Models: friction models for the sliding bearings."""
        if self._vm.project is None:
            self._new_project()
        FrictionLibraryDialog(self._vm, self._window).exec()

    def material_tester(self) -> None:
        # Non-modal and reused: a second trigger raises the open dialog.
        if self._vm.project is None:
            self._new_project()
        if self.material_tester_dialog is None:
            self.material_tester_dialog = MaterialTesterDialog(self._vm, self._window)
        self.material_tester_dialog.show()
        self.material_tester_dialog.raise_()
        self.material_tester_dialog.activateWindow()

    def ground_motions(self) -> None:
        # Non-modal and reused: a second trigger raises the open dialog.
        if self._vm.project is None:
            self._new_project()
        if self.ground_motions_dialog is None:
            self.ground_motions_dialog = GroundMotionsDialog(self._vm, self._window)
        self.ground_motions_dialog.show()
        self.ground_motions_dialog.raise_()
        self.ground_motions_dialog.activateWindow()

    def section_library(self) -> None:
        if self._vm.project is None:
            self._new_project()
        SectionLibraryDialog(self._vm, self._window).exec()

    def concrete_section(self) -> None:
        """Define → Concrete Section Wizard: materials and sections in one undo step."""
        from opensees_studio.views.dialogs.concrete_section import ConcreteSectionDialog

        if self._vm.project is None:
            self._new_project()
        project = self._vm.project
        if project is None:
            return
        dialog = ConcreteSectionDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.built_section()
        if result is None:
            return
        sections = [s for s in (result.fiber, result.elastic) if s is not None]
        self._add_materials_and_sections("Concrete section", result.materials, sections)

    def steel_deck(self) -> None:
        """Define → Steel Deck Slab Wizard: orthotropic layered shell, one undo step."""
        from opensees_studio.views.dialogs.steel_deck import SteelDeckDialog

        if self._vm.project is None:
            self._new_project()
        project = self._vm.project
        if project is None:
            return
        dialog = SteelDeckDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.built_deck()
        if result is not None:
            self._add_materials_and_sections("Steel deck slab", result.materials, [result.section])

    def section_designer(self) -> None:
        """Define → Section Designer: a drawn or imported section, added in one undo step."""
        from opensees_studio.views.dialogs.section_designer import SectionDesignerDialog

        if self._vm.project is None:
            self._new_project()
        project = self._vm.project
        if project is None:
            return
        dialog = SectionDesignerDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        section = dialog.built_section()
        if section is not None:
            self._add_materials_and_sections("Designed section", [], [section])

    def _add_materials_and_sections(
        self, text: str, materials: list[Any], sections: list[Any]
    ) -> None:
        """Add ``materials`` then ``sections`` as one undo step, and say what was added."""
        stack = self._vm.undo_stack
        stack.beginMacro(text)
        try:
            if materials:
                self._vm.apply_command(AddMaterialsCommand(self._vm, materials))
            if sections:
                self._vm.apply_command(AddSectionsCommand(self._vm, sections))
        finally:
            stack.endMacro()
        names = ", ".join(f"#{s.id} {s.name}" for s in sections)
        self._shell.log(f"{text}: added {len(materials)} material(s) and section(s) {names}.")
