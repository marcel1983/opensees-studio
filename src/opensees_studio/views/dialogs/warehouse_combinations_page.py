"""The Combinations page of the Warehouse Wizard: the code's combinations, to see and edit.

The page plans the warehouse as the other pages describe it and shows the
combinations of the code on its load cases, one row each and a column per
case. A factor can be changed (an empty cell is 0), a combination unticked or
renamed, and one added; :meth:`CombinationsEditor.edited` hands the rows to
``WarehouseLoads.edited_combinations`` when they differ from the code's. When
the load cases change (another code, the wind turned on) the table starts
again from the code's combinations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.core.warehouse import PlannedCombination, WarehouseError
from opensees_studio.views.dialogs.frame_wizard import _CompletablePage
from opensees_studio.views.float_field import format_float, parse_float
from opensees_studio.views.i18n import tr

#: The columns before the load cases.
_NAME, _SET, _FIRST_CASE = 0, 1, 2


class CombinationsEditor(QWidget):
    """A table of combinations against load cases; ``changed`` on every edit."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._code: list[PlannedCombination] = []
        self._cases: list[str] = []
        self.table = QTableWidget(0, _FIRST_CASE)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setToolTip(
            "One row per combination, one column per load case: the factor of that case "
            "(empty is 0). Untick a combination to leave it out; double-click a name or a "
            "factor to change it."
        )
        self.add = QPushButton("Add Combination")
        self.remove = QPushButton("Remove")
        self.reset = QPushButton("Restore the Code's Combinations")
        self.add.clicked.connect(self._add_row)
        self.remove.clicked.connect(self._remove_rows)
        self.reset.clicked.connect(self._restore)
        self.table.itemChanged.connect(lambda _item: self.changed.emit())
        buttons = QHBoxLayout()
        for button in (self.add, self.remove, self.reset):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

    # ── what the plan gives ─────────────────────────────────────────
    @property
    def shown(self) -> bool:
        """The code's combinations have been shown (the page was visited)."""
        return bool(self._cases)

    def show_code(self, code: list[PlannedCombination], cases: list[str]) -> None:
        """Show the code's ``code`` on ``cases``; edits stay while both are the same."""
        if code == self._code and cases == self._cases:
            return
        self._code, self._cases = list(code), list(cases)
        self._restore()

    def _restore(self) -> None:
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(_FIRST_CASE + len(self._cases))
        self.table.setHorizontalHeaderLabels([tr("Combination"), tr("Set"), *self._cases])
        self.table.setRowCount(0)
        for combination in self._code:
            self._append(combination)
        self.table.blockSignals(False)
        self.changed.emit()

    def _append(self, combination: PlannedCombination, *, at: int | None = None) -> None:
        row = self.table.rowCount() if at is None else at
        self.table.insertRow(row)
        name = QTableWidgetItem(combination.name)
        name.setFlags(name.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
        name.setCheckState(Qt.CheckState.Checked)
        self.table.setItem(row, _NAME, name)
        group = QTableWidgetItem(combination.group)
        group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, _SET, group)
        for column, case in enumerate(self._cases, start=_FIRST_CASE):
            factor = combination.factor(case)
            item = QTableWidgetItem(format_float(factor) if factor else "")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, item)

    def _add_row(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        at = rows[-1] + 1 if rows else self.table.rowCount()
        group_row = rows[-1] if rows else self.table.rowCount() - 1
        group = self._text(group_row, _SET) if group_row >= 0 else ""
        taken = {self._text(r, _NAME) for r in range(self.table.rowCount())}
        n = 1
        while f"COMB{n}" in taken:
            n += 1
        self.table.blockSignals(True)
        self._append(PlannedCombination(f"COMB{n}", (), group), at=at)
        self.table.blockSignals(False)
        self.table.selectRow(at)
        self.changed.emit()

    def _remove_rows(self) -> None:
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        self.changed.emit()

    # ── what the user made of it ────────────────────────────────────
    def _text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item is not None else ""

    def rows(self) -> tuple[PlannedCombination, ...]:
        """The ticked rows.

        Raises:
            ValueError: for a factor that is not a number.
        """
        out = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, _NAME)
            if name is None or name.checkState() != Qt.CheckState.Checked:
                continue
            factors = []
            for column, case in enumerate(self._cases, start=_FIRST_CASE):
                text = self._text(row, column)
                if not text:
                    continue
                try:
                    value = parse_float(text.replace(",", "."))
                except ValueError:
                    raise ValueError(
                        tr("The factor of {case} in {name} is not a number: {text}").format(
                            case=case, name=name.text(), text=text
                        )
                    ) from None
                if value != 0.0:
                    factors.append((case, value))
            out.append(
                PlannedCombination(name.text().strip(), tuple(factors), self._text(row, _SET))
            )
        return tuple(out)

    def edited(self) -> tuple[PlannedCombination, ...] | None:
        """The rows when they differ from the code's combinations, else None.

        Raises:
            ValueError: for a factor that is not a number.
        """
        rows = self.rows()
        code = tuple(
            PlannedCombination(c.name, tuple((n, f) for n, f in c.factors if f != 0.0), c.group)
            for c in self._code
        )
        same = len(rows) == len(code) and all(
            a.name == b.name and a.group == b.group and _factors(a) == _factors(b)
            for a, b in zip(rows, code, strict=True)
        )
        return None if same else rows


