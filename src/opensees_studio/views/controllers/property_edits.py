"""What the Properties dock changes in the model when the user edits a value there."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from opensees_studio.commands import (
    AssignMaterialCommand,
    AssignSectionCommand,
    SetMassCommand,
    SetRestraintCommand,
)
from opensees_studio.views.controllers.shell import Shell


class PropertyEditsController(QObject):
    """The Properties dock's edits, each as one undo step.

    The dock shows the selected joint or element and calls back with what the
    user changed; this turns the change into commands: one joint's mass, an
    element's type, material, section or fields, and the edits of a selection
    of several joints or elements at once. It keeps no state.
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    def apply_mass(self, node_id: int, mass) -> None:  # type: ignore[no-untyped-def]
        """Callback from the property editor — dispatch as an undoable command."""
        try:
            self._vm.apply_command(SetMassCommand(self._vm, {node_id}, mass))
        except Exception as exc:
            QMessageBox.critical(self._window, "Apply mass failed", str(exc))

    def change_element_type(self, element_id: int, new_type: str) -> None:
        """User picked a different element type from the Properties dock."""
        command = self._convert_command({element_id}, new_type)
        if command is None:
            return
        try:
            self._vm.apply_command(command)
            self._shell.log(f"Element {element_id} → {new_type}.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Convert element failed", str(exc))

    def _convert_command(self, element_ids: set[int], new_type: str) -> Any:
        """The command converting ``element_ids`` to ``new_type``, None if it cannot."""
        from opensees_studio.commands import ConvertElementTypeCommand

        project = self._vm.project
        if project is None:
            return None
        # Supply sensible defaults for fields the target type requires.
        defaults: dict[str, object] = {}
        if new_type in ("Truss", "CorotTruss"):
            # Prefer an existing ElasticUniaxial + a nominal area.
            from opensees_studio.core import ElasticUniaxial

            mat = next((m for m in project.materials if isinstance(m, ElasticUniaxial)), None)
            if mat is None and project.materials:
                mat = project.materials[0]
            if mat is None:
                QMessageBox.warning(
                    self._window,
                    "Convert element",
                    "Define a material before converting to a truss type.",
                )
                return None
            defaults["material_id"] = mat.id
            defaults["area"] = 0.001
        elif new_type in ("ElasticBeamColumn", "ForceBeamColumn", "DispBeamColumn"):
            if not project.sections:
                QMessageBox.warning(
                    self._window,
                    "Convert element",
                    f"Define a section before converting to {new_type}.",
                )
                return None
            defaults["section_id"] = project.sections[0].id
        return ConvertElementTypeCommand(self._vm, element_ids, new_type, defaults=defaults)

    def assign_node_restraints(self, restraints: dict[int, tuple[bool, ...]]) -> None:
        self._apply_grouped(restraints, SetRestraintCommand, "Edit restraints")

    def assign_node_masses(self, masses: dict[int, tuple[float, ...]]) -> None:
        self._apply_grouped(masses, SetMassCommand, "Edit masses")

    def _apply_grouped(self, values: dict[int, Any], command: Any, text: str) -> None:
        """One command per distinct value, all in one undo step."""
        groups: dict[Any, set[int]] = {}
        for node_id, value in values.items():
            groups.setdefault(tuple(value), set()).add(node_id)
        stack = self._vm.undo_stack
        stack.beginMacro(f"{text} of {len(values)} joint(s)")
        try:
            for value, ids in groups.items():
                self._vm.apply_command(command(self._vm, ids, value))
        except Exception as exc:
            QMessageBox.critical(self._window, text, str(exc))
        finally:
            stack.endMacro()

    def assign_elements(self, edit: Any) -> None:
        """Properties dock, several elements: type, section, material and fields at once."""
        from opensees_studio.commands import AssignElementFieldsCommand

        ids = set(edit.element_ids)
        convert = None
        if edit.new_type is not None:
            convert = self._convert_command(ids, edit.new_type)
            if convert is None:
                return
        stack = self._vm.undo_stack
        stack.beginMacro(f"Edit {len(ids)} element(s)")
        try:
            # The type first: the other edits then apply to what the elements became.
            if convert is not None:
                self._vm.apply_command(convert)
            project = self._vm.project
            assert project is not None
            has = {
                key: {e.id for e in project.elements if e.id in ids and hasattr(e, key)}
                for key in ("section_id", "material_id")
            }
            if edit.material_id is not None and has["material_id"]:
                self._vm.apply_command(
                    AssignMaterialCommand(self._vm, has["material_id"], edit.material_id)
                )
            for key, value in edit.fields.items():
                # One field at a time: each lands on the elements that have it.
                self._vm.apply_command(AssignElementFieldsCommand(self._vm, ids, {key: value}))
            if edit.per_element:
                self._vm.apply_command(
                    AssignElementFieldsCommand(
                        self._vm, set(edit.per_element), {}, per_element=edit.per_element
                    )
                )
            # The section goes last: assigning a nonprismatic template splits the
            # member into pieces, and it must see the other edits on the frame.
            if edit.section_id is not None and has["section_id"]:
                self._vm.apply_command(
                    AssignSectionCommand(self._vm, has["section_id"], edit.section_id)
                )
            self._shell.log(f"Edited {len(ids)} element(s) from the Properties panel.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Edit elements failed", str(exc))
        finally:
            stack.endMacro()

    def change_element_material(self, element_id: int, material_id: int) -> None:
        try:
            self._vm.apply_command(AssignMaterialCommand(self._vm, {element_id}, material_id))
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign material failed", str(exc))

    def change_element_section(self, element_id: int, section_id: int) -> None:
        try:
            self._vm.apply_command(AssignSectionCommand(self._vm, {element_id}, section_id))
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign section failed", str(exc))

    def change_element_fields(self, element_id: int, fields: dict) -> None:  # type: ignore[type-arg]
        """Inline scalar edit dispatched from Properties dock (e.g. area)."""
        from opensees_studio.commands import UpdateElementFieldsCommand

        try:
            self._vm.apply_command(UpdateElementFieldsCommand(self._vm, element_id, fields))
        except Exception as exc:
            QMessageBox.critical(self._window, "Edit element failed", str(exc))
