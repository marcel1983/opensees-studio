"""Assign Frame Point Load dialog — a concentrated load inside selected frame elements."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.views.float_field import FloatField
from opensees_studio.views.screen_fit import FittedDialog

RELATIVE = "relative"
ABSOLUTE = "absolute"


class AssignPointElementLoadDialog(FittedDialog):
    """Modal dialog for a point load (Px, Py, Pz) at a distance along each element.

    Components are in the **element local frame** (local x / y / z axes). The
    distance is measured from end i, either as a fraction of the length
    (``RELATIVE``, 0..1) or in length units (``ABSOLUTE``).
    """

    def __init__(self, n_selected: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Frame Point Load")
        self._build_ui(n_selected)

    def _build_ui(self, n_selected: int) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Apply to <b>{n_selected}</b> selected frame element(s)."))

        form = QFormLayout()
        self._fields: dict[str, FloatField] = {}
        for label, tip in (
            ("Px", "Force along local-x (axial)"),
            ("Py", "Force along local-y (transverse, in-plane for 2D)"),
            ("Pz", "Force along local-z (out-of-plane for 2D)"),
        ):
            field = FloatField()
            field.setRange(-1e12, 1e12)
            field.setSingleStep(1.0)
            field.setValue(0.0)
            field.setToolTip(tip)
            self._fields[label] = field
            form.addRow(f"{label}:", field)

        self._mode = QComboBox()
        self._mode.addItem("Relative distance (x/L)", RELATIVE)
        self._mode.addItem("Absolute distance", ABSOLUTE)
        self._mode.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("Measured as:", self._mode)

        self._distance = FloatField()
        self._distance.setRange(0.0, 1.0)
        self._distance.setSingleStep(0.1)
        self._distance.setValue(0.5)
        self._distance.setToolTip("Distance from end i of each element")
        form.addRow("Distance from end i:", self._distance)
        layout.addLayout(form)

        layout.addWidget(
            QLabel(
                "<i>Forces are in the element's local frame. The load goes into "
                "the active Plain pattern; if none exists a default pattern is "
                "created. Force- and displacement-based elements resolve a point "
                "load through their integration points: split the member at the "
                "load for exact end forces.</i>",
            )
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_mode_changed(self) -> None:
        if self.mode() == RELATIVE:
            self._distance.setRange(0.0, 1.0)
            self._distance.setSingleStep(0.1)
        else:
            self._distance.setRange(0.0, 1e12)
            self._distance.setSingleStep(1.0)

    def _on_accept(self) -> None:
        if all(field.value() == 0.0 for field in self._fields.values()):
            QMessageBox.warning(self, "Assign Frame Point Load", "Enter a non-zero force.")
            return
        self.accept()

    def mode(self) -> str:
        """``RELATIVE`` or ``ABSOLUTE``."""
        return str(self._mode.currentData())

    def distance(self) -> float:
        return self._distance.value()

    def values(self) -> tuple[float, float, float]:
        """Return (Py, Pz, Px)."""
        return (
            self._fields["Py"].value(),
            self._fields["Pz"].value(),
            self._fields["Px"].value(),
        )