class CombinationsPage(_CompletablePage):
    """The wizard page around a :class:`CombinationsEditor`.

    ``preview()`` plans the warehouse as the other pages describe it, without
    the edits of this page, and returns the plan, or None when no combinations
    are wanted; :meth:`refresh` calls it when the page is shown.
    """

    def __init__(self, preview: Callable[[], Any | None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview = preview
        self._error = ""
        self._wanted = True
        self.complete_check = lambda: not self._error
        self.setTitle("Load combinations")
        self.setSubTitle(
            "The combinations of the code on these load cases: change a factor, untick "
            "a combination or add one."
        )
        self.editor = CombinationsEditor(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        note = QLabel(
            "<i>An envelope is made over the ticked combinations of each set. With the "
            "braces in tension only each combination is analysed as a case of its own. "
            "When the load cases change the table starts again from the code's "
            "combinations.</i>"
        )
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.summary)
        layout.addWidget(note)
        self.editor.changed.connect(self._check)

    def refresh(self) -> None:
        """Plan again and show the code's combinations on the cases of the plan."""
        try:
            plan = self._preview()
        except WarehouseError as exc:
            plan, self._error = None, str(exc)
            self._wanted = True
            self.editor.setEnabled(False)
            self.summary.setText("<b>" + tr("Check the numbers:") + f"</b> {tr(self._error)}")
            self.completeChanged.emit()
            return
        self._wanted = plan is not None
        self.editor.setEnabled(self._wanted)
        if plan is not None:
            cases: list[str] = []
            for combination in plan.code_combinations:
                for name, _factor in combination.factors:
                    if name not in cases:
                        cases.append(name)
            for case in plan.cases:
                name = case.name or str(case.id)
                derived = name.startswith("Comb: ") or getattr(case, "direct_analysis", None)
                if name not in cases and not derived:
                    cases.append(name)
            self.editor.show_code(plan.code_combinations, cases)
        self._check()

    def _check(self) -> None:
        self._error = ""
        if not self._wanted:
            self.summary.setText(
                tr("No combinations are made: Generate the load combinations of the code is off.")
            )
        else:
            try:
                rows = self.editor.rows()
                edited = self.editor.edited()
            except ValueError as exc:
                self._error = str(exc)
                self.summary.setText("<b>" + tr("Check the numbers:") + f"</b> {self._error}")
            else:
                names = [r.name for r in rows]
                if any(not n for n in names):
                    self._error = tr("Every combination needs a name.")
                elif len(set(names)) < len(names):
                    self._error = tr("Two combinations have the same name.")
                elif any(not r.factors for r in rows):
                    self._error = tr("A ticked combination has no load case with a factor.")
                if self._error:
                    self.summary.setText("<b>" + tr("Check the numbers:") + f"</b> {self._error}")
                else:
                    text = tr("<b>{n}</b> combinations will be created.").format(n=len(rows))
                    if edited is not None:
                        text += " " + tr("They differ from the code's.")
                    self.summary.setText(text)
        self.completeChanged.emit()

    def edited(self) -> tuple[PlannedCombination, ...] | None:
        """The combinations to make instead of the code's; None for the code's.

        Raises:
            WarehouseError: for a factor that is not a number.
        """
        if not self._wanted or not self.editor.shown:
            return None
        try:
            return self.editor.edited()
        except ValueError as exc:
            raise WarehouseError(str(exc)) from None


def _factors(combination: PlannedCombination) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, factor in combination.factors:
        out[name] = out.get(name, 0.0) + factor
    return out


__all__ = ["CombinationsEditor", "CombinationsPage"]
