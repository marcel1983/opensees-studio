"""The Bracing page of the Warehouse Wizard: the X braces of the roof and of the walls.

The roof and the side walls are braced on their own: each has its bays (the
whole roof may be braced and only two bays of each wall), the roof its number
of X panels per slope, and each says whether its braces work in tension only.
:meth:`BracingFields.spec_fields` hands them to
:class:`~opensees_studio.core.warehouse.WarehouseSpec`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from opensees_studio.core.warehouse import WarehouseError
from opensees_studio.core.warehouse_stiffeners import ROOF_STIFFENERS, WALL_BRACING_TYPES
from opensees_studio.views.i18n import tr

_TENSION_ONLY_TIP = (
    "Rods and slender angles buckle at once in compression: each X then holds with "
    "the diagonal the load stretches. The braces become tension-only members, and "
    "each load combination is analysed as a case of its own (Newton iteration), "
    "because which diagonal works depends on the whole load. Untick for braces "
    "that also take compression."
)


#: Labels of :data:`ROOF_STIFFENERS`, in its order.
STIFFENER_LABELS: tuple[str, ...] = ("None", "Beams", "Trusses")
#: Labels of :data:`WALL_BRACING_TYPES`, in its order.
WALL_BRACING_LABELS: tuple[str, ...] = (
    "X from the base to the eave",
    "Double X with a strut at mid-height",
    "Moment frame (eave beam framed into the columns)",
)


def parse_bays(text: str) -> tuple[int, ...] | None:
    """0-based bays of a field of 1-based numbers (``"1, 4; 7"``); None when empty."""
    text = text.strip()
    if not text:
        return None
    try:
        return tuple(int(part) - 1 for part in text.replace(";", ",").split(",") if part.strip())
    except ValueError:
        raise WarehouseError(
            "The braced bays are numbers separated by commas, for example 1, 6."
        ) from None


class BracingFields(QObject):
    """The fields of the roof and the wall bracing; ``changed`` when any of them does."""

    changed = Signal()

    def __init__(self, length: Callable[[float], Any], parent: QObject | None = None) -> None:
        """``length(metres)`` makes a length field in the project's units."""
        super().__init__(parent)
        self.roof = QCheckBox("X bracing in the roof")
        self.roof.setChecked(True)
        self.roof_bays = QLineEdit()
        self.roof_bays.setPlaceholderText("First and last bay")
        self.roof_bays.setToolTip(
            "Bay numbers with roof bracing, separated by commas (bay 1 is between the "
            "first two frames). Leave empty for the first and the last bay."
        )
        self.roof_panels = QSpinBox()
        self.roof_panels.setRange(0, 99)
        self.roof_panels.setSpecialValueText(tr("About as long as the bay"))
        self.roof_panels.setToolTip(
            "How many X each slope of roof has across the building, in each braced bay: "
            "the slope is cut on purlin lines, so there are at most as many as purlin "
            "spaces. Automatic makes each panel about as long as the bay, so the "
            "diagonals stay near 45 degrees."
        )
        self.roof_tension_only = QCheckBox("Roof braces work in tension only")
        self.roof_tension_only.setChecked(True)
        self.roof_tension_only.setToolTip(_TENSION_ONLY_TIP)

        self.wall = QCheckBox("X bracing in the side walls")
        self.wall.setChecked(True)
        self.wall_bays = QLineEdit()
        self.wall_bays.setPlaceholderText("Same bays as the roof")
        self.wall_bays.setToolTip(
            "Bay numbers with wall bracing, separated by commas. Leave empty for the "
            "bays the roof has."
        )
        self.wall_tension_only = QCheckBox("Wall braces work in tension only")
        self.wall_tension_only.setChecked(True)
        self.wall_tension_only.setToolTip(_TENSION_ONLY_TIP)

        self.wall_type = QComboBox()
        for label in WALL_BRACING_LABELS:
            self.wall_type.addItem(tr(label))
        self.wall_type.setToolTip(
            "What holds a braced bay of a side wall along the building: one X from the "
            "base to the eave; two X one above the other, with a strut between the two "
            "columns at mid-height (the girt line nearest it, when the wall has girts); "
            "or a moment frame, whose eave beam is framed into the two columns."
        )
        self.stiffeners = QComboBox()
        for label in STIFFENER_LABELS:
            self.stiffeners.addItem(tr(label))
        self.stiffeners.setToolTip(
            "Longitudinal beams or trusses from frame to frame, framed into the rafters at "
            "mid-span of each nave and on more lines towards the columns. Each takes the "
            "place of the purlin on its line, and the roof X braces are cut at their "
            "lines, so each X lies within a space between two of them."
        )
        self.stiffener_lines = QSpinBox()
        self.stiffener_lines.setRange(0, 20)
        self.stiffener_lines.setToolTip(
            "Stiffener lines on each side of the one at mid-span, evenly between it and "
            "the columns, each on the nearest purlin line."
        )
        self.stiffener_depth = length(0.6)
        self.stiffener_depth.setToolTip(
            "Depth of a stiffening truss, from the roof line down to its bottom chord."
        )
        self.stiffeners.currentIndexChanged.connect(self._on_changed)
        self.wall_type.currentIndexChanged.connect(self._on_changed)
        self.stiffener_lines.valueChanged.connect(self._on_changed)
        self.stiffener_depth.valueChanged.connect(self._on_changed)
        for box in (self.roof, self.wall, self.roof_tension_only, self.wall_tension_only):
            box.toggled.connect(self._on_changed)
        for edit in (self.roof_bays, self.wall_bays):
            edit.textChanged.connect(self._on_changed)
        self.roof_panels.valueChanged.connect(self._on_changed)
        self._enable()

    def add_to(self, form: QFormLayout) -> None:
        """Put the two groups of fields on ``form``."""
        roof = QGroupBox("Roof bracing")
        roof_form = QFormLayout(roof)
        roof_form.addRow(self.roof)
        roof_form.addRow("Braced bays:", self.roof_bays)
        roof_form.addRow("X panels per roof slope:", self.roof_panels)
        roof_form.addRow(self.roof_tension_only)
        roof_form.addRow("Roof stiffeners:", self.stiffeners)
        roof_form.addRow("Stiffener lines each side of mid-span:", self.stiffener_lines)
        roof_form.addRow("Stiffening truss depth:", self.stiffener_depth)
        wall = QGroupBox("Wall bracing")
        wall_form = QFormLayout(wall)
        wall_form.addRow(self.wall)
        wall_form.addRow("Braced bays:", self.wall_bays)
        wall_form.addRow("Bracing of a braced bay:", self.wall_type)
        wall_form.addRow(self.wall_tension_only)
        form.addRow(roof)
        form.addRow(wall)

    def widgets(self) -> list[QWidget]:
        return [
            self.roof,
            self.roof_bays,
            self.roof_panels,
            self.roof_tension_only,
            self.wall,
            self.wall_bays,
            self.wall_type,
            self.wall_tension_only,
            self.stiffeners,
            self.stiffener_lines,
            self.stiffener_depth,
        ]

    def spec_fields(self) -> dict[str, Any]:
        """The :class:`WarehouseSpec` fields of the bracing.

        Raises:
            WarehouseError: when a field of bays is not a list of numbers.
        """
        return {
            "roof_bracing": self.roof.isChecked(),
            "wall_bracing": self.wall.isChecked(),
            "braced_bays": parse_bays(self.roof_bays.text()),
            "wall_braced_bays": parse_bays(self.wall_bays.text()),
            "roof_bracing_panels": self.roof_panels.value(),
            "roof_tension_only": self.roof.isChecked() and self.roof_tension_only.isChecked(),
            "wall_tension_only": self.wall_tension_only.isEnabled()
            and self.wall_tension_only.isChecked(),
            "wall_bracing_type": WALL_BRACING_TYPES[self.wall_type.currentIndex()],
            "roof_stiffeners": ROOF_STIFFENERS[self.stiffeners.currentIndex()],
            "stiffener_lines": self.stiffener_lines.value(),
            "stiffener_depth": (
                self.stiffener_depth.value() if self.stiffeners.currentIndex() == 2 else 0.0
            ),
        }

    def _enable(self) -> None:
        roof, wall = self.roof.isChecked(), self.wall.isChecked()
        for widget in (self.roof_bays, self.roof_panels, self.roof_tension_only):
            widget.setEnabled(roof)
        frame = WALL_BRACING_TYPES[self.wall_type.currentIndex()] == "moment_frame"
        self.wall_bays.setEnabled(wall)
        self.wall_type.setEnabled(wall)
        self.wall_tension_only.setEnabled(wall and not frame)
        stiffened = self.stiffeners.currentIndex() > 0
        self.stiffener_lines.setEnabled(stiffened)
        self.stiffener_depth.setEnabled(self.stiffeners.currentIndex() == 2)

    def _on_changed(self, *_args: object) -> None:
        self._enable()
        self.changed.emit()


__all__ = ["BracingFields", "parse_bays"]
