"""The Analyze menu: the cases, the checks before a run, the run and its failure report."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import shiboken6
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from opensees_studio.commands import MeshCommand
from opensees_studio.core.mesh import pre_run_auto_mesh
from opensees_studio.core.model_check import Finding, check_model
from opensees_studio.services.stability import StabilityReport
from opensees_studio.viewmodels import AnalysisRunner
from opensees_studio.viewmodels.results_session import ResultsSession
from opensees_studio.viewmodels.stability_checker import StabilityChecker
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    AnalysisCaseManagerDialog,
    ModelCheckDialog,
    RunAnalysisDialog,
)
from opensees_studio.views.dialogs.run_cases import RunCasesDialog


class AnalysisController(QObject):
    """Cases, Check Model, Check Model Stability, Run, Run All and Run Selected Cases.

    The cases run in a child process that ``runner`` (the window's
    ``AnalysisRunner``) drives; ``stability`` is its ``StabilityChecker``. This
    controller is what stands between a command and them: the Run dialog (one
    at a time, :attr:`run_dialog`), the frames divided and the model checked on
    the way in, and the report of a run that failed (:attr:`error_box`) or of a
    stability check (:attr:`stability_box`), which are kept so they are not
    collected while they are open. The results of a run do not come here: the
    window receives them from the runner.

    ``results`` is the window's results session (the Run dialog combines from
    its case results) and ``finished`` what the window does with the results of
    a combination that dialog evaluated. ``new_project`` lets Cases… work with
    no project open, ``select_rows`` selects what a finding of Check Model
    names, ``show_mechanism`` animates one, and ``console`` writes a failure
    report to the Console dock.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        runner: AnalysisRunner,
        stability: StabilityChecker,
        results: ResultsSession,
        finished: Callable[[object], None],
        new_project: Callable[[], None],
        select_rows: Callable[[Sequence[int], Sequence[int]], None],
        show_mechanism: Callable[[Finding], None],
        console: Callable[[str], None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._runner = runner
        self._stability = stability
        self._results = results
        self._finished = finished
        self._new_project = new_project
        self._select_rows = select_rows
        self._show_mechanism = show_mechanism
        self._console = console
        #: The Run dialog while one is open.
        self.run_dialog: RunAnalysisDialog | None = None
        #: The report of the last run that failed, until it is closed.
        self.error_box: QMessageBox | None = None
        #: The answer of the last stability check.
        self.stability_box: QMessageBox | None = None

    def case_manager(self) -> None:
        if self._vm.project is None:
            self._new_project()
        AnalysisCaseManagerDialog(self._vm, self._window).exec()

    def check_model(self) -> None:
        """Analyze → Check Model: loose nodes, unconnected elements, mechanisms."""
        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Check Model", "Open or create a project first.")
            return
        report = check_model(project)
        dlg = ModelCheckDialog(
            project, report=report, on_select=self._select_rows, parent=self._window
        )
        try:
            dlg.exec()
            mechanism = dlg.mechanism_to_show()
        finally:
            dlg.deleteLater()
        self._shell.log(report.summary())
        if mechanism is not None:
            self._show_mechanism(mechanism)

    def _review_model_before_run(self) -> bool:
        """Check the model on the way into Run; ``False`` means the run was called off.

        Errors stop at a dialog that offers *Run anyway* (the check is a linear,
        small-displacement test, so the person may know better). Warnings are
        written to the console and do not interrupt: a modeller who has seen
        "two separate parts" once does not want to click through it on every run.
        """
        project = self._vm.project
        if project is None:
            return True
        report = check_model(project)
        if report.has_errors:
            dlg = ModelCheckDialog(
                project,
                report=report,
                pre_run=True,
                on_select=self._select_rows,
                parent=self._window,
            )
            try:
                proceed = dlg.exec() == QDialog.DialogCode.Accepted
                mechanism = dlg.mechanism_to_show()
            finally:
                dlg.deleteLater()
            self._shell.log(
                report.summary() + (" Running anyway." if proceed else " Run cancelled.")
            )
            if mechanism is not None:
                self._show_mechanism(mechanism)
            return proceed
        for finding in report.warnings:
            self._shell.log(finding.summary())
        if not report.is_complete:
            # A partial check is not a pass: say what was left out.
            for finding in report.infos:
                self._shell.log(finding.summary())
            self._shell.log(report.summary())
        return True

    def check_stability(self) -> None:
        """Analyze → Check Model Stability: look for mechanisms before solving anything."""
        project = self._vm.project
        if project is None:
            return
        if not project.nodes:
            QMessageBox.information(
                self._window, "Check Model Stability", "The model has no joints yet."
            )
            return
        self._stability.check(project, self._vm.path)

    def on_stability_progress(self, phase: str, message: str) -> None:
        """Show the coarse stability phase in the status bar and console."""
        self._shell.log(f"Stability [{phase}]: {message}")

    def on_stability_report(self, report: StabilityReport) -> None:
        summary = report.summary()
        self._shell.log(summary)
        if report.nodes:
            # Show where the mechanisms are: their joints become the selection.
            self._shell.canvas().selection.set_selection(set(report.nodes), set())
            self._shell.refresh_actions()
        box = QMessageBox(self._window)
        box.setWindowTitle("Check Model Stability")
        box.setIcon(QMessageBox.Icon.Information if report.stable else QMessageBox.Icon.Warning)
        if report.completion != "complete":
            headline = "The stability check is incomplete."
        elif report.classification == "no_free_equations":
            headline = "The model is fully restrained."
        elif report.stable:
            headline = "The model is statically stable."
        else:
            headline = "The model is not statically stable."
        box.setText(headline)
        box.setInformativeText(
            summary + ("\n\nThe joints that move are selected." if report.nodes else "")
        )
        box.open()
        self.stability_box = box

    def on_stability_failed(self, message: str) -> None:
        self._shell.log(message)
        box = QMessageBox(self._window)
        box.setWindowTitle("Check Model Stability")
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText("The stability check could not finish.")
        box.setInformativeText(message)
        box.open()
        self.stability_box = box

    def run(self) -> None:
        if self._vm.project is None:
            QMessageBox.information(self._window, "Run Analysis", "Open or create a project first.")
            return
        if not self._vm.project.analyses:
            QMessageBox.information(
                self._window,
                "Run Analysis",
                "No analysis cases defined. Open Analyze → Cases…",
            )
            return
        open_dialog = self.run_dialog
        if open_dialog is not None and open_dialog.isVisible():
            # One Run dialog at a time: F5 again brings it to the front.
            open_dialog.raise_()
            open_dialog.activateWindow()
            return
        self.auto_mesh_before_run()
        if not self._review_model_before_run():
            return
        dlg = RunAnalysisDialog(
            self._vm, self._runner, self._window, case_results=self._results.cases
        )
        combination_finished = getattr(dlg, "combinationFinished", None)
        if combination_finished is not None:
            combination_finished.connect(self._finished)
        self.run_dialog = dlg
        # Modeless: the model, the viewport and the results stay usable while
        # the case runs and after, next to the log.
        dlg.finished.connect(lambda _code, d=dlg: self._on_run_dialog_closed(d))
        dlg.show()

    def _on_run_dialog_closed(self, dlg: QWidget) -> None:
        if self.run_dialog is dlg:
            self.run_dialog = None
        self.keep_failure_report_alive(dlg)
        # The dialog connects seven signals of the long-lived runner and is
        # parented to this window, so without this it stays alive after it
        # closes and every later run keeps appending to its log widget.
        dlg.deleteLater()

    def run_all(self) -> None:
        """Analyze → Run All Cases: every case, in one child process."""
        project = self._vm.project
        if project is None or self._runner.is_running:
            return
        if not project.analyses:
            self._shell.log("No analysis cases. Define one in Analyze → Cases…")
            return
        self._shell.log(f"Running all {len(project.analyses)} case(s).")
        self._start_batch(list(project.analyses))

    def run_selected(self) -> None:
        """Analyze → Run Selected Cases: tick the cases, then run them together."""
        project = self._vm.project
        if project is None or self._runner.is_running:
            return
        if not project.analyses:
            self._shell.log("No analysis cases. Define one in Analyze → Cases…")
            return
        dialog = RunCasesDialog(project, self._window)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            chosen = set(dialog.selected_case_ids())
        finally:
            dialog.deleteLater()
        cases = [case for case in project.analyses if case.id in chosen]
        if not cases:
            self._shell.log("No case selected.")
            return
        self._shell.log(f"Running {len(cases)} selected case(s).")
        self._start_batch(cases)

    def _start_batch(self, cases: list[Any]) -> None:
        """Hand a set of cases to the runner in one child process."""
        project = self._vm.project
        if project is None:
            return
        self.auto_mesh_before_run()
        try:
            self._runner.run_cases(project, cases, project_path=self._vm.path)
        except Exception as exc:
            self._shell.log(f"Could not start: {exc}")

    def auto_mesh_before_run(self) -> None:
        """Divide the frames that another frame ends on or crosses, in one undo step.

        So no member lying on another is left unconnected. Members with their own
        Auto Mesh off, and every member while Analyze → Auto-mesh Frames Before
        Run is off, are left as drawn.
        """
        project = self._vm.project
        if project is None:
            return
        plan = pre_run_auto_mesh(project)
        if plan.is_empty:
            return
        try:
            self._vm.apply_command(MeshCommand(self._vm, plan, text="Auto-mesh frames"))
        except Exception as exc:
            self._shell.log(f"Auto-mesh before run failed: {exc}")
            return
        self._shell.log(f"Auto-mesh before run: {plan.summary()}")

    def toggle_auto_mesh_frames(self, checked: bool) -> None:
        """Analyze → Auto-mesh Frames Before Run (saved with the project)."""
        from opensees_studio.commands import SetAutoMeshFramesCommand

        project = self._vm.project
        if project is None or project.auto_mesh_frames == checked:
            return
        self._vm.apply_command(SetAutoMeshFramesCommand(self._vm, checked))

    def on_failed(self, report: str) -> None:
        """Show the failure report (exit code, last error, stderr tail) without blocking."""
        self._console(report)
        code = self._runner.last_exit_code
        headline = "Analysis failed."
        if code is not None:
            headline = f"Analysis process exited with code {code}."
        # A child of the modal Run dialog, so it is not blocked and opens in front of it.
        box = QMessageBox(self._failure_parent())
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Analysis failed")
        box.setText(headline)
        box.setInformativeText(
            "The application and your model are unaffected. "
            "The pre-run snapshot is kept for recovery. Details below and in the Console dock."
        )
        box.setDetailedText(report)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.setModal(False)
        box.finished.connect(self._forget_failure_report)
        self.error_box = box
        box.show()
        box.raise_()
        box.activateWindow()
        self._shell.log(headline)

    def _failure_parent(self) -> QWidget:
        """The dialog that started the run while it is open, else the main window."""
        dlg = self.run_dialog
        if dlg is not None and dlg.isVisible():
            return dlg
        return self._window

    def keep_failure_report_alive(self, dlg: QWidget) -> None:
        """Reparent an unread failure report so it outlives the Run dialog.

        The report is created with ``WA_DeleteOnClose``, so once the user has
        closed it Qt has destroyed the C++ object while this window still holds
        the Python wrapper. ``box.parent()`` then raises ``RuntimeError``, and
        an exception raised here — inside the ``finally`` of a Qt slot — used to
        take the whole application down with it. Hence the validity check, and
        the reference being dropped when the box is gone.
        """
        box = self.error_box
        if box is None:
            return
        if not shiboken6.isValid(box):
            self.error_box = None
            return
        if box.parent() is dlg:
            box.setParent(self._window, box.windowFlags())
            box.show()

    def _forget_failure_report(self, _result: int = 0) -> None:
        """The report is closed (and, with ``WA_DeleteOnClose``, about to be deleted)."""
        self.error_box = None
