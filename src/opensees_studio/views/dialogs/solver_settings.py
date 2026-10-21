"""Options → Solver: which engine solves, and where OpenSeesPy is installed.

OpenSeesPy is a separate program with its own license; the application may be
installed without it. This dialog shows whether an engine is available and
lets the user point to one: the application's own environment, another Python
of the same version that has ``openseespy``, or a folder holding the package.
The logic is in :mod:`opensees_studio.services.engines`.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.core.help import TOPIC_PROPERTY
from opensees_studio.services.engines import (
    OPENSEES_PY,
    EngineError,
    SolverSettings,
    current_status,
    inspect_python,
)
from opensees_studio.views.screen_fit import FittedDialog, MessageArea

LICENSE_NOTE = (
    "<i>OpenSeesPy is a separate program with its own license: free for research, "
    "education and internal use; commercial redistribution needs a license from its "
    "authors. OpenSees Studio does not include it — check that your use fits its "
    "terms.</i>"
)

OWN, PYTHON, FOLDER = "own", "python", "folder"


class SolverSettingsDialog(FittedDialog):
    """Choose where OpenSeesPy comes from and see whether it is usable."""

    def __init__(self, settings: SolverSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Solver")
        self.setProperty(TOPIC_PROPERTY, "options.solver")
        self._settings = settings
        self._build_ui()
        if settings.python:
            self._python_radio.setChecked(True)
            self._python_edit.setText(settings.python)
        elif settings.package_dir:
            self._folder_radio.setChecked(True)
            self._folder_edit.setText(settings.package_dir)
        else:
            self._own_radio.setChecked(True)
        self._refresh()

    # ── ui ──────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "OpenSees Studio models; an <b>engine</b> solves. The engine today is "
                "<b>OpenSeesPy 3.8</b>. Without it you can still model, export and "
                "report, but not run an analysis."
            )
        )
        form = QFormLayout()
        self._own_radio = QRadioButton("OpenSeesPy installed with OpenSees Studio")
        self._python_radio = QRadioButton(
            f"OpenSeesPy of another Python {sys.version_info[0]}.{sys.version_info[1]}"
        )
        self._folder_radio = QRadioButton("A folder that contains the openseespy package")
        self._group = QButtonGroup(self)
        for button in (self._own_radio, self._python_radio, self._folder_radio):
            self._group.addButton(button)
            button.toggled.connect(self._refresh)

        self._python_edit = QLineEdit()
        self._python_edit.setPlaceholderText("python executable")
        self._python_edit.editingFinished.connect(self._refresh)
        python_row = self._row(self._python_edit, self._browse_python)
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("…/site-packages")
        self._folder_edit.editingFinished.connect(self._refresh)
        folder_row = self._row(self._folder_edit, self._browse_folder)

        form.addRow(self._own_radio)
        form.addRow(self._python_radio)
        form.addRow("Interpreter:", python_row)
        form.addRow(self._folder_radio)
        form.addRow("Folder:", folder_row)
        layout.addLayout(form)

        self._status = MessageArea()
        layout.addWidget(self._status)
        note = QLabel(LICENSE_NOTE)
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._ok = buttons.button(QDialogButtonBox.StandardButton.Ok)

    def _row(self, edit: QLineEdit, browse: object) -> QWidget:
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(edit)
        button = QPushButton("Browse…")
        button.clicked.connect(browse)
        box.addWidget(button)
        return row

    def _browse_python(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Python interpreter")
        if path:
            self._python_edit.setText(path)
            self._python_radio.setChecked(True)
            self._refresh()

    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Folder with the openseespy package")
        if path:
            self._folder_edit.setText(path)
            self._folder_radio.setChecked(True)
            self._refresh()

    # ── state ───────────────────────────────────────────────────────
    def mode(self) -> str:
        if self._python_radio.isChecked():
            return PYTHON
        if self._folder_radio.isChecked():
            return FOLDER
        return OWN

    def _candidate(self) -> SolverSettings:
        """The settings the form describes; raises EngineError when they cannot be used."""
        mode = self.mode()
        if mode == PYTHON:
            executable = self._python_edit.text().strip()
            if not executable:
                raise EngineError("Choose a Python interpreter.")
            return inspect_python(executable)
        if mode == FOLDER:
            folder = self._folder_edit.text().strip()
            if not folder:
                raise EngineError("Choose a folder.")
            return SolverSettings(engine=OPENSEES_PY, package_dir=folder)
        return SolverSettings(engine=OPENSEES_PY)

    def _refresh(self, *_: object) -> None:
        self._python_edit.setEnabled(self._python_radio.isChecked())
        self._folder_edit.setEnabled(self._folder_radio.isChecked())
        try:
            self._settings = self._candidate()
        except EngineError as exc:
            self._status.show_message(str(exc), level="error")
            self._ok.setEnabled(False)
            return
        self._ok.setEnabled(True)
        status = current_status(self._settings)
        if status.available:
            self._status.show_message(
                "\n".join(filter(None, [f"Ready: {status.summary()}.", status.message]))
            )
        else:
            self._status.show_message(status.message, level="warning")

    def settings(self) -> SolverSettings:
        """What to save on OK (the last settings the form could describe)."""
        return self._settings
