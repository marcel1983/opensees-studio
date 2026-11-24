"""Assign → Frame: section, material, formulation and the frame member options."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from opensees_studio.commands import (
    AssignElementFieldsCommand,
    AssignMaterialCommand,
    AssignSectionCommand,
)
from opensees_studio.core import FrameMember
from opensees_studio.core.frame_members import connectivity_offsets
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    AssignBeamIntegrationDialog,
    AssignGeomTransfDialog,
    AssignLocalAxesDialog,
    AssignMaterialDialog,
    AssignSectionDialog,
    FrameEndOffsetsDialog,
    FrameInsertionDialog,
    FrameModifiersDialog,
    FrameReleasesDialog,
)


class MembersController(QObject):
    """What a selected member is made of and how it is modelled.

    Section and material; the geometric transformation, local axes and beam
    integration of a frame element; releases, end offsets, insertion point,
    property modifiers and auto mesh of a frame member. Each command takes the
    selected elements that have the field, shows the value they share and
    assigns the new one in one undo step (``AssignElementFieldsCommand``).
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    # ── section and material ──────────────────────────────────────────
    def assign_section(self) -> None:
        if self._vm.project is None:
            return
        sel_elements = set(self._shell.canvas().selection.elements)
        if not sel_elements:
            QMessageBox.information(
                self._window, "Assign Section", "Select one or more frame elements first."
            )
            return
        dlg = AssignSectionDialog(self._vm.project.sections, len(sel_elements), self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(AssignSectionCommand(self._vm, sel_elements, dlg.section_id()))
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Section failed", str(exc))

    def assign_material(self) -> None:
        if self._vm.project is None:
            return
        sel_elements = set(self._shell.canvas().selection.elements)
        if not sel_elements:
            QMessageBox.information(
                self._window,
                "Assign Material",
                "Select one or more truss/zero-length elements first.",
            )
            return
        dlg = AssignMaterialDialog(self._vm.project.materials, len(sel_elements), self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(AssignMaterialCommand(self._vm, sel_elements, dlg.material_id()))
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Material failed", str(exc))

    # ── how a frame element is formulated ─────────────────────────────
    def assign_geom_transf(self) -> None:
        """Assign > Frame > Geometric Transformation: Linear, PDelta or Corotational."""
        project = self._vm.project
        ids = self._selected_accepting({"geom_transf": "Linear"})
        if project is None or not ids:
            QMessageBox.information(
                self._window, "Geometric Transformation", "Select one or more frame elements first."
            )
            return
        current = {project.element(i).geom_transf for i in ids}  # type: ignore[union-attr]
        dlg = AssignGeomTransfDialog(
            len(ids), project.ndm, current.pop() if len(current) == 1 else None, self._window
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._assign_element_fields(
            "Geometric Transformation", ids, {"geom_transf": dlg.transf_type()}
        )

    def assign_local_axes(self) -> None:
        """Assign > Frame > Local Axes: rotate the member's section about its axis."""
        project = self._vm.project
        ids = self._selected_accepting({"local_axis_angle": 0.0})
        if project is None or not ids:
            QMessageBox.information(
                self._window, "Local Axes", "Select one or more frame elements first."
            )
            return
        current = {float(getattr(project.element(i), "local_axis_angle", 0.0) or 0.0) for i in ids}
        dlg = AssignLocalAxesDialog(
            len(ids),
            project.ndm,
            current.pop() if len(current) == 1 else None,
            self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._assign_element_fields("Local Axes", ids, {"local_axis_angle": dlg.angle()})

    def assign_integration(self) -> None:
        """Assign > Frame > Beam Integration: rule and points of force/disp beam-columns."""
        project = self._vm.project
        ids = self._selected_accepting({"integration": "Lobatto", "integration_points": 5})
        if project is None or not ids:
            QMessageBox.information(
                self._window,
                "Beam Integration",
                "Select one or more force or displacement beam-column elements first.",
            )
            return
        frames = [project.element(i) for i in ids]
        rules = {el.integration for el in frames}  # type: ignore[union-attr]
        points = {el.integration_points for el in frames}  # type: ignore[union-attr]
        dlg = AssignBeamIntegrationDialog(
            len(ids),
            rules.pop() if len(rules) == 1 else None,
            points.pop() if len(points) == 1 else None,
            self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._assign_element_fields(
            "Beam Integration",
            ids,
            {"integration": dlg.rule(), "integration_points": dlg.points()},
        )

    # ── frame member options ──────────────────────────────────────────
    def assign_releases(self) -> None:
        """Assign > Frame > Releases/Partial Fixity."""
        picked = self._frames_sharing("Frame Releases", "releases")
        if picked is None or self._vm.project is None:
            return
        ids, current = picked
        dlg = FrameReleasesDialog(len(ids), self._vm.project.ndm, current, self._window)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._assign_element_fields("Frame Releases", ids, {"releases": dlg.releases()})

    def assign_end_offsets(self) -> None:
        """Assign > Frame > End (Length) Offsets."""
        picked = self._frames_sharing("Frame End Offsets", "end_offsets")
        if picked is None:
            return
        ids, current = picked
        dlg = FrameEndOffsetsDialog(len(ids), current, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        offsets = dlg.offsets()
        if not dlg.automatic:
            self._assign_element_fields("Frame End Offsets", ids, {"end_offsets": offsets})
            return
        project = self._vm.project
        assert project is not None
        try:
            per_element = {}
            for i in ids:
                li, lj = connectivity_offsets(project, i)
                per_element[i] = {
                    "end_offsets": offsets.model_copy(update={"length_i": li, "length_j": lj})
                }
            self._vm.apply_command(
                AssignElementFieldsCommand(
                    self._vm,
                    ids,
                    {"end_offsets": offsets},
                    per_element=per_element,
                    text=f"Assign automatic end offsets to {len(ids)} element(s)",
                )
            )
            self._shell.log(f"Frame End Offsets (from connectivity) on {len(ids)} element(s).")
        except Exception as exc:
            QMessageBox.critical(self._window, "Frame End Offsets failed", str(exc))

    def assign_insertion(self) -> None:
        """Assign > Frame > Insertion Point."""
        picked = self._frames_sharing("Frame Insertion Point", "insertion")
        if picked is None or self._vm.project is None:
            return
        ids, current = picked
        dlg = FrameInsertionDialog(len(ids), self._vm.project.ndm, current, self._window)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._assign_element_fields(
                "Frame Insertion Point", ids, {"insertion": dlg.insertion()}
            )

    def assign_modifiers(self) -> None:
        """Assign > Frame > Property Modifiers."""
        picked = self._frames_sharing("Frame Property Modifiers", "modifiers")
        if picked is None:
            return
        ids, current = picked
        dlg = FrameModifiersDialog(len(ids), current, self._window)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._assign_element_fields(
                "Frame Property Modifiers", ids, {"modifiers": dlg.modifiers()}
            )

    def assign_auto_mesh(self) -> None:
        """Assign > Frame > Auto Mesh: whether Run may divide the selected members."""
        project = self._vm.project
        ids = self._selected_accepting({"auto_mesh": True})
        if project is None or not ids:
            QMessageBox.information(
                self._window, "Auto Mesh", "Select one or more frame or truss elements first."
            )
            return
        choices = [
            "Divide automatically where members end on it or cross it",
            "Never divide automatically",
        ]
        current = all(getattr(project.element(i), "auto_mesh", True) for i in ids)
        choice, ok = QInputDialog.getItem(
            self._window,
            "Auto Mesh",
            f"{len(ids)} member(s):",
            choices,
            0 if current else 1,
            False,
        )
        if not ok:
            return
        self._assign_element_fields("Auto Mesh", ids, {"auto_mesh": choice == choices[0]})

    # ── what is selected, and the one way a field is assigned ─────────
    def _selected_accepting(self, fields: dict[str, Any]) -> set[int]:
        """Selected elements that declare every one of ``fields`` (frames for a transformation)."""
        project = self._vm.project
        if project is None:
            return set()
        selected = set(self._shell.canvas().selection.elements)
        return {
            el.id
            for el in project.elements
            if el.id in selected and AssignElementFieldsCommand.accepts(el, fields)
        }

    def _frames_sharing(self, title: str, field: str) -> tuple[set[int], Any] | None:
        """Selected frame members and the value of ``field`` they share (None when they differ)."""
        project = self._vm.project
        selected = set(self._shell.canvas().selection.elements)
        frames = (
            []
            if project is None
            else [
                el for el in project.elements if el.id in selected and isinstance(el, FrameMember)
            ]
        )
        if not frames:
            QMessageBox.information(self._window, title, "Select one or more frame elements first.")
            return None
        values = [getattr(el, field) for el in frames]
        shared = values[0] if all(v == values[0] for v in values) else None
        return {el.id for el in frames}, shared

    def _assign_element_fields(self, title: str, ids: set[int], fields: dict[str, Any]) -> None:
        try:
            self._vm.apply_command(AssignElementFieldsCommand(self._vm, ids, fields))
            self._shell.log(f"{title}: {fields} on {len(ids)} element(s).")
        except Exception as exc:
            QMessageBox.critical(self._window, f"{title} failed", str(exc))
