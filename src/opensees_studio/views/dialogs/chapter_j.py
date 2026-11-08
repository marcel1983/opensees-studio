"""Design → Connection Checks: AISC 360 Chapter J limit states."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.core.aisc import SOURCE_UNITS
from opensees_studio.core.design.chapter_j_model import ChapterJCheck
from opensees_studio.core.help import TOPIC_PROPERTY
from opensees_studio.core.units import force_scale, length_scale, stress_scale
from opensees_studio.views.float_field import FloatField
from opensees_studio.views.screen_fit import FittedDialog

_TYPES = (
    ("Fillet weld (J2.4)", "fillet_weld"),
    ("Bolt shear (J3.1)", "bolt_shear"),
    ("Bolt tension (J3.1)", "bolt_tension"),
    ("Bolt bearing/tearout (J3.6)", "bolt_bearing"),
    ("Slip-critical (J3.4)", "slip_critical"),
    ("Plate shear yielding (J4.3)", "plate_shear_yielding"),
    ("Plate shear rupture (J4.4)", "plate_shear_rupture"),
    ("Block shear (J4.5)", "block_shear"),
)


class ChapterJDialog(FittedDialog):
    """Lists, adds, edits and removes AISC 360 Chapter J checks."""

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = project
        self._items = [check.model_copy() for check in project.chapter_j_checks]
        self._unit_l = length_scale(SOURCE_UNITS, project.meta.units)
        self._unit_s = stress_scale(SOURCE_UNITS, project.meta.units)
        self._unit_f = force_scale(SOURCE_UNITS, project.meta.units)
        self.setWindowTitle("Connection Checks - AISC 360 Chapter J")
        self.setProperty(TOPIC_PROPERTY, "design.chapter_j")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "One AISC 360 Chapter J limit state per row. Only the fields used "
                "by the selected check are read; the demand is Vu or Tu."
            )
        )
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Check", "Name", "Type", "Demand"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setMinimumHeight(120)
        self._table.itemSelectionChanged.connect(self._load_selected)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("Name:", self._name)
        self._type = QComboBox()
        for label, key in _TYPES:
            self._type.addItem(label, key)
        self._type.currentIndexChanged.connect(self._update_fields)
        form.addRow("Check type:", self._type)
        self._demand = FloatField()
        self._demand.setRange(1e-9, 1e12)
        form.addRow("Demand Vu / Tu:", self._demand)
        layout.addLayout(form)

        self._weld_group = QGroupBox("Fillet weld (J2.4)")
        weld = QFormLayout(self._weld_group)
        self._fexx = FloatField()
        self._fexx.setRange(1e-6, 1e9)
        self._fexx.setValue(70.0 * self._unit_s)
        weld.addRow("Fexx:", self._fexx)
        self._weld_leg = FloatField()
        self._weld_leg.setRange(1e-6, 1e9)
        self._weld_leg.setValue(0.25 * self._unit_l)
        weld.addRow("Weld leg:", self._weld_leg)
        self._weld_length = FloatField()
        self._weld_length.setRange(1e-6, 1e9)
        self._weld_length.setValue(10.0 * self._unit_l)
        weld.addRow("Weld length:", self._weld_length)
        self._weld_both = QCheckBox("Both sides")
        self._weld_both.setChecked(True)
        weld.addRow("Sides:", self._weld_both)
        layout.addWidget(self._weld_group)

        self._bolt_group = QGroupBox("Bolts (J3.1 / J3.6)")
        bolt = QFormLayout(self._bolt_group)
        self._fn = FloatField()
        self._fn.setRange(1e-6, 1e9)
        self._fn.setValue(54.0 * self._unit_s)
        bolt.addRow("Fnv / Fnt:", self._fn)
        self._bolt_diameter = FloatField()
        self._bolt_diameter.setRange(1e-6, 1e9)
        self._bolt_diameter.setValue(0.75 * self._unit_l)
        bolt.addRow("Bolt diameter:", self._bolt_diameter)
        self._bolt_count = FloatField()
        self._bolt_count.setRange(1.0, 1e6)
        self._bolt_count.setValue(4.0)
        bolt.addRow("Bolt count:", self._bolt_count)
        self._fu = FloatField()
        self._fu.setRange(1e-6, 1e9)
        self._fu.setValue(65.0 * self._unit_s)
        bolt.addRow("Fu (bearing):", self._fu)
        self._thickness = FloatField()
        self._thickness.setRange(1e-6, 1e9)
        self._thickness.setValue(0.5 * self._unit_l)
        bolt.addRow("Plate thickness:", self._thickness)
        self._edge = FloatField()
        self._edge.setRange(1e-6, 1e9)
        self._edge.setValue(1.5 * self._unit_l)
        bolt.addRow("Edge distance:", self._edge)
        self._hole = FloatField()
        self._hole.setRange(1e-6, 1e9)
        self._hole.setValue(0.8125 * self._unit_l)
        bolt.addRow("Hole diameter:", self._hole)
        self._deformation = QCheckBox("Deformation is a design consideration")
        self._deformation.setChecked(True)
        bolt.addRow("Bearing:", self._deformation)
        layout.addWidget(self._bolt_group)

        self._slip_group = QGroupBox("Slip-critical (J3.4)")
        slip = QFormLayout(self._slip_group)
        self._mu = FloatField()
        self._mu.setRange(1e-6, 1.0)
        self._mu.setValue(0.3)
        slip.addRow("Slip coefficient mu:", self._mu)
        self._tb = FloatField()
        self._tb.setRange(1e-6, 1e12)
        self._tb.setValue(28.0 * self._unit_f)
        slip.addRow("Pretension Tb:", self._tb)
        self._slip_planes = FloatField()
        self._slip_planes.setRange(1.0, 1e6)
        self._slip_planes.setValue(1.0)
        slip.addRow("Slip planes:", self._slip_planes)
        self._hole_type = QComboBox()
        self._hole_type.addItem("Standard", "standard")
        self._hole_type.addItem("Oversized", "oversized")
        self._hole_type.addItem("Long-slotted", "long_slotted")
        slip.addRow("Hole type:", self._hole_type)
        layout.addWidget(self._slip_group)

        self._plate_group = QGroupBox("Plate and block shear (J4.3 / J4.4 / J4.5)")
        plate = QFormLayout(self._plate_group)
        self._fy = FloatField()
        self._fy.setRange(1e-6, 1e9)
        self._fy.setValue(50.0 * self._unit_s)
        plate.addRow("Fy:", self._fy)
        self._agv = FloatField()
        self._agv.setRange(1e-9, 1e12)
        self._agv.setValue(6.0 * self._unit_l**2)
        plate.addRow("Agv:", self._agv)
        self._anv = FloatField()
        self._anv.setRange(1e-9, 1e12)
        self._anv.setValue(4.375 * self._unit_l**2)
        plate.addRow("Anv:", self._anv)
        self._ant = FloatField()
        self._ant.setRange(1e-9, 1e12)
        self._ant.setValue(1.0 * self._unit_l**2)
        plate.addRow("Ant:", self._ant)
        self._uniform = QCheckBox("Uniform tension (Ubs = 1.0)")
        self._uniform.setChecked(True)
        plate.addRow("Block shear:", self._uniform)
        layout.addWidget(self._plate_group)

        row = QHBoxLayout()
        add = QPushButton("Add")
        add.clicked.connect(self._add)
        update = QPushButton("Update selected")
        update.clicked.connect(self._update)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self._remove)
        row.addWidget(add)
        row.addWidget(update)
        row.addWidget(remove)
        row.addStretch(1)
        layout.addLayout(row)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()
        self._update_fields()

    def _update_fields(self) -> None:
        kind = str(self._type.currentData())
        self._weld_group.setEnabled(kind == "fillet_weld")
        self._bolt_group.setEnabled(kind in ("bolt_shear", "bolt_tension", "bolt_bearing"))
        self._slip_group.setEnabled(kind == "slip_critical")
        self._plate_group.setEnabled(
            kind in ("plate_shear_yielding", "plate_shear_rupture", "block_shear")
        )
        self._summary.setText(
            "Only the fields used by the selected check are read. "
            "The report shows the nominal, available and ratio."
        )

    def _next_id(self) -> int:
        used = {item.id for item in self._items}
        return max(used, default=0) + 1

    def _candidate(self) -> ChapterJCheck:
        return ChapterJCheck(
            id=self._next_id(),
            name=self._name.text().strip(),
            check_type=self._type.currentData(),
            demand=self._demand.value(),
            fexx=self._fexx.value(),
            weld_leg=self._weld_leg.value(),
            weld_length=self._weld_length.value(),
            weld_both_sides=self._weld_both.isChecked(),
            fn=self._fn.value(),
            bolt_diameter=self._bolt_diameter.value(),
            bolt_count=int(self._bolt_count.value()),
            fu=self._fu.value(),
            thickness=self._thickness.value(),
            edge_distance=self._edge.value(),
            hole_diameter=self._hole.value(),
            deformation=self._deformation.isChecked(),
            mu=self._mu.value(),
            tb=self._tb.value(),
            slip_planes=int(self._slip_planes.value()),
            hole_type=self._hole_type.currentData(),
            fy=self._fy.value(),
            agv=self._agv.value(),
            anv=self._anv.value(),
            ant=self._ant.value(),
            uniform_tension=self._uniform.isChecked(),
        )

    def _add(self) -> None:
        self._items.append(self._candidate())
        self._refresh()

    def _update(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        candidate = self._candidate()
        candidate.id = self._items[row].id
        self._items[row] = candidate
        self._refresh()

    def _remove(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            del self._items[row]
            self._refresh()

    def _refresh(self) -> None:
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            values = (item.id, item.name or "-", item.check_type, item.demand)
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(str(value)))
        self._summary.setText(f"{len(self._items)} connection check(s).")

    def _load_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._items):
            return
        item = self._items[row]
        self._name.setText(item.name)
        index = self._type.findData(item.check_type)
        if index >= 0:
            self._type.setCurrentIndex(index)
        self._demand.setValue(item.demand)
        self._fexx.setValue(item.fexx or 70.0 * self._unit_s)
        self._weld_leg.setValue(item.weld_leg or 0.25 * self._unit_l)
        self._weld_length.setValue(item.weld_length or 10.0 * self._unit_l)
        self._weld_both.setChecked(item.weld_both_sides)
        self._fn.setValue(item.fn or 54.0 * self._unit_s)
        self._bolt_diameter.setValue(item.bolt_diameter or 0.75 * self._unit_l)
        self._bolt_count.setValue(float(item.bolt_count or 4))
        self._fu.setValue(item.fu or 65.0 * self._unit_s)
        self._thickness.setValue(item.thickness or 0.5 * self._unit_l)
        self._edge.setValue(item.edge_distance or 1.5 * self._unit_l)
        self._hole.setValue(item.hole_diameter or 0.8125 * self._unit_l)
        self._deformation.setChecked(item.deformation)
        self._mu.setValue(item.mu or 0.3)
        self._tb.setValue(item.tb or 28.0 * self._unit_f)
        self._slip_planes.setValue(float(item.slip_planes or 1))
        index = self._hole_type.findData(item.hole_type)
        if index >= 0:
            self._hole_type.setCurrentIndex(index)
        self._fy.setValue(item.fy or 50.0 * self._unit_s)
        self._agv.setValue(item.agv or 6.0 * self._unit_l**2)
        self._anv.setValue(item.anv or 4.375 * self._unit_l**2)
        self._ant.setValue(item.ant or 1.0 * self._unit_l**2)
        self._uniform.setChecked(item.uniform_tension)
        self._update_fields()

    def checks(self) -> list[ChapterJCheck]:
        """The checks as the dialog shows them."""
        return [item.model_copy() for item in self._items]
