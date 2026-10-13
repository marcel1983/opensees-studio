"""Add Uniform Excitation pattern dialog.

Constructs a :class:`UniformExcitationPattern` from a direction (DOF)
picker, an accel TimeSeries picker (typically a PathTimeSeries), and
an optional scale factor. Used for ground-motion transients — node
masses + this pattern + a Newmark TransientCase reproduces the
OpenSees ``pattern UniformExcitation`` / ``analyze N dt`` recipe.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.core import Project, UniformExcitationPattern
from opensees_studio.core.plane import VERTICAL_AXIS, dof_indices, dof_labels
from opensees_studio.views.float_field import FloatField
from opensees_studio.views.screen_fit import FittedDialog


def _direction_choices(ndm: int, ndf: int) -> list[tuple[int, str]]:
    """``(OpenSees DOF, label)`` of every DOF of the model; Z is the vertical one."""
    out: list[tuple[int, str]] = []
    for dof, (slot, label) in enumerate(
        zip(dof_indices(ndm, ndf), dof_labels(ndm, ndf), strict=True), start=1
    ):
        note = " (vertical)" if slot == VERTICAL_AXIS else " (horizontal)" if slot < 3 else ""
        out.append((dof, f"{dof} — {label}{note}"))
    return out


class UniformExcitationDialog(FittedDialog):
    """Pick direction + accel series for a UniformExcitation pattern."""

    def __init__(
        self,
        project: Project,
        next_pattern_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Uniform Excitation")
        self._project = project
        self._next_id = next_pattern_id
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "<b>UniformExcitation</b> — apply a base ground motion "
                "to every free node in the chosen DOF direction."
            )
        )

        form = QFormLayout()
        self._name_edit = QLineEdit("GroundMotion")
        form.addRow("Name:", self._name_edit)

        self._dir_cb = QComboBox()
        for dof, label in _direction_choices(self._project.ndm, self._project.ndf):
            self._dir_cb.addItem(label, dof)
        form.addRow("Direction:", self._dir_cb)

        # Accel series picker — only shows existing TimeSeries ids
        # (user must have added a PathTimeSeries via the other dialog
        # before opening this one).
        self._accel_cb = QComboBox()
        for ts in self._project.time_series:
            label = f"#{ts.id}  {ts.name or ts.type}  [{ts.type}]"
            self._accel_cb.addItem(label, ts.id)
        if self._project.time_series:
            form.addRow("Accel series:", self._accel_cb)
        else:
            self._accel_cb.addItem("(none — add a Path series first)", None)
            self._accel_cb.setEnabled(False)
            form.addRow("Accel series:", self._accel_cb)

        self._factor_spin = FloatField()
        self._factor_spin.setRange(-1e12, 1e12)
        self._factor_spin.setSingleStep(0.1)
        self._factor_spin.setValue(1.0)
        self._factor_spin.setToolTip("Extra scale applied on top of the TimeSeries' own factor.")
        form.addRow("Factor:", self._factor_spin)

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def pattern(self) -> UniformExcitationPattern:
        accel_id = self._accel_cb.currentData()
        if accel_id is None:
            raise ValueError("No accel time series selected.")
        return UniformExcitationPattern(
            id=self._next_id,
            name=self._name_edit.text().strip() or "GroundMotion",
            direction=int(self._dir_cb.currentData()),
            accel_series_id=int(accel_id),
            factor=self._factor_spin.value(),
        )
