"""File → Import: a drawing into the project, or another program's model as a new one."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

from opensees_studio.commands import AddElementsCommand, AddNodesCommand, AddSectionsCommand
from opensees_studio.core import UnitSystem, make_default_section
from opensees_studio.core.model_check import check_model
from opensees_studio.diagnostics.performance import perf
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    DxfImportDialog,
    S3dImportDialog,
    TclImportDialog,
    member_sections,
)


class ImportsController(QObject):
    """What comes in from another program.

    A DXF drawing adds bars to the open project in one undo step. A PORTICO,
    SAP2000 text, IFC or Tcl file replaces the project: the command asks about
    unsaved changes first (confirm_discard, the prompt New and Open share),
    adopts the imported project and has the window take its saved viewport
    (apply_view_settings). What a file has and the import cannot carry goes
    to the log. It keeps no state.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        confirm_discard: Callable[[str], bool],
        apply_view_settings: Callable[[], None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._confirm_discard = confirm_discard
        self._apply_view_settings = apply_view_settings

    def dxf(self) -> None:
        """File → Import → DXF Drawing: bars from a drawing, in one undo step.

        The dialog decides what the drawing means (layers, units, plane); this
        inserts the result the same way the frame wizard does, so a bad import is
        one Ctrl+Z away.
        """
        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Import DXF", "Open or create a project first.")
            return

        dialog = DxfImportDialog(project, sections=member_sections(project), parent=self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        section_id = dialog.section_choice()
        if section_id is None:
            # Section ids are allocated inside the macro, so the models must be
            # built there too: the dialog is asked for the drawing, not for bars.
            section_id = project.next_section_id()

        self._vm.undo_stack.beginMacro("Import DXF")
        try:
            if dialog.section_choice() is None:
                self._vm.apply_command(
                    AddSectionsCommand(self._vm, [make_default_section(section_id, project)])
                )
            bars = dialog.imported_bars(section_id)
            if bars is None:
                return
            self._vm.apply_command(AddNodesCommand(self._vm, bars.nodes))
            self._vm.apply_command(AddElementsCommand(self._vm, bars.elements))
        except Exception as exc:
            QMessageBox.critical(self._window, "Could not import the drawing", str(exc))
            return
        finally:
            self._vm.undo_stack.endMacro()

        self._shell.canvas().selection.clear()
        for node in bars.nodes:
            self._shell.canvas().selection.select_node(node.id, additive=True)
        source = dialog.source()
        self._shell.log(
            f"Imported {bars.summary()} from {source.name if source else 'the drawing'}."
        )
        drawing = dialog.drawing()
        if drawing is not None and drawing.skipped_summary():
            self._shell.log(drawing.skipped_summary())

    def s3d(self) -> None:
        """File → Import → PORTICO Model: a ``.s3d`` file as a new, unsaved project.

        The whole model is replaced, so this asks about unsaved changes like Open
        does. What the file has and the import cannot carry is written to the log.
        """
        if not self._confirm_discard("Importing a PORTICO model"):
            return
        dialog = S3dImportDialog(parent=self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        imported = dialog.imported()
        if imported is None:
            return
        self._vm.adopt(imported.project)
        self._apply_view_settings()
        source = dialog.source()
        self._shell.log(
            f"Imported {source.name if source else 'the PORTICO model'} "
            f"({imported.source_units} → {imported.project.meta.units.value}): "
            f"{imported.summary()}"
        )
        for note in imported.notes:
            self._shell.log(note)

    def s2k(self) -> None:
        """File → Import → SAP2000 Text: a ``.s2k`` / ``.$2k`` file as a new, unsaved project.

        The whole model is replaced, so this asks about unsaved changes like Open
        does. What the file has and the import cannot carry is written to the log.
        """
        from opensees_studio.services.sap2000_text import (
            Sap2000TextError,
            import_s2k,
            read_s2k,
        )

        if not self._confirm_discard("Importing a SAP2000 text file"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self._window,
            "Import SAP2000 Text",
            "",
            "SAP2000 text (*.s2k *.$2k *.S2K *.$2K);;All files (*)",
        )
        if not path:
            return
        subdivisions: int | None = None
        try:
            if read_s2k(path).rows("FRAME SECTION PROPERTIES 05 - NONPRISMATIC"):
                subdivisions, ok = QInputDialog.getInt(
                    self._window,
                    "Nonprismatic members",
                    "Pieces per nonprismatic member (minimum 12):",
                    12,
                    12,
                    200,
                )
                if not ok:
                    return
        except Sap2000TextError as exc:
            QMessageBox.critical(self._window, "Import SAP2000 Text failed", str(exc))
            return
        try:
            with perf.span("ui.import_s2k"):
                imported = import_s2k(path, nonprismatic_subdivisions=subdivisions)
        except Sap2000TextError as exc:
            QMessageBox.critical(self._window, "Import SAP2000 Text failed", str(exc))
            return
        self._vm.adopt(imported.project)
        self._apply_view_settings()
        self._shell.log(
            f"Imported {Path(path).name} ({imported.source_units} → "
            f"{imported.project.meta.units.value}): {imported.summary()}"
        )
        for note in imported.notes:
            self._shell.log(note)

    def ifc(self) -> None:
        """File → Import → IFC: the analytical or the physical model as a new, unsaved project.

        The file is read once to say what it holds; the dialog chooses which model
        to build from. The whole model is replaced, so this asks about unsaved
        changes like Open does, and what the file has that the import cannot carry
        is written to the log.
        """
        from opensees_studio.services.ifc_import import IfcImportError, import_ifc, inspect_ifc
        from opensees_studio.views.dialogs.ifc_import import IfcImportDialog

        if not self._confirm_discard("Importing an IFC file"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self._window, "Import IFC", "", "IFC (*.ifc *.IFC *.ifczip *.ifcZIP);;All files (*)"
        )
        if not path:
            return
        try:
            with perf.span("ui.inspect_ifc"):
                inventory = inspect_ifc(path)
        except IfcImportError as exc:
            QMessageBox.critical(self._window, "Import IFC failed", str(exc))
            return
        dialog = IfcImportDialog(inventory, parent=self._window)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            options = dialog.options()
        finally:
            dialog.deleteLater()
        try:
            with perf.span("ui.import_ifc"):
                imported = import_ifc(path, options)
        except IfcImportError as exc:
            QMessageBox.critical(self._window, "Import IFC failed", str(exc))
            return
        self._vm.adopt(imported.project)
        self._apply_view_settings()
        self._shell.log(f"Imported {Path(path).name}: {imported.summary()}")
        for note in imported.notes:
            self._shell.log(note)
        report = check_model(imported.project)
        if not report.is_clean:
            self._shell.log(f"{report.summary()} See Analyze → Check Model.")

    def tcl(self) -> None:
        """File → Import → OpenSees Tcl Script: a ``.tcl`` file as a new project.

        Tcl has no unit metadata, so the dialog asks which system the numbers
        are in. The whole model is replaced, so this asks about unsaved changes
        like Open does; what the file has and the import cannot carry is logged.
        """
        if not self._confirm_discard("Importing an OpenSees Tcl script"):
            return
        project = self._vm.project
        default_units = project.meta.units if project is not None else UnitSystem.SI_M_N
        dialog = TclImportDialog(parent=self._window, default_units=default_units)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        imported = dialog.imported()
        if imported is None:
            return
        self._vm.adopt(imported.project)
        self._apply_view_settings()
        source = dialog.source()
        self._shell.log(
            f"Imported {source.name if source else 'the Tcl script'} "
            f"({imported.source_units} → {imported.project.meta.units.value}): "
            f"{imported.summary()}"
        )
        for note in imported.notes:
            self._shell.log(note)
