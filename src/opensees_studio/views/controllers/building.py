"""Storeys, mass source, seismic loads, diaphragms, rigid links."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import (
    AddDiaphragmCommand,
    AddRigidLinkCommand,
    RemoveConstraintsCommand,
    SetMassSourceCommand,
    SetStoreysCommand,
)
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.buildings import (
    AssignDiaphragmDialog,
    AssignRigidLinkDialog,
    MassSourceDialog,
    StoreysDialog,
)
from opensees_studio.views.dialogs.seismic_loads import SeismicLoadsDialog


class BuildingController(QObject):
    """What makes a frame a building: its storeys, its mass and what ties a floor.

    Define → Storeys, Mass Source and Seismic Loads; Assign → Diaphragm, Rigid
    Link and Remove Constraints. It keeps no state: each command opens its
    dialog on the project as it is and pushes one undo step.
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    # ── define ───────────────────────────────────────────────────────
    def define_storeys(self) -> None:
        project = self._vm.project
        if project is None:
            return
        dlg = StoreysDialog(project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetStoreysCommand(self._vm, dlg.storeys()))
            self._shell.log(f"Storeys set: {len(project.storeys)}.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Define Storeys failed", str(exc))

    def define_mass_source(self) -> None:
        project = self._vm.project
        if project is None:
            return
        dlg = MassSourceDialog(project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetMassSourceCommand(self._vm, dlg.mass_source()))
            self._shell.log("Mass source updated.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Define Mass Source failed", str(exc))

    def define_seismic_loads(self) -> None:
        """Define → Seismic Loads: ELF base shear and storey forces as load patterns."""
        if self._vm.project is None:
            return
        dlg = SeismicLoadsDialog(self._vm, self._window)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.written:
            self._shell.log(
                "Seismic loads written: " + ", ".join(dlg.written) + ". " + dlg.summary.text()
            )

    # ── assign ───────────────────────────────────────────────────────
    def assign_diaphragm(self) -> None:
        project = self._vm.project
        if project is None:
            return
        selected = sorted(self._shell.canvas().selection.nodes)
        dlg = AssignDiaphragmDialog(project, selected, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            diaphragm, retained = dlg.diaphragm()
            self._vm.apply_command(AddDiaphragmCommand(self._vm, diaphragm, retained))
            where = f"new node {retained.id}" if retained else f"node {diaphragm.retained_node}"
            self._shell.log(
                f"Added rigid diaphragm {diaphragm.name or diaphragm.id}, retained {where}."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Diaphragm failed", str(exc))

    def assign_rigid_link(self) -> None:
        selected = sorted(self._shell.canvas().selection.nodes)
        if len(selected) != 2 or self._vm.project is None:
            QMessageBox.information(
                self._window, "Assign Rigid Link", "Select exactly two nodes first."
            )
            return
        dlg = AssignRigidLinkDialog(selected, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            link = dlg.link()
            self._vm.apply_command(AddRigidLinkCommand(self._vm, link))
            self._shell.log(
                f"Added rigid {link.kind} link {link.retained_node} -> {link.constrained_node}."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign Rigid Link failed", str(exc))

    def remove_constraints(self) -> None:
        """Assign → Remove Constraints: equalDOF, rigid links and diaphragms of the selected joints."""
        selected = set(self._shell.canvas().selection.nodes)
        if not selected or self._vm.project is None:
            return
        self._vm.apply_command(RemoveConstraintsCommand(self._vm, selected))
        self._shell.log(f"Removed the constraints of {len(selected)} node(s).")
