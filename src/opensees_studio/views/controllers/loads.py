"""Loads on joints, frames and areas, joint patterns, and Edit → Delete Loads."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import (
    AddElementLoadsCommand,
    AddNodalLoadsCommand,
    AddPointElementLoadsCommand,
    AddTemperatureLoadsCommand,
    AddTrapezoidalElementLoadsCommand,
    SetJointPatternsCommand,
)
from opensees_studio.core import SHELL_ELEMENT_CLASSES
from opensees_studio.core.units import labels_for
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    AssignDistributedLoadDialog,
    AssignLoadDialog,
    AssignPointElementLoadDialog,
    AssignTemperatureLoadDialog,
    TrapezoidalLoadDialog,
)
from opensees_studio.views.dialogs.area_loads import (
    FloorLoadDialog,
    ImposedDisplacementDialog,
    SurfaceLoadDialog,
)
from opensees_studio.views.dialogs.joint_patterns import (
    AssignJointPatternDialog,
    JointPatternsDialog,
)
from opensees_studio.views.dialogs.load_target import force_units, plain_patterns


class LoadsController(QObject):
    """Assigns loads to the selection and removes them.

    Every command reads the selection of the focused viewport, opens its
    dialog and pushes one undo step; a load goes to the pattern the dialog
    names (or a new one). Joint patterns are here because they exist to scale
    a surface load (a hydrostatic pressure is a pattern of depths).
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    # ── joints ────────────────────────────────────────────────────────
    def assign_nodal_load(self) -> None:
        sel_nodes = set(self._shell.canvas().selection.nodes)
        if not sel_nodes or self._vm.project is None:
            QMessageBox.information(self._window, "Assign Load", "Select one or more nodes first.")
            return
        from opensees_studio.core import PlainLoadPattern

        existing = [
            (p.id, p.name)
            for p in self._vm.project.load_patterns
            if isinstance(p, PlainLoadPattern)
        ]
        labels = labels_for(self._vm.project.meta.units)
        dlg = AssignLoadDialog(
            len(sel_nodes),
            existing_patterns=existing,
            parent=self._window,
            force_unit=labels.force,
            length_unit=labels.length,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            pid = dlg.selected_pattern_id()
            new_name = dlg.new_pattern_name() if pid is None else None
            new_ts_type = dlg.new_time_series_type() if pid is None else "Linear"
            self._vm.apply_command(
                AddNodalLoadsCommand(
                    self._vm,
                    sel_nodes,
                    dlg.forces(),
                    pattern_id=pid,
                    new_pattern_name=new_name,
                    new_ts_type=new_ts_type,
                    mode=dlg.load_mode(),
                )
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Load failed", str(exc))

    def assign_imposed_displacement(self) -> None:
        """Assign > Joint > Imposed Displacement: a static settlement of the selected joints."""
        project = self._vm.project
        nodes = sorted(self._shell.canvas().selection.nodes)
        if project is None or not nodes:
            return
        dlg = ImposedDisplacementDialog(len(nodes), project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_pattern_loads(
            "imposed_displacements", dlg.loads(nodes), dlg.pattern_id(), "Imposed Displacement"
        )
        self._shell.log(f"Imposed displacement on {len(nodes)} joint(s).")

    # ── frames ────────────────────────────────────────────────────────
    def assign_distributed_load(self) -> None:
        project = self._vm.project
        sel_elements = set(self._shell.canvas().selection.elements)
        if project is None or not sel_elements:
            QMessageBox.information(
                self._window,
                "Assign Distributed Load",
                "Select one or more elements first.",
            )
            return
        dlg = AssignDistributedLoadDialog(
            len(sel_elements),
            ndm=project.ndm,
            parent=self._window,
            patterns=plain_patterns(project),
            units=force_units(project, per_length=True),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        fx, fy, fz = dlg.values()
        pid, mode = dlg.pattern_id(), dlg.load_mode()
        try:
            if dlg.is_local():
                self._vm.apply_command(
                    AddElementLoadsCommand(
                        self._vm, sel_elements, wy=fy, wz=fz, wx=fx, pattern_id=pid, mode=mode
                    ),
                )
            else:
                self._vm.apply_command(
                    AddElementLoadsCommand(
                        self._vm,
                        sel_elements,
                        global_vector=(fx, fy, fz),
                        pattern_id=pid,
                        mode=mode,
                    ),
                )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Distributed Load failed", str(exc))

    def assign_frame_point_load(self) -> None:
        """Assign → Frame → Point Load: a concentrated load inside each selected frame."""
        from opensees_studio.core import FRAME_ELEMENT_CLASSES
        from opensees_studio.views.dialogs.point_element_load import RELATIVE

        project = self._vm.project
        selected = set(self._shell.canvas().selection.elements)
        if project is None or not selected:
            QMessageBox.information(
                self._window, "Assign Frame Point Load", "Select one or more frame elements first."
            )
            return
        frames = [
            el
            for el in project.elements
            if el.id in selected and isinstance(el, FRAME_ELEMENT_CLASSES)
        ]
        if not frames:
            QMessageBox.information(
                self._window,
                "Assign Frame Point Load",
                "None of the selected elements is a frame (beam-column) element.",
            )
            return
        dlg = AssignPointElementLoadDialog(
            len(frames),
            ndm=project.ndm,
            parent=self._window,
            patterns=plain_patterns(project),
            units=force_units(project),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        fx, fy, fz = dlg.vector()
        pid, mode = dlg.pattern_id(), dlg.load_mode()

        positions: dict[int, float] = {}
        too_short: list[int] = []
        coords = {node.id: node.coords for node in project.nodes}
        for el in frames:
            if dlg.mode() == RELATIVE or mode == "delete":
                positions[el.id] = dlg.distance()
                continue
            length = math.dist(coords[el.nodes[0]], coords[el.nodes[1]])
            if length <= 0.0 or dlg.distance() > length:
                too_short.append(el.id)
                continue
            positions[el.id] = dlg.distance() / length
        if not positions:
            QMessageBox.warning(
                self._window,
                "Assign Frame Point Load",
                "The distance is longer than every selected element.",
            )
            return
        try:
            if dlg.is_local():
                self._vm.apply_command(
                    AddPointElementLoadsCommand(
                        self._vm, positions, py=fy, pz=fz, px=fx, pattern_id=pid, mode=mode
                    ),
                )
            else:
                self._vm.apply_command(
                    AddPointElementLoadsCommand(
                        self._vm, positions, global_vector=(fx, fy, fz), pattern_id=pid, mode=mode
                    ),
                )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Frame Point Load failed", str(exc))
            return
        skipped = len(selected) - len(frames)
        message = f"Assigned a point load to {len(positions)} frame element(s)."
        if skipped:
            message += f" Skipped {skipped} element(s) that are not frames."
        if too_short:
            message += " Skipped element(s) shorter than the distance: " + ", ".join(
                str(eid) for eid in too_short
            )
        self._shell.log(message)

    def assign_trapezoidal_load(self) -> None:
        """Assign > Frame > Trapezoidal Load: a linearly varying load over part of each member."""
        project = self._vm.project
        ids = self._selected_frames("Frame Trapezoidal Load")
        if project is None or not ids:
            return
        dlg = TrapezoidalLoadDialog(
            len(ids),
            project.ndm,
            self._window,
            patterns=plain_patterns(project),
            units=force_units(project, per_length=True),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        pid, mode = dlg.pattern_id(), dlg.load_mode()
        try:
            if dlg.is_local():
                command = AddTrapezoidalElementLoadsCommand(
                    self._vm, ids, values, pattern_id=pid, mode=mode
                )
            else:
                command = AddTrapezoidalElementLoadsCommand(
                    self._vm,
                    ids,
                    {"x_start": values["x_start"], "x_end": values["x_end"]},
                    global_start=(
                        values["wx_start"],
                        values["wy_start"],
                        values["wz_start"],
                    ),
                    global_end=(
                        values["wx_end"],
                        values["wy_end"],
                        values["wz_end"],
                    ),
                    pattern_id=pid,
                    mode=mode,
                )
            self._vm.apply_command(command)
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Frame Trapezoidal Load failed", str(exc))
            return
        self._shell.log(f"{command.text()} ({dlg.target.pattern_text()}).")

    def assign_temperature_load(self) -> None:
        """Assign → Frame → Temperature Load: uniform ΔT and gradients on the selected members.

        Every selected member is checked before anything changes: the method needs
        elastic members without releases or end offsets (see ``core.thermal``).
        """
        from opensees_studio.core import TemperatureLoad
        from opensees_studio.core.thermal import ThermalLoadError, fixed_end_forces

        project = self._vm.project
        selected = set(self._shell.canvas().selection.elements)
        if project is None or not selected:
            QMessageBox.information(
                self._window, "Assign Temperature Load", "Select one or more frame members first."
            )
            return
        refused = []
        for element_id in sorted(selected):
            try:
                fixed_end_forces(project, TemperatureLoad(element_id=element_id, alpha=1.0))
            except ThermalLoadError as exc:
                refused.append(str(exc))
        if refused:
            QMessageBox.warning(self._window, "Assign Temperature Load", "\n".join(refused[:8]))
            return
        dialog = AssignTemperatureLoadDialog(len(selected), ndm=project.ndm, parent=self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            values = dialog.values()
            self._vm.apply_command(
                AddTemperatureLoadsCommand(
                    self._vm,
                    selected,
                    alpha=values["alpha"],
                    uniform=values["uniform"],
                    gradient_y=values["gradient_y"],
                    gradient_z=values["gradient_z"],
                )
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Temperature Load failed", str(exc))

    def assign_tendon(self) -> None:
        """Assign → Frame → Tendon (Post-Tensioning): a tendon in each selected member."""
        from opensees_studio.core import TendonLoad
        from opensees_studio.views.dialogs.tendon_load import TendonLoadDialog

        project = self._vm.project
        if project is None:
            return
        selected = set(self._shell.canvas().selection.elements)
        members = sorted(e.id for e in project.elements if e.id in selected and len(e.nodes) == 2)
        if not members:
            QMessageBox.information(
                self._window, "Tendon", "Select one or more frame members first."
            )
            return
        dlg = TendonLoadDialog(len(members), project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        loads = [TendonLoad(element_id=eid, **values) for eid in members]  # type: ignore[arg-type]
        self._apply_pattern_loads("tendon_loads", loads, dlg.pattern_id(), "Tendon")
        self._shell.log(f"Tendon of {values['force']:g} in {len(members)} member(s).")

    # ── areas ─────────────────────────────────────────────────────────
    def assign_surface_load(self) -> None:
        """Assign > Area > Surface Load on Shells: a uniform pressure on the selected shells."""
        from opensees_studio.core import SurfaceLoad

        project = self._vm.project
        if project is None:
            return
        selected = set(self._shell.canvas().selection.elements)
        shells = sorted(
            el.id
            for el in project.elements
            if el.id in selected and isinstance(el, SHELL_ELEMENT_CLASSES)
        )
        if not shells:
            QMessageBox.information(
                self._window, "Surface Load", "Select one or more shells first."
            )
            return
        dlg = SurfaceLoadDialog(len(shells), project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        loads = [SurfaceLoad(element_id=eid, **values) for eid in shells]
        self._apply_pattern_loads("surface_loads", loads, dlg.pattern_id(), "Surface Load")
        by = ""
        if "joint_pattern_id" in values:
            pattern = next(p for p in project.joint_patterns if p.id == values["joint_pattern_id"])
            by = f" × joint pattern {pattern.name or pattern.id}"
        self._shell.log(
            f"Surface load {values['value']:g}{by} ({values['direction']}) on "
            f"{len(shells)} shell(s)."
        )

    def assign_floor_load(self) -> None:
        """Assign > Area > Floor Load to Frames: every bay the selected joints frame."""
        from opensees_studio.core.area_loads import floor_panels

        project = self._vm.project
        if project is None:
            return
        panels = floor_panels(project, set(self._shell.canvas().selection.nodes))
        if not panels:
            QMessageBox.information(
                self._window,
                "Floor Load",
                "Select the joints of a floor: the load goes to every rectangular bay whose "
                "four corners are selected and whose four sides are framed by beams.",
            )
            return
        dlg = FloorLoadDialog(panels, project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        loads = dlg.loads()
        self._apply_pattern_loads("floor_loads", loads, dlg.pattern_id(), "Floor Load")
        self._shell.log(f"Floor load on {len(loads)} bay(s).")

    # ── joint patterns ────────────────────────────────────────────────
    def define_joint_patterns(self) -> None:
        """Define → Joint Patterns: add, rename, delete patterns and edit their values."""
        project = self._vm.project
        if project is None:
            return
        dlg = JointPatternsDialog(project, self._window)
        try:
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            patterns = dlg.patterns()
        finally:
            dlg.deleteLater()
        try:
            self._vm.apply_command(SetJointPatternsCommand(self._vm, patterns))
        except ValueError as exc:
            QMessageBox.critical(self._window, "Joint Patterns", str(exc))
            return
        self._shell.canvas().render()
        self._shell.log(f"Joint patterns: {len(patterns)}.")

    def assign_joint_pattern(self) -> None:
        """Assign → Joint → Joint Pattern Values: the selected joints' values, as SAP2000 does."""
        project = self._vm.project
        if project is None:
            return
        nodes = sorted(self._shell.canvas().selection.nodes)
        if not nodes:
            QMessageBox.information(
                self._window, "Joint Pattern Values", "Select one or more joints first."
            )
            return
        dlg = AssignJointPatternDialog(project, nodes, self._window)
        try:
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            patterns, name = dlg.patterns(), dlg.pattern_name()
        finally:
            dlg.deleteLater()
        self._vm.apply_command(
            SetJointPatternsCommand(
                self._vm, patterns, f"Joint pattern {name}: {len(nodes)} joint(s)"
            )
        )
        self._shell.canvas().render()
        self._shell.log(f"Joint pattern {name}: values on {len(nodes)} joint(s).")

    # ── removing, and the one way a pattern load is stored ────────────
    def delete_loads(self) -> None:
        """Edit → Delete Loads: remove loads by type, pattern and selection, one undo step."""
        from opensees_studio.commands import DeleteLoadsCommand
        from opensees_studio.core.load_removal import KINDS_BY_KEY
        from opensees_studio.views.dialogs.delete_loads import DeleteLoadsDialog

        project = self._vm.project
        if project is None:
            return
        dialog = DeleteLoadsDialog(
            project,
            selected_nodes=set(self._shell.canvas().selection.nodes),
            selected_elements=set(self._shell.canvas().selection.elements),
            parent=self._window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        command = DeleteLoadsCommand(self._vm, dialog.kinds(), dialog.scope())
        try:
            self._vm.apply_command(command)
        except Exception as exc:
            QMessageBox.critical(self._window, "Could not delete the loads", str(exc))
            return
        done = [f"{n} {KINDS_BY_KEY[k].label.lower()}" for k, n in command.removed.items() if n]
        self._shell.log("Delete Loads: " + (", ".join(done) if done else "nothing removed") + ".")

    def _apply_pattern_loads(
        self, list_name: str, loads: list[Any], pattern_id: int | None, title: str
    ) -> None:
        from opensees_studio.commands import AddPatternLoadsCommand

        try:
            self._vm.apply_command(AddPatternLoadsCommand(self._vm, list_name, loads, pattern_id))
        except Exception as exc:
            QMessageBox.critical(self._window, f"{title} failed", str(exc))

    def _selected_frames(self, title: str) -> set[int]:
        """The selected frame members; says so, and returns nothing, when there is none."""
        from opensees_studio.core import FrameMember

        project = self._vm.project
        selected = set(self._shell.canvas().selection.elements)
        frames = (
            set()
            if project is None
            else {
                el.id
                for el in project.elements
                if el.id in selected and isinstance(el, FrameMember)
            }
        )
        if not frames:
            QMessageBox.information(self._window, title, "Select one or more frame elements first.")
        return frames
