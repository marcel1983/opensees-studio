"""Assign → Joint: restraints, masses, springs, and what joins two joints."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import (
    AddElementsCommand,
    AddEqualDOFConstraintCommand,
    SetMassCommand,
    SetRestraintCommand,
    SetSpringCommand,
)
from opensees_studio.core import SLIDING_BEARING_CLASSES, ZeroLengthSectionElement, labels_for
from opensees_studio.core.materials.library import is_uniaxial
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    AssignElastomericBearingDialog,
    AssignEqualDOFDialog,
    AssignMassesDialog,
    AssignSupportDialog,
    AssignZeroLengthDialog,
    AssignZeroLengthSectionDialog,
)
from opensees_studio.views.dialogs.assign_springs import AssignSpringsDialog


class JointsController(QObject):
    """What holds a joint, what it weighs, and what ties it to another one.

    Restraints, masses and support springs go on every selected joint. An
    equalDOF constraint, a zero-length element or section, a bearing and a
    link need exactly two: the commands say so when the selection is not that.
    It keeps no state.
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    def assign_support(self) -> None:
        sel_nodes = set(self._shell.canvas().selection.nodes)
        if not sel_nodes:
            QMessageBox.information(
                self._window, "Assign Support", "Select one or more nodes first."
            )
            return
        project = self._vm.project
        dlg = AssignSupportDialog(len(sel_nodes), self._window, ndm=project.ndm if project else 3)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetRestraintCommand(self._vm, sel_nodes, dlg.restraint()))
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Support failed", str(exc))

    def assign_masses(self) -> None:
        """Assign → Joint → Masses: bulk-set mass on every selected node."""
        sel_nodes = set(self._shell.canvas().selection.nodes)
        if not sel_nodes or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Assign Masses",
                "Select one or more nodes first.",
            )
            return
        dlg = AssignMassesDialog(
            len(sel_nodes), ndf=self._vm.project.ndf, ndm=self._vm.project.ndm, parent=self._window
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetMassCommand(self._vm, sel_nodes, dlg.mass_vector()))
            self._shell.log(f"Assigned mass to {len(sel_nodes)} node(s).")
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Masses failed", str(exc))

    def assign_springs(self) -> None:
        """Assign → Joint → Springs: elastic support springs on every selected joint."""
        project = self._vm.project
        sel_nodes = set(self._shell.canvas().selection.nodes)
        if not sel_nodes or project is None:
            QMessageBox.information(
                self._window, "Assign Springs", "Select one or more joints first."
            )
            return
        first = next(n for n in project.nodes if n.id in sel_nodes)
        labels = labels_for(project.meta.units)
        dlg = AssignSpringsDialog(
            len(sel_nodes),
            project.ndm,
            project.ndf,
            current=first.spring,
            units=(f"{labels.force}/{labels.length}", f"{labels.moment}/rad"),
            parent=self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetSpringCommand(self._vm, sel_nodes, dlg.spring_vector()))
            self._shell.log(f"Assigned support springs to {len(sel_nodes)} joint(s).")
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Springs failed", str(exc))

    def assign_equal_dof(self) -> None:
        sel = sorted(self._shell.canvas().selection.nodes)
        if len(sel) != 2 or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Assign EqualDOF",
                "Select exactly two nodes first.",
            )
            return
        dlg = AssignEqualDOFDialog(
            sel, ndf=self._vm.project.ndf, parent=self._window, ndm=self._vm.project.ndm
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(AddEqualDOFConstraintCommand(self._vm, dlg.constraint()))
            self._shell.log(f"Added equalDOF constraint between nodes {sel[0]} and {sel[1]}.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign EqualDOF failed", str(exc))

    def assign_zero_length(self) -> None:
        """Assign > Joint > Zero-Length Element: one material per global DOF."""
        sel = sorted(self._shell.canvas().selection.nodes)
        project = self._vm.project
        if len(sel) != 2 or project is None:
            QMessageBox.information(
                self._window,
                "Assign Zero-Length Element",
                "Select exactly two coincident joints first.",
            )
            return
        n1, n2 = (project.node(node_id) for node_id in sel)
        if any(abs(n1.coords[k] - n2.coords[k]) > 1e-6 for k in range(3)):
            QMessageBox.warning(
                self._window,
                "Assign Zero-Length Element",
                f"Joints {sel[0]} and {sel[1]} are not coincident. "
                "Move one onto the other before creating the element.",
            )
            return
        if not any(is_uniaxial(material) for material in project.materials):
            QMessageBox.warning(
                self._window,
                "Assign Zero-Length Element",
                "Define a uniaxial material first (Material Library).",
            )
            return
        dlg = AssignZeroLengthDialog(project, (sel[0], sel[1]), parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            element = dlg.build_element(project.next_element_id())
            self._vm.apply_command(AddElementsCommand(self._vm, [element]))
            dofs = ", ".join(str(dof) for dof in element.dofs)
            self._shell.log(
                f"Created {element.type} {element.id} between joints "
                f"{element.nodes[0]}-{element.nodes[1]} (DOFs {dofs})."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Zero-Length Element failed", str(exc))

    def assign_zls(self) -> None:
        """Assign → Joint → Zero-Length Section: wrap 2 coincident nodes."""
        sel = sorted(self._shell.canvas().selection.nodes)
        if len(sel) != 2 or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Assign Zero-Length Section",
                "Select exactly two coincident nodes first.",
            )
            return
        # Verify coincidence — differ by more than 1e-6 in any axis is
        # a modelling error; zeroLengthSection needs coincident nodes.
        n1, n2 = (next(n for n in self._vm.project.nodes if n.id == sel[i]) for i in (0, 1))
        if any(abs(n1.coords[k] - n2.coords[k]) > 1e-6 for k in range(3)):
            QMessageBox.warning(
                self._window,
                "Assign Zero-Length Section",
                f"Nodes {sel[0]} and {sel[1]} are not coincident. "
                "Move one onto the other before creating the element.",
            )
            return
        if not self._vm.project.sections:
            QMessageBox.warning(
                self._window,
                "Assign Zero-Length Section",
                "Define a section first (Define → Section Library).",
            )
            return
        dlg = AssignZeroLengthSectionDialog(
            self._vm.project,
            (sel[0], sel[1]),
            parent=self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        sec_id = dlg.section_id()
        if sec_id is None:
            return
        try:
            eid = self._vm.project.next_element_id()
            elem = ZeroLengthSectionElement(
                id=eid,
                nodes=(sel[0], sel[1]),
                section_id=int(sec_id),
            )
            self._vm.apply_command(AddElementsCommand(self._vm, [elem]))
            self._shell.log(
                f"Created ZeroLengthSection {eid} "
                f"between nodes {sel[0]}-{sel[1]} (section {sec_id})."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Zero-Length Section failed", str(exc))

    def assign_bearing(self) -> None:
        """Assign > Joint > Bearing: elastomeric or sliding isolator between two joints."""
        sel = sorted(self._shell.canvas().selection.nodes)
        if len(sel) != 2 or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Assign Bearing",
                "Select exactly two nodes first (bottom, then top).",
            )
            return
        dlg = AssignElastomericBearingDialog(
            self._vm.project, (sel[0], sel[1]), parent=self._window
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._create_bearing(dlg)

    def assign_link(self) -> None:
        """Assign > Joint > Link: a twoNodeLink or a Triple Friction Pendulum between two joints."""
        from opensees_studio.views.dialogs.assign_link import AssignLinkDialog

        sel = sorted(self._shell.canvas().selection.nodes)
        project = self._vm.project
        if len(sel) != 2 or project is None:
            QMessageBox.information(self._window, "Assign Link", "Select exactly two joints first.")
            return
        dlg = AssignLinkDialog(project, (sel[0], sel[1]), parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            element = dlg.build_element(project.next_element_id())
            self._vm.apply_command(AddElementsCommand(self._vm, [element]))
            self._shell.log(
                f"Created {element.type} {element.id} between joints {sel[0]}-{sel[1]}."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Link failed", str(exc))

    def _create_bearing(self, dlg: AssignElastomericBearingDialog) -> bool:
        """Build the bearing the dialog describes and add it undoably."""
        if self._vm.project is None:
            return False
        try:
            eid = self._vm.project.next_element_id()
            elem = dlg.build_element(eid)
            self._vm.apply_command(AddElementsCommand(self._vm, [elem]))
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Bearing failed", str(exc))
            return False
        if isinstance(elem, SLIDING_BEARING_CLASSES):
            detail = f"Kinit {elem.k_init:g}, friction model {elem.friction_model_id}"
            if elem.type == "SingleFPBearing":
                detail += f", Reff {elem.r_eff:g}"
        else:
            detail = f"Kinit {elem.k_init:g}, Qd {elem.qd:g}, alpha1 {elem.alpha1:g}"
        self._shell.log(
            f"Created {elem.type} {eid} between nodes {elem.nodes[0]}-{elem.nodes[1]} ({detail})."
        )
        return True
