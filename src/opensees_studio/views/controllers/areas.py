"""Shells and distributed support springs: create, formulation, area/edge/line springs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from opensees_studio.commands import AddElementsCommand, ReplaceElementsCommand
from opensees_studio.commands.support_springs import SetSupportSpringsCommand
from opensees_studio.core import (
    SHELL_ELEMENT_CLASSES,
    ShellDKGTElement,
    ShellMITC4Element,
    labels_for,
    with_shell_formulation,
)
from opensees_studio.core.geometry.ordering import QuadOrderError, order_quad_nodes
from opensees_studio.core.sections import SHELL_SECTION_CLASSES
from opensees_studio.core.support_springs import AreaSpring, EdgeSpring, LineSpring
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.support_springs import SupportSpringDialog


class AreasController(QObject):
    """What a slab or a wall panel is, and the ground under it.

    Define → Create Shell builds a shell on three or four selected joints (it
    orders a quadrilateral itself), Assign → Shell Formulation swaps the element
    formulation, and the three spring commands set the distributed support
    springs under shells, along their edges and under frame members. It keeps
    no state.
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    def create_shell(self) -> None:
        """Define → Create Shell: a ShellMITC4 from four selected nodes, a ShellDKGT from three.

        The selection carries no order, so the winding is derived from the
        nodes' coordinates: a shell built from a scrambled list is inverted or
        twisted, and the user has no way to express "counter-clockwise" by
        clicking.
        """
        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Create shell", "Open or create a project first.")
            return
        selected = [n for n in project.nodes if n.id in self._shell.canvas().selection.nodes]
        if len(selected) not in (3, 4):
            QMessageBox.information(
                self._window,
                "Create shell",
                "Select four nodes (a quadrilateral) or three (a triangle) first "
                f"(you have {len(selected)}).",
            )
            return
        plate_sections = [s for s in project.sections if isinstance(s, SHELL_SECTION_CLASSES)]
        if not plate_sections:
            QMessageBox.information(
                self._window,
                "Create shell",
                "A shell needs a plate section. Add one from Define → Section Library "
                "(type 'Plate Section (shell)').",
            )
            return
        if len(plate_sections) == 1:
            section = plate_sections[0]
        else:
            labels = [f"#{s.id} {s.name} (h = {s.h:g})" for s in plate_sections]
            choice, accepted = QInputDialog.getItem(
                self._window, "Create shell", "Plate section:", labels, 0, False
            )
            if not accepted:
                return
            section = plate_sections[labels.index(choice)]
        element_id = project.next_element_id()
        if len(selected) == 3:
            # Any three points wind one way or the other: keep the selection order.
            corners = (selected[0].id, selected[1].id, selected[2].id)
            tri = ShellDKGTElement(id=element_id, nodes=corners, section_id=section.id)
            self._vm.apply_command(
                AddElementsCommand(self._vm, [tri], text=f"Add shell {element_id}")
            )
            self._shell.log(
                f"Shell {element_id} (ShellDKGT): nodes {tri.nodes}, plate section {section.id}."
            )
            return
        points = [
            (float(node.coords[0]), float(node.coords[1]), float(node.coords[2]))
            for node in selected
        ]
        try:
            order = order_quad_nodes(points)
        except QuadOrderError as exc:
            QMessageBox.critical(self._window, "Cannot build the shell", str(exc))
            return
        ordered = [selected[index] for index in order]
        nodes = (ordered[0].id, ordered[1].id, ordered[2].id, ordered[3].id)
        try:
            self._vm.apply_command(
                AddElementsCommand(
                    self._vm,
                    [ShellMITC4Element(id=element_id, nodes=nodes, section_id=section.id)],
                    text=f"Add shell {element_id}",
                )
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Cannot create the shell", str(exc))
            return
        self._shell.log(
            f"Shell {element_id}: nodes {nodes}, plate section {section.id} "
            f"(winding ordered counter-clockwise)."
        )

    def shell_formulation(self) -> None:
        """Assign → Area → Shell Formulation: MITC4, DKGQ or NLDKGQ (quads), DKGT or NLDKGT."""
        project = self._vm.project
        if project is None:
            return
        selected = set(self._shell.canvas().selection.elements)
        shells = [
            e for e in project.elements if e.id in selected and isinstance(e, SHELL_ELEMENT_CLASSES)
        ]
        if not shells:
            QMessageBox.information(
                self._window, "Shell Formulation", "Select one or more shells first."
            )
            return
        quads = [e for e in shells if len(e.nodes) == 4]
        tris = [e for e in shells if len(e.nodes) == 3]
        choices: list[tuple[str, str, str]] = [
            ("MITC4 / DKGT — the default pair", "ShellMITC4", "ShellDKGT"),
            ("DKGQ / DKGT — thin plates, drilling stiffness", "ShellDKGQ", "ShellDKGT"),
            ("NLDKGQ / NLDKGT — large displacements", "ShellNLDKGQ", "ShellNLDKGT"),
        ]
        labels = [c[0] for c in choices]
        choice, accepted = QInputDialog.getItem(
            self._window,
            "Shell Formulation",
            f"{len(quads)} quadrilateral and {len(tris)} triangular shell(s):",
            labels,
            0,
            False,
        )
        if not accepted:
            return
        _label, quad_kind, tri_kind = choices[labels.index(choice)]
        replaced = [
            with_shell_formulation(e, quad_kind if len(e.nodes) == 4 else tri_kind) for e in shells
        ]
        replaced = [new for new, old in zip(replaced, shells, strict=True) if new.type != old.type]
        if not replaced:
            self._shell.log("Shell formulation: nothing to change.")
            return
        self._vm.apply_command(ReplaceElementsCommand(self._vm, replaced))
        self._shell.log(
            f"Shell formulation: {len(replaced)} shell(s) are now {choice.split(' — ')[0]}."
        )
        self._shell.canvas().render()

    def assign_area_springs(self) -> None:
        """Assign → Area → Area Springs: a spring per area under the selected shells."""
        self._assign_springs_of("area")

    def assign_edge_springs(self) -> None:
        """Assign → Area → Edge Springs: along the shell edges whose two joints are selected."""
        self._assign_springs_of("edge")

    def assign_line_springs(self) -> None:
        """Assign → Frame → Line Springs: a spring per length under the selected members."""
        self._assign_springs_of("line")

    def _assign_springs_of(self, kind: str) -> None:
        """Add, replace or delete the support springs of one kind on the selection."""
        project = self._vm.project
        if project is None:
            return
        selected = set(self._shell.canvas().selection.elements)
        joints = set(self._shell.canvas().selection.nodes)
        targets: list[Any]
        if kind == "line":
            targets = [e for e in project.elements if e.id in selected and len(e.nodes) == 2]
            what = "frame members"
        else:
            targets = [
                e for e in project.elements if e.id in selected and isinstance(e, ShellMITC4Element)
            ]
            what = "shells"
        if not targets:
            QMessageBox.information(self._window, "Springs", f"Select one or more {what} first.")
            return
        edges: list[tuple[int, int]] = []
        if kind == "edge":
            edges = [
                (e.id, k + 1)
                for e in targets
                for k in range(4)
                if e.nodes[k] in joints and e.nodes[(k + 1) % 4] in joints
            ]
            if not edges:
                QMessageBox.information(
                    self._window,
                    "Edge Springs",
                    "Select the shells and the joints along the supported edge: an edge whose "
                    "two joints are selected takes the spring.",
                )
                return
        labels = labels_for(project.meta.units)
        dlg = SupportSpringDialog(
            kind,  # type: ignore[arg-type]
            len(edges) if kind == "edge" else len(targets),
            length_unit=labels.length,
            force_unit=labels.force,
            parent=self._window,
        )
        try:
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            values, mode = dlg.values(), dlg.mode()
        finally:
            dlg.deleteLater()
        area, line, edge = (
            list(project.area_springs),
            list(project.line_springs),
            list(project.edge_springs),
        )
        ids = {e.id for e in targets}
        if kind == "area":
            if mode != "add":
                area = [s for s in area if s.element_id not in ids]
            if mode != "delete":
                area += [AreaSpring(element_id=i, **values) for i in sorted(ids)]  # type: ignore[arg-type]
        elif kind == "line":
            if mode != "add":
                line = [s for s in line if s.element_id not in ids]
            if mode != "delete":
                line += [LineSpring(element_id=i, **values) for i in sorted(ids)]  # type: ignore[arg-type]
        else:
            chosen = set(edges)
            if mode != "add":
                edge = [s for s in edge if (s.element_id, s.edge) not in chosen]
            if mode != "delete":
                edge += [EdgeSpring(element_id=i, edge=k, **values) for i, k in edges]  # type: ignore[arg-type]
        count = len(edges) if kind == "edge" else len(ids)
        self._vm.apply_command(
            SetSupportSpringsCommand(
                self._vm, area, line, edge, f"{mode.capitalize()} {kind} springs on {count}"
            )
        )
        self._shell.canvas().render()
        self._shell.log(
            f"{kind.capitalize()} springs: {mode} on {count} {'edge' if kind == 'edge' else 'element'}(s)."
        )
