"""Minimal Constant series editor with undoable, reference-safe operations."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.commands.series_and_patterns import (
    AddTimeSeriesCommand,
    DeleteTimeSeriesCommand,
    ReplaceTimeSeriesCommand,
)
from opensees_studio.core import ConstantTimeSeries, Project
from opensees_studio.viewmodels import ProjectViewModel
from opensees_studio.views.float_field import FloatField
from opensees_studio.views.screen_fit import FittedDialog, MessageArea


class ConstantTimeSeriesDialog(FittedDialog):
    def __init__(self, vm: ProjectViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = vm
        self.setWindowTitle("Constant Time Series")
        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(self._list)
        self._name = QLineEdit("Constant")
        self._factor = FloatField()
        self._factor.setRange(-1e100, 1e100)
        self._factor.setValue(1)
        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Factor:", self._factor)
        layout.addLayout(form)
        row = QHBoxLayout()
        for label, callback in (
            ("Add", self._add),
            ("Apply", self._apply),
            ("Delete", self._delete),
            ("Close", self.accept),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self._message = MessageArea()
        layout.addWidget(self._message)
        self._list.currentRowChanged.connect(self._select)
        vm.modelMutated.connect(self._refresh)
        self._refresh()

    def _project(self) -> Project:
        project = self._vm.project
        if project is None:
            raise RuntimeError("The Constant Time Series dialog needs an open project.")
        return project

    def _refresh(self) -> None:
        self._list.clear()
        for series in self._project().time_series:
            if isinstance(series, ConstantTimeSeries):
                item = QListWidgetItem(f"#{series.id} {series.name} (factor {series.factor:g})")
                item.setData(Qt.ItemDataRole.UserRole, series.id)
                self._list.addItem(item)

    def _id(self) -> int | None:
        item = self._list.currentItem()
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _select(self) -> None:
        series = next((s for s in self._project().time_series if s.id == self._id()), None)
        if series:
            self._name.setText(series.name)
            self._factor.setValue(series.factor)

    def _entity(self, sid: int) -> ConstantTimeSeries:
        return ConstantTimeSeries(id=sid, name=self._name.text(), factor=self._factor.value())

    def _add(self) -> None:
        self._vm.apply_command(
            AddTimeSeriesCommand(self._vm, self._entity(self._project().next_time_series_id()))
        )

    def _apply(self) -> None:
        sid = self._id()
        if sid is not None:
            self._vm.apply_command(ReplaceTimeSeriesCommand(self._vm, self._entity(sid)))

    def _delete(self) -> None:
        sid = self._id()
        if sid is None:
            return
        try:
            command = DeleteTimeSeriesCommand(self._vm, sid)
            self._vm.apply_command(command)
        except ValueError as exc:
            self._message.show_message(str(exc), "error")
