"""Define → Coordinate System/Grids and Grid Wizard; View → Show Grids and Grid Labels."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import SetCoordSystemsCommand
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import CoordinateGridSystemsDialog
from opensees_studio.views.dialogs.grid_wizard import GridWizardDialog


class GridsController(QObject):
    """The coordinate systems of the project and their grid lines.

    Every change is one ``SetCoordSystemsCommand``, so showing or hiding a
    grid is an undo step like editing it. Both dialogs work with no project
    open: ``new_project`` (File → New) starts one first. ``sync_actions`` has
    the window tick Show Grids and Show Grid Labels from the project again;
    those two checkable commands stay with the window.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        new_project: Callable[[], None],
        sync_actions: Callable[[], None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._new_project = new_project
        self._sync_actions = sync_actions

    def define(self) -> None:
        """Open the SAP2000-style Coordinate/Grid Systems manager."""
        if self._vm.project is None:
            self._new_project()
        proj = self._vm.project
        assert proj is not None
        dlg = CoordinateGridSystemsDialog(proj.coord_systems, parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            new_systems = dlg.result_systems()
            self._vm.apply_command(SetCoordSystemsCommand(self._vm, new_systems))
            names = ", ".join(cs.name for cs in new_systems)
            self._shell.log(f"Coordinate/Grid Systems updated: {names}.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Grid update failed", str(exc))

    def wizard(self) -> None:
        """Define → Grid Wizard: a regular Cartesian or radial grid, one undo step."""
        if self._vm.project is None:
            self._new_project()
        project = self._vm.project
        assert project is not None
        dlg = GridWizardDialog(project.coord_systems, ndm=project.ndm, parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        target = dlg.target()
        if target:
            systems = [
                cs.model_copy(update={"grid": dlg.grid_system()}) if cs.name == target else cs
                for cs in project.coord_systems
            ]
            name = target
        else:
            new = dlg.system()
            systems = [*project.coord_systems, new]
            name = new.name
        self._vm.apply_command(SetCoordSystemsCommand(self._vm, systems))
        self._shell.log(f"Grid Wizard: grid of '{name}' set.")

    def set_shown(self, shown: bool, name: str | None = None) -> None:
        """Show or hide the grids (all, or the system called ``name``): an undo step.

        The same flag as the Hide All Grid Lines box of the grid dialog.
        """
        project = self._vm.project
        if project is None:
            return
        systems = [
            cs.model_copy(update={"grid": cs.grid.model_copy(update={"hide_all": not shown})})
            if name is None or cs.name == name
            else cs
            for cs in project.coord_systems
        ]
        if systems != project.coord_systems:
            self._vm.apply_command(SetCoordSystemsCommand(self._vm, systems))
        self._sync_actions()

    def set_labels_shown(self, shown: bool) -> None:
        project = self._vm.project
        if project is None:
            return
        systems = [
            cs.model_copy(update={"grid": cs.grid.model_copy(update={"show_labels": shown})})
            for cs in project.coord_systems
        ]
        if systems != project.coord_systems:
            self._vm.apply_command(SetCoordSystemsCommand(self._vm, systems))
        self._sync_actions()
