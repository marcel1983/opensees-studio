"""Assign → Frame: section, material, formulation and the frame member options."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from opensees_studio.commands import (
    AddElementsCommand,
    AddMaterialsCommand,
    AddNodesCommand,
    AssignElementFieldsCommand,
    AssignMaterialCommand,
    AssignSectionCommand,
    ReplaceElementsCommand,
)
from opensees_studio.core import BeamWithHingesElement, ElasticBeamColumn, FrameMember
from opensees_studio.core.frame_members import connectivity_offsets
from opensees_studio.core.self_weight import section_weight_per_length
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    AssignBeamIntegrationDialog,
    AssignGeomTransfDialog,
    AssignHingeDialog,
    AssignLocalAxesDialog,
    AssignMaterialDialog,
    AssignSectionDialog,
    FrameEndOffsetsDialog,
    FrameInsertionDialog,
    FrameModifiersDialog,
    FrameReleasesDialog,
)
from opensees_studio.views.i18n import tr


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

    def assign_tension_only(self) -> None:
        """Assign > Frame > Tension Only: rods and slender braces that buckle in compression."""
        project = self._vm.project
        ids = {
            i
            for i in self._selected_accepting({"tension_only": True})
            if project is not None and isinstance(project.element(i), ElasticBeamColumn)
        }
        if project is None or not ids:
            QMessageBox.information(
                self._window,
                tr("Tension Only"),
                tr("Select one or more elastic frame elements first."),
            )
            return
        choices = [
            tr("Frame member (tension and compression)"),
            tr("Tension only (a truss that goes slack in compression)"),
        ]
        current = all(getattr(project.element(i), "tension_only", False) for i in ids)
        choice, ok = QInputDialog.getItem(
            self._window,
            tr("Tension Only"),
            tr("{n} member(s):").format(n=len(ids)),
            choices,
            1 if current else 0,
            False,
        )
        if not ok:
            return
        self._assign_element_fields("Tension Only", ids, {"tension_only": choice == choices[1]})

    # ── what turns a member into something else ───────────────────────
    def assign_hinge(self) -> None:

        sel_elements = set(self._shell.canvas().selection.elements)
        if not sel_elements or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Assign Hinge",
                "Select one or more elements first.",
            )
            return
        if not self._vm.project.sections:
            QMessageBox.warning(
                self._window,
                "Assign Hinge",
                "No sections defined. Add a section before assigning hinges.",
            )
            return
        dlg = AssignHingeDialog(len(sel_elements), self._vm.project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.values()
        replacements = []
        for el in self._vm.project.elements:
            if el.id in sel_elements:
                replacements.append(
                    BeamWithHingesElement(
                        id=el.id,
                        name=el.name,
                        nodes=el.nodes,
                        section_i_id=vals["section_i_id"],
                        section_j_id=vals["section_j_id"],
                        lp_i=vals["lp_i"],
                        lp_j=vals["lp_j"],
                        E=vals["E"],
                        A=vals["A"],
                        Iz=vals["Iz"],
                        Iy=vals["Iy"],
                        G=vals["G"],
                        J=vals["J"],
                        geom_transf=getattr(el, "geom_transf", "Linear"),
                        # Keep the member's weight per length: gamma on the new A.
                        unit_weight=section_weight_per_length(
                            self._vm.project, getattr(el, "section_id", 0)
                        )
                        / vals["A"],
                    )
                )
        self._vm.apply_command(ReplaceElementsCommand(self._vm, replacements))
        self._shell.log(f"Converted {len(sel_elements)} element(s) to BeamWithHinges.")

    def assign_wall(self) -> None:
        """Assign → Frame → RC Wall: selected vertical members to MVLEM, one undo step."""
        from opensees_studio.views.dialogs.assign_wall import AssignWallDialog

        project = self._vm.project
        selected = set(self._shell.canvas().selection.elements)
        if project is None or not selected:
            QMessageBox.information(
                self._window, "RC Wall", "Select the vertical members of the wall first."
            )
            return
        dialog = AssignWallDialog(project, selected, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        conversion = dialog.conversion()
        if conversion is None or not conversion.elements:
            return
        stack = self._vm.undo_stack
        stack.beginMacro("Assign RC wall")
        try:
            if conversion.materials:
                self._vm.apply_command(AddMaterialsCommand(self._vm, conversion.materials))
            self._vm.apply_command(ReplaceElementsCommand(self._vm, conversion.elements))
        finally:
            stack.endMacro()
        self._shell.log(
            f"RC wall: {len(conversion.elements)} member(s) became MVLEM segments"
            + (f", {len(conversion.skipped)} left as they were." if conversion.skipped else ".")
        )

    def assign_pile(self) -> None:
        """Assign → Frame → Pile Soil Springs: p-y, t-z and q-z springs along the pile."""
        from opensees_studio.views.dialogs.pile_springs import PileSpringsDialog

        project = self._vm.project
        selected = set(self._shell.canvas().selection.elements)
        if project is None or not selected:
            QMessageBox.information(
                self._window, "Pile Soil Springs", "Select the pile's members first."
            )
            return
        dialog = PileSpringsDialog(project, selected, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        springs = dialog.springs()
        if springs is None or not springs.elements:
            return
        stack = self._vm.undo_stack
        stack.beginMacro("Assign pile soil springs")
        try:
            self._vm.apply_command(AddNodesCommand(self._vm, springs.nodes))
            self._vm.apply_command(AddMaterialsCommand(self._vm, springs.materials))
            self._vm.apply_command(AddElementsCommand(self._vm, springs.elements))
        finally:
            stack.endMacro()
        self._shell.log("Pile soil springs: " + " ".join(springs.notes))

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
