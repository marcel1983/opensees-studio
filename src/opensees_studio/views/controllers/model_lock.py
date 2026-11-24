"""The model lock: results make an edit ask first."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox, QToolButton

from opensees_studio.core.combinations import model_fingerprint
from opensees_studio.viewmodels.results_session import ResultsSession
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.i18n import tr


class ModelLockController(QObject):
    """Options → Lock Model and the padlock of the status bar.

    The model locks itself when results arrive (:attr:`after_analysis`), so an
    edit asks before it makes them stale. What the lock protects is the
    fingerprint of the model, not the project: after every push, undo and redo
    (:meth:`on_undo_index_changed`, which the window connects to the undo
    stack) the fingerprint is compared with the locked one, and a change the
    user refuses to unlock for is taken back. Combinations, design settings
    and display choices are not in the fingerprint and are never asked about.

    ``results`` is the window's results session, ``drop_results`` forgets it
    and returns to the model view (unlocking discards the results), and
    ``action`` is the window's ``action(id)``, to tick Lock Model.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        results: ResultsSession,
        drop_results: Callable[[], None],
        action: Callable[[str], QAction],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._results = results
        self._drop_results = drop_results
        self._action = action
        #: True while an edit of the model has to ask first.
        self.locked = False
        #: Lock the model when results arrive. Tests of other features switch it off.
        self.after_analysis = True
        self._fingerprint: str | None = None  # the model the lock protects
        self._index = 0  # the undo position the lock was last seen at
        self._reverting = False
        #: The padlock, where SAP2000 users look for it (the window puts it in the status bar).
        self.button = QToolButton()
        self.button.setCheckable(True)
        self.button.setAutoRaise(True)
        self.button.setText(tr("Unlocked"))

    def set_locked(self, locked: bool) -> None:
        """Lock or unlock, remembering the model the lock protects."""
        project = self._vm.project
        self.locked = bool(locked and project is not None)
        self._fingerprint = (
            model_fingerprint(project) if self.locked and project is not None else None
        )
        self._index = self._vm.undo_stack.index()
        self._action("options.lock_model").setChecked(self.locked)
        self.button.setChecked(self.locked)
        self.button.setText(tr("Locked") if self.locked else tr("Unlocked"))

    def lock_for_results(self) -> None:
        """Results arrived: from here on an edit would make them stale."""
        if self.after_analysis and not self.locked:
            self.set_locked(True)
            self._shell.log(
                "Model locked: it has analysis results (Options → Lock Model unlocks it)."
            )

    def confirm_unlock(self) -> bool:
        """Ask before the lock goes; with results, say that they go with it."""
        if self._results.has_any(self._vm.project):
            text = (
                "The model is locked because it has analysis results.\n\n"
                "Unlock it and discard the results of this session? The results "
                "database is kept."
            )
        else:
            text = "The model is locked. Unlock it to change it?"
        answer = QMessageBox.question(
            self._window,
            "Unlock Model",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def unlock(self) -> None:
        """Unlock; results in memory belonged to the locked model and go with it."""
        had_results = self._results.has_any(self._vm.project)
        self.set_locked(False)
        if had_results:
            self._drop_results()
            self._shell.log("Model unlocked: the results of this session were discarded.")
        else:
            self._shell.log("Model unlocked.")
        self._shell.refresh_actions()

    def toggle(self, checked: bool) -> None:
        """Options → Lock Model, and the padlock in the status bar."""
        if checked:
            self.set_locked(True)
            self._shell.log("Model locked.")
        elif self.confirm_unlock():
            self.unlock()
        else:
            self._action("options.lock_model").setChecked(True)
            self.button.setChecked(True)

    def on_undo_index_changed(self, index: int) -> None:
        """An edit, an undo or a redo happened: a locked model asks first.

        Only a change of the model the results depend on counts (its
        fingerprint): combinations, design settings and display choices are
        free. Refused, the change is taken back.
        """
        project = self._vm.project
        if not self.locked or self._reverting or project is None:
            self._index = index
            return
        if model_fingerprint(project) == self._fingerprint:
            self._index = index
            return
        if self.confirm_unlock():
            self.unlock()
            return
        stack = self._vm.undo_stack
        self._reverting = True
        try:
            if index < self._index:
                stack.redo()
            else:
                stack.undo()
        finally:
            self._reverting = False
        self._index = stack.index()
        self._window.statusBar().showMessage(
            tr("The model is locked: the change was not made."), 6000
        )
