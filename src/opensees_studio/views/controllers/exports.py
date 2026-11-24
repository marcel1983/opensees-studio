"""File → Export: the model and its results for another program or for a reader."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

from opensees_studio import __version__
from opensees_studio.services.opensees_script import case_label, export_script
from opensees_studio.services.steel_design import DesignReport, steel_frame_check
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import CalculationMemoryDialog
from opensees_studio.views.report_pdf import write_pdf

#: First entry of the export dialog's case list: no analysis block in the script.
EXPORT_MODEL_ONLY = "Model only"


class ExportsController(QObject):
    """What goes out of the program, each to a file the user names.

    The model as an OpenSeesPy script, as IFC and as SAP2000 text; the report
    (PDF, Word, HTML) and the calculation memory of the steel members. The
    last two read results, which the window owns: ``results`` is the results of
    the model as it is now, by case id, and ``report_results`` what the report
    includes (those, plus the one on screen). It keeps no state.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        results: Callable[[], dict[int, Any]],
        report_results: Callable[[], list[Any]],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._results = results
        self._report_results = report_results

    def script(self) -> None:
        """File → Export → OpenSees script: the model as plain OpenSeesPy.

        The script is the command sequence the runner itself emits, so it
        cannot drift from what the solver is given (see
        ``services/opensees_script.py``).
        """
        if self._vm.project is None:
            QMessageBox.information(
                self._window, "Export script", "Open or create a project first."
            )
            return
        chosen, case = self._ask_case()
        if not chosen:
            return
        default = (self._vm.path.stem if self._vm.path is not None else "model") + ".py"
        path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Export OpenSees script",
            default,
            "Python script (*.py)",
        )
        if not path:
            return
        try:
            source = export_script(
                self._vm.project, case, version=__version__, filename=Path(path).name
            )
            Path(path).write_text(source, encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self._window, "Export failed", str(exc))
            return
        self._shell.log(f"Exported OpenSees script: {path}")

    def _ask_case(self) -> tuple[bool, Any]:
        """Ask which case the script should run. ``(False, None)`` on cancel."""
        project = self._vm.project
        if project is None or not project.analyses:
            return True, None
        analyses = project.analyses
        labels = [EXPORT_MODEL_ONLY, *(case_label(c) for c in analyses)]
        choice, accepted = QInputDialog.getItem(
            self._window,
            "Export OpenSees script",
            "Include which analysis case?",
            labels,
            0,
            False,
        )
        if not accepted:
            return False, None
        if choice == EXPORT_MODEL_ONLY:
            return True, None
        return True, analyses[labels.index(choice) - 1]

    def ifc(self) -> None:
        """File → Export → IFC: the physical BIM model and the analytical model, IFC4."""
        from opensees_studio.services.ifc_export import IfcExportError, export_ifc

        if self._vm.project is None:
            QMessageBox.information(self._window, "Export IFC", "Open or create a project first.")
            return
        default = (self._vm.path.stem if self._vm.path is not None else "model") + ".ifc"
        path, _ = QFileDialog.getSaveFileName(self._window, "Export IFC", default, "IFC (*.ifc)")
        if not path:
            return
        if not path.lower().endswith(".ifc"):
            path += ".ifc"
        try:
            report = export_ifc(self._vm.project, path)
        except (IfcExportError, OSError, ValueError) as exc:
            QMessageBox.critical(self._window, "Export IFC failed", str(exc))
            return
        self._shell.log(report.summary())
        if report.notes:
            QMessageBox.information(self._window, "Export IFC", report.summary())

    def s2k(self) -> None:
        """File → Export → SAP2000 Text: the frame model as SAP2000 text tables."""
        from opensees_studio.services.sap2000_text import Sap2000TextError, export_s2k

        if self._vm.project is None:
            QMessageBox.information(
                self._window, "Export SAP2000 Text", "Open or create a project first."
            )
            return
        default = (self._vm.path.stem if self._vm.path is not None else "model") + ".s2k"
        path, _ = QFileDialog.getSaveFileName(
            self._window, "Export SAP2000 Text", default, "SAP2000 text (*.s2k *.$2k)"
        )
        if not path:
            return
        if not path.lower().endswith((".s2k", ".$2k")):
            path += ".s2k"
        try:
            report = export_s2k(self._vm.project, path)
        except Sap2000TextError as exc:
            QMessageBox.critical(self._window, "Export SAP2000 Text failed", str(exc))
            return
        self._shell.log(f"Exported {Path(path).name}: {report.summary()}")
        if report.skipped:
            QMessageBox.information(self._window, "Export SAP2000 Text", report.summary())

    def report(self) -> None:
        """File → Export → Report: model, loads, cases and current results (PDF, Word, HTML)."""
        from opensees_studio.services.report import build_report, report_sections, running_text
        from opensees_studio.views.dialogs.report_options import (
            ReportOptionsDialog,
            load_options,
            save_options,
        )

        project = self._vm.project
        if project is None:
            QMessageBox.information(
                self._window, "Export report", "Open or create a project first."
            )
            return
        results = self._report_results()
        dialog = ReportOptionsDialog(
            report_sections(project, results), load_options(), self._window
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        options = dialog.options()
        save_options(options)
        default = (self._vm.path.stem if self._vm.path is not None else "model") + "-report.pdf"
        path, chosen = QFileDialog.getSaveFileName(
            self._window,
            "Export report",
            default,
            "PDF (*.pdf);;Word document (*.docx);;HTML page (*.html)",
        )
        if not path:
            return
        lower = path.lower()
        if lower.endswith((".html", ".htm")):
            fmt = "html"
        elif lower.endswith(".docx"):
            fmt = "docx"
        elif lower.endswith(".pdf"):
            fmt = "pdf"
        else:
            fmt = "html" if "HTML" in chosen else "docx" if "Word" in chosen else "pdf"
            path += {"html": ".html", "docx": ".docx", "pdf": ".pdf"}[fmt]
        page = build_report(project, results, options=options, paged=fmt == "pdf")
        running = None
        if options.header_footer:
            running = running_text(
                project, skip_first_page=options.cover, language=options.language
            )
        try:
            if fmt == "html":
                Path(path).write_text(page, encoding="utf-8")
            elif fmt == "docx":
                from opensees_studio.services.report_docx import docx_bytes
                from opensees_studio.views.report_pdf import svg_to_png

                Path(path).write_bytes(
                    docx_bytes(
                        page,
                        running=running,
                        keep_tables_together=options.keep_tables_together,
                        rasterize=svg_to_png,
                        language=options.language,
                        title=project.meta.name,
                    )
                )
            else:
                write_pdf(
                    page,
                    path,
                    running=running,
                    keep_tables_together=options.keep_tables_together,
                )
        except OSError as exc:
            QMessageBox.critical(self._window, "Export report failed", str(exc))
            return
        self._shell.log(f"Report written: {path} ({len(results)} result set(s)).")

    def calc_memory(self) -> None:
        """File → Export → Calculation Memory: member sheets in the chosen format."""
        from opensees_studio.services.calc_memory import (
            Language,
            build_member_memory,
            odt_bytes,
        )

        project = self._vm.project
        if project is None:
            QMessageBox.information(
                self._window, "Calculation memory", "Open or create a project first."
            )
            return
        dialog = CalculationMemoryDialog(self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        results = self._results()
        report = steel_frame_check(project, results, project.design)
        members = report.members
        chosen = dialog.member_filter()
        if chosen == "selected":
            ids = set(self._shell.canvas().selection.elements)
            members = [m for m in members if m.element_id in ids]
        elif chosen == "ng":
            members = [m for m in members if m.status == "NG"]
        if not members:
            QMessageBox.information(
                self._window, "Calculation memory", "No member matches the chosen filter."
            )
            return
        filtered = DesignReport(
            members=members,
            joints=report.joints,
            connections=report.connections,
            load_sets=report.load_sets,
            notes=report.notes,
        )
        fmt = dialog.format()
        extensions = {
            "html": (".html", "HTML page (*.html)"),
            "markdown": (".md", "Markdown (*.md)"),
            "latex": (".tex", "LaTeX (*.tex)"),
            "odt": (".odt", "OpenDocument text (*.odt)"),
            "pdf": (".pdf", "PDF (*.pdf)"),
        }
        suffix, file_filter = extensions[fmt]
        stem = self._vm.path.stem if self._vm.path is not None else "model"
        path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Export calculation memory",
            f"{stem}-calc-memory{suffix}",
            file_filter,
        )
        if not path:
            return
        language = cast(Language, dialog.language())
        try:
            if fmt == "odt":
                Path(path).write_bytes(odt_bytes(project, filtered, language=language))
            elif fmt == "pdf":
                page = build_member_memory(
                    project,
                    filtered,
                    language=language,
                    fmt="html",
                )
                write_pdf(page, path)
            else:
                text = build_member_memory(
                    project,
                    filtered,
                    language=language,
                    fmt=cast(Any, fmt),
                )
                Path(path).write_text(text, encoding="utf-8")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self._window, "Calculation memory failed", str(exc))
            return
        self._shell.log(f"Calculation memory written: {path} ({len(members)} member(s)).")
