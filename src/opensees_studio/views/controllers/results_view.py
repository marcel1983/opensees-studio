"""The results on screen: which case the window shows, its panels and its reactions."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QComboBox, QInputDialog, QLabel, QMessageBox, QToolButton

from opensees_studio.services.batch import StoredResults, stored_results
from opensees_studio.services.combination import MissingCaseResultsError
from opensees_studio.services.result_store import load_results
from opensees_studio.services.results import (
    CombinationResults,
    ResponseSpectrumResults,
    TransientResults,
)
from opensees_studio.services.results_db import database_path, delete_all_results, record_results
from opensees_studio.viewmodels.results_session import ResultsSession, case_names
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.reactions import ReactionsDialog
from opensees_studio.views.docks import ReactionsPanel, ResultsPanel


class ResultsViewController(QObject):
    """What a run leaves behind and which of it the window is showing.

    It receives the results of a run (:meth:`on_case_finished` for each case,
    :meth:`on_finished` for the one to show), keeps them in the window's
    :class:`ResultsSession`, and points everything at one of them
    (:meth:`show`): the Results panel, the reactions (panel, dialog and the
    overlay of the viewport), the Case list and step arrows of the View
    toolbar and the viewport's caption. Display → Show Results Of
    (:meth:`pick`, :meth:`show_results_of`), the results a batch stored
    (:meth:`offer_stored`) and Analyze → Delete All Results
    (:meth:`delete_all`) are here too.

    It owns the widgets it fills; the window only places them: :attr:`panel`
    and :attr:`reactions_panel` go into docks, :attr:`case_combo`,
    :attr:`step_back`, :attr:`step_forward` and :attr:`step_label` into the
    View toolbar.

    ``results`` is the window's results session. ``lock`` locks the model for
    its results and ``unlock`` releases it; ``set_caption`` writes the
    viewport's caption and ``back_to_model`` closes the post-processing view;
    ``show_reactions_dock`` raises the dock the window put the reactions panel
    in; ``action`` is the window's ``action(id)``.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        results: ResultsSession,
        lock: Callable[[], None],
        unlock: Callable[[], None],
        set_caption: Callable[[str], None],
        back_to_model: Callable[[], None],
        show_reactions_dock: Callable[[], None],
        action: Callable[[str], QAction],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._results = results
        self._lock = lock
        self._unlock = unlock
        self._set_caption = set_caption
        self._back_to_model = back_to_model
        self._show_reactions_dock = show_reactions_dock
        self._action = action
        #: The tables and curves of the case on screen (the Results dock).
        self.panel = ResultsPanel()
        #: The reactions of the case on screen (the Reactions dock).
        self.reactions_panel = ReactionsPanel()
        #: Which results case the viewport represents: the layers (deformed
        #: shape, diagrams, reactions) follow it.
        self.case_combo = QComboBox()
        self.case_combo.setMinimumWidth(190)
        self.case_combo.setToolTip(
            "Results case shown in the viewport. Deformed shape, force diagram, "
            "contours and reactions all read this case."
        )
        self.case_combo.currentIndexChanged.connect(self._on_case_changed)
        self.step_back = QToolButton()
        self.step_back.setText("\u25c0")
        self.step_back.setToolTip("Previous step of this case")
        self.step_back.setEnabled(False)
        self.step_back.clicked.connect(lambda: self.shift_step(-1))
        self.step_forward = QToolButton()
        self.step_forward.setText("\u25b6")
        self.step_forward.setToolTip("Next step of this case")
        self.step_forward.setEnabled(False)
        self.step_forward.clicked.connect(lambda: self.shift_step(1))
        self.step_label = QLabel("")
        self._step_index = 0
        #: Re-draws the step-based layer at a step. Only a layer that knows how
        #: sets it; until one does, the arrows stay disabled.
        self.step_apply: Callable[[int], None] | None = None

    def on_finished(self, results) -> None:  # type: ignore[no-untyped-def]
        """A run ended, or a case or combination was picked: show it and say so."""
        self.show(results)
        self._shell.log(
            f"Analysis complete: {self._results.caption_for(self._vm.project, results)}."
        )
        if isinstance(results, TransientResults) and results.early_stop:
            self._shell.log(f"Warning: transient run did not converge ({results.steps_summary()}).")
        if isinstance(results, ResponseSpectrumResults | CombinationResults):
            for warning in results.warnings:
                self._shell.log(f"Warning: {warning}")
        self._set_caption(self._results.caption_for(self._vm.project, results))
        self._shell.refresh_actions()

    def on_case_finished(self, results: object) -> None:
        """Keep each case result of a run for the load combinations."""
        self.keep(results)
        self._record(results)

    def keep(self, results: object) -> None:
        """Keep one case's results in the session; results lock the model."""
        self._results.keep(self._vm.project, results)
        self._lock()

    def _record(self, results: object) -> None:
        """Append this case's results to the project's queryable database.

        A failure here must never fail the analysis: the run already happened,
        so the database is reported as a warning and the results stay in memory.
        """
        try:
            run_id = record_results(results, project_path=self._vm.path, project=self._vm.project)
        except Exception as exc:
            self._shell.log(f"Warning: the results database was not written: {exc}")
            return
        if run_id is not None:
            self._shell.log(f"Results recorded in {database_path(self._vm.path)} (run {run_id}).")

    def offer_stored(self) -> None:
        """Offer the results a batch stored for this model, so nothing has to run again."""
        stored = stored_results(self._vm.path, self._vm.project)
        if stored is None:
            return
        answer = QMessageBox.question(
            self._window,
            "Stored results",
            f"Results of {len(stored.entries)} case(s) from a batch run "
            f"({stored.finished_at or 'time unknown'}) are stored for this model, and the "
            "model has not changed since.\n\nLoad them to view without running again?\n\n"
            f"Folder: {stored.out_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.load_stored(stored)

    def load_stored(self, stored: StoredResults) -> int:
        """Load every case of ``stored`` as if it had just run; show the last one.

        They are already in the results database, so nothing is recorded again.
        Returns how many cases loaded.
        """
        loaded = []
        for entry in stored.entries:
            try:
                results = load_results(entry, stored.out_dir)
            except Exception as exc:
                self._shell.log(
                    f"Warning: stored results of case {entry.get('case_id')} unreadable: {exc}"
                )
                continue
            self.keep(results)
            loaded.append(results)
        if loaded:
            self.show(loaded[-1])
            self._shell.log(f"Loaded {len(loaded)} stored case result(s) from {stored.out_dir}.")
        return len(loaded)

    def show(self, results: object) -> None:
        """Point the whole window at one results case."""
        self._results.latest = results
        self._lock()
        self.panel.show_results(results, self._vm.project)
        self.refresh_reactions()
        self.refresh_case_combo()
        self._set_caption(self._results.caption_for(self._vm.project, results))
        self._shell.refresh_actions()
        self._refresh_step_buttons()

    def show_results_of(self, key: str) -> bool:
        """Make ``case:<id>`` or ``combination:<id>`` the results Display shows.

        A combination is combined from the current case results; when some of its
        cases have none, the message says to run it from Analyze → Run.
        """
        results = self.for_key(key)
        if results is None:
            return False
        self._back_to_model()
        self.on_finished(results)
        return True

    def for_key(self, key: str) -> object | None:
        """Resolve a ``case:<id>`` / ``combination:<id>`` key, or explain why not."""
        project = self._vm.project
        if project is None:
            return None
        kind, _, raw_id = key.partition(":")
        try:
            ref_id = int(raw_id)
        except ValueError:
            return None
        if kind == "case":
            results = self._results.cases.current(project).get(ref_id)
            if results is None:
                self._shell.log(f"Case {ref_id} has no current results: run it first.")
                return None
            return cast(object, results)
        try:
            return cast(object, self._results.cases.combine(project, ref_id))
        except (MissingCaseResultsError, ValueError, KeyError) as exc:
            QMessageBox.information(
                self._window,
                "Show Results Of",
                f"{exc}\n\nAnalyze → Run, then pick the combination: it runs only the "
                "cases without current results.",
            )
            return None

    def pick(self) -> None:
        """Display → Show Results Of…: switch between stored case and combination results."""
        choices = self._results.choices(self._vm.project)
        if not choices:
            QMessageBox.information(
                self._window,
                "Show Results Of",
                "No results yet: run a case (Analyze → Run) or define a load combination.",
            )
            return
        label, ok = QInputDialog.getItem(
            self._window, "Show Results Of", "Results:", [c[0] for c in choices], 0, False
        )
        if ok:
            self.show_results_of(dict(choices)[label])

    def refresh_case_combo(self) -> None:
        """List the cases that still hold results for this model, newest order."""
        project = self._vm.project
        entries = self._results.cases.current(project) if project is not None else {}
        current = getattr(self._results.latest, "case_id", None)
        names = case_names(self._vm.project)
        self.case_combo.blockSignals(True)
        self.case_combo.clear()
        for case_id, results in sorted(entries.items()):
            kind = type(results).__name__.removesuffix("Results")
            name = names.get(case_id) or getattr(results, "case_name", None) or f"Case {case_id}"
            self.case_combo.addItem(f"{name} · {kind}", case_id)
        if current is not None:
            index = self.case_combo.findData(current)
            if index >= 0:
                self.case_combo.setCurrentIndex(index)
        self.case_combo.blockSignals(False)
        self.case_combo.setEnabled(bool(entries))
        self._refresh_step_buttons()

    def _on_case_changed(self, index: int) -> None:
        """Show the chosen case; the layers read it from `results.latest`."""
        case_id = self.case_combo.itemData(index)
        project = self._vm.project
        if case_id is None or project is None:
            return
        results = self._results.cases.current(project).get(case_id)
        if results is not None and results is not self._results.latest:
            self.show(results)

    def _refresh_step_buttons(self) -> None:
        """Enable the step arrows only when the shown case has more than one."""
        steps = self._results.steps()
        # Only a layer that knows how to redraw itself at another step registers
        # an applier; until one does, the arrows must not pretend to work.
        steppable = steps > 1 and self.step_apply is not None
        self._step_index = min(self._step_index, max(steps - 1, 0))
        self.step_back.setEnabled(steppable)
        self.step_forward.setEnabled(steppable)
        if steps > 1:
            self.step_label.setText(f"Step {self._step_index + 1}/{steps}")
        else:
            self.step_label.setText("")

    def shift_step(self, delta: int) -> None:
        """The step arrows: one step back or forward, within the shown case."""
        steps = self._results.steps()
        if steps <= 1:
            return
        target = min(max(self._step_index + delta, 0), steps - 1)
        if target == self._step_index:
            return
        self._step_index = target
        self._refresh_step_buttons()
        self._apply_step()

    def _apply_step(self) -> None:
        """Re-draw the step-based layer at the current step, if one is showing."""
        if self.step_apply is not None:
            self.step_apply(self._step_index)

    def refresh_reactions(self) -> None:
        """Keep the table and the overlay on the same case, and enable the actions."""
        rows = self._results.reaction_rows(self._vm.project)
        self.reactions_panel.set_rows(rows)
        overlay = self._action("display.show_reactions")
        self._shell.canvas().set_reactions(rows, show=overlay.isChecked())
        enabled = bool(rows)
        overlay.setEnabled(enabled)
        self._action("display.reactions_table").setEnabled(enabled)
        self._action("display.reactions_dialog").setEnabled(enabled)
        if not enabled and overlay.isChecked():
            overlay.setChecked(False)
            self.show_reactions(False)  # unticked here, not by the user: nobody else is told

    def show_reactions(self, checked: bool) -> None:
        """Display → Show Reactions: the arrows and values at the supports."""
        self._shell.canvas().set_reactions(
            self._results.reaction_rows(self._vm.project), show=checked
        )

    def reactions_dialog(self) -> None:
        """Display → Reactions…: the table of the case on screen, in a dialog."""
        dialog = ReactionsDialog(self._results.reaction_rows(self._vm.project), self._window)
        dialog.exec()

    def reactions_table(self) -> None:
        """Display → Reactions Table: bring the Reactions panel to the front."""
        self._show_reactions_dock()

    def delete_all(self) -> None:
        """Analyze → Delete All Results: forget every stored result."""
        db_path = database_path(self._vm.path)
        answer = QMessageBox.question(
            self._window,
            "Delete All Results",
            "Delete every stored result?\n\n"
            "  • the results of this session\n"
            f"  • {db_path}\n\n"
            "The model, its analysis cases and any other project's database are "
            "not touched.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.drop()
        self._unlock()
        removed = delete_all_results(db_path)
        self._shell.log(
            "All results deleted."
            if removed
            else "All results deleted (the database was already empty)."
        )
        self._shell.refresh_actions()

    def drop(self) -> None:
        """Forget the results held in memory and return to the model view."""
        self._results.clear()
        self.refresh_reactions()
        self.refresh_case_combo()
        self._back_to_model()
        self.panel.show_results(None, self._vm.project)
