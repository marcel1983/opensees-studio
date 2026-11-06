"""Design → Connections: the AISC 358-22 RBS connections of the project."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.core.design.connections import RbsConnection, rbs_geometry
from opensees_studio.core.geometry.elements import FRAME_ELEMENT_CLASSES
from opensees_studio.core.help import TOPIC_PROPERTY
from opensees_studio.services.steel_design import shape_in_units
from opensees_studio.views.float_field import FloatField
from opensees_studio.views.screen_fit import FittedDialog


class ConnectionsDialog(FittedDialog):
    """Lists, adds, edits and removes RBS connections."""

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = project
        self._items = [connection.model_copy() for connection in project.connections]
        self._sections = {s.id: s for s in project.sections}
        self._elements = {e.id: e for e in project.elements if isinstance(e, FRAME_ELEMENT_CLASSES)}
        self.setWindowTitle("Connections - AISC 358-22")
        self.setProperty(TOPIC_PROPERTY, "design.connections")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "A reduced beam section (RBS) moves the plastic hinge away from the "
                "column face. The cut is checked against AISC 358-22 Section 5.7: "
                "0.5bf <= a <= 0.75bf, 0.65d <= b <= 0.85d and 0.1bf <= c <= 0.25bf."
            )
        )
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Connection", "Beam", "Column", "a", "b", "c"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setMinimumHeight(130)
        self._table.itemSelectionChanged.connect(self._load_selected)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._beam = QComboBox()
        self._column = QComboBox()
        for element_id, element in sorted(self._elements.items()):
            label = f"{element_id} ({self._section_name(element)})"
            self._beam.addItem(label, element_id)
            self._column.addItem(label, element_id)
        self._beam.currentIndexChanged.connect(self._prefill)
        form.addRow("Beam element:", self._beam)
        form.addRow("Column element:", self._column)
        self._a = FloatField()
        self._a.setRange(1e-6, 1e9)
        form.addRow("a (cut start):", self._a)
        self._b = FloatField()
        self._b.setRange(1e-6, 1e9)
        form.addRow("b (cut length):", self._b)
        self._c = FloatField()
        self._c.setRange(1e-6, 1e9)
        form.addRow("c (cut depth):", self._c)
        layout.addLayout(form)

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
        self._prefill()

    def _section_name(self, element: Any) -> str:
        section = self._sections.get(getattr(element, "section_id", -1))
        return getattr(section, "name", "") or "no section"

    def _shape(self, element_id: int) -> Any:
        element = self._elements.get(element_id)
        if element is None:
            return None
        name = self._section_name(element)
        try:
            return shape_in_units(name, self._project.meta.units)
        except (KeyError, ValueError):
            return None

    def _next_id(self) -> int:
        used = {item.id for item in self._items}
        return max(used, default=0) + 1

    def _prefill(self) -> None:
        """Suggest the midpoints of the 5.7 limits for the selected beam."""
        shape = self._shape(int(self._beam.currentData())) if self._beam.count() else None
        if shape is None or not hasattr(shape, "bf"):
            return
        if self._a.value() and self._b.value() and self._c.value():
            return
        self._a.setValue(0.625 * shape.bf)
        self._b.setValue(0.75 * shape.d)
        self._c.setValue(0.175 * shape.bf)

    def _candidate(self) -> RbsConnection | None:
        if not self._beam.count() or not self._column.count():
            QMessageBox.warning(self, "Connections", "The project has no frame elements.")
            return None
        beam_id = int(self._beam.currentData())
        column_id = int(self._column.currentData())
        if beam_id == column_id:
            QMessageBox.warning(self, "Connections", "Beam and column are the same element.")
            return None
        connection = RbsConnection(
            id=self._next_id(),
            beam_element_id=beam_id,
            column_element_id=column_id,
            a=self._a.value(),
            b=self._b.value(),
            c=self._c.value(),
        )
        shape = self._shape(beam_id)
        if shape is None:
            QMessageBox.warning(self, "Connections", "The beam section is not an AISC shape.")
            return None
        try:
            rbs_geometry(connection, shape)
        except ValueError as exc:
            QMessageBox.warning(self, "Connections", str(exc))
            return None
        return connection

    def _add(self) -> None:
        connection = self._candidate()
        if connection is None:
            return
        self._items.append(connection)
        self._refresh()

    def _update(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        connection = self._candidate()
        if connection is None:
            return
        connection.id = self._items[row].id
        self._items[row] = connection
        self._refresh()

    def _remove(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            del self._items[row]
            self._refresh()

    def _refresh(self) -> None:
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            values = (
                item.id,
                item.beam_element_id,
                item.column_element_id,
                item.a,
                item.b,
                item.c,
            )
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(str(value)))
        self._summary.setText(
            f"{len(self._items)} connection(s). Invalid cuts are refused when added."
        )

    def _load_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._items):
            return
        item = self._items[row]
        for combo, value in (
            (self._beam, item.beam_element_id),
            (self._column, item.column_element_id),
        ):
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
        self._a.setValue(item.a)
        self._b.setValue(item.b)
        self._c.setValue(item.c)

    def connections(self) -> list[RbsConnection]:
        """The connections as the dialog shows them."""
        return [item.model_copy() for item in self._items]
