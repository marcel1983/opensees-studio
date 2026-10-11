"""Define → Load Combinations: factored sums and envelopes of analysis-case results.

The list on the left holds the project's combinations; the form on the right
edits the selected one (name, type, and a table of included cases or
combinations with their scale factors). Every change goes through an undoable
command. A combination is checked before it is applied: a missing or
non-combinable case, an empty list or a cycle of combinations is refused, and
adding a possibly nonlinear case is applied with a warning.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.commands import (
    AddCombinationsCommand,
    DeleteCombinationsCommand,
    UpdateCombinationCommand,
)
from opensees_studio.core import (
    COMBINATION_LABELS,
    COMBINATION_TYPES,
    CombinationTerm,
    LoadCombination,
    Project,
)
from opensees_studio.core.combinations import (
    COMBINABLE_CASE_TYPES,
    LOAD_ROLE_LABELS,
    LOAD_ROLES,
    asce7_16_lrfd,
    combination_problems,
    combinations_using_combination,
    guess_load_role,
    superposition_warnings,
)
from opensees_studio.viewmodels import ProjectViewModel
from opensees_studio.views.float_field import FloatField
from opensees_studio.views.screen_fit import FittedDialog, MessageArea

ENVELOPE_NAME = "LRFD envelope"
"""Name of the envelope the ASCE 7-16 generator adds over what it generated."""


def _key(source: str, ref_id: int) -> str:
    """Item data of a term source: ``case:3`` or ``combination:2``."""
    return f"{source}:{ref_id}"


def _combinable_cases(project: Project) -> list[Any]:
    return [c for c in project.analyses if c.type in COMBINABLE_CASE_TYPES]


class _TermRow:
    """The two cell widgets of one term row."""

    def __init__(self, source: QComboBox, factor: FloatField) -> None:
        self.source = source
        self.factor = factor


class LoadCombinationsDialog(FittedDialog):
    """Library-style editor for ``project.combinations``."""

    def __init__(self, vm: ProjectViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Load Combinations")
        self.resize(860, 560)
        self._vm = vm
        self._rows: list[_TermRow] = []
        self._build_ui()
        self._refresh_list()
        self._vm.modelMutated.connect(self._refresh_list)

    # ── UI ───────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        intro = QLabel(
            "<b>Load Combinations</b> combine the stored results of analysis cases "
            "(Static and Response Spectrum) or of other combinations. Nothing is re-run: "
            "pick a combination in Analyze → Run, which runs only the cases without "
            "current results."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        body = QHBoxLayout()
        outer.addLayout(body, stretch=1)

        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        left.addWidget(self._list, stretch=1)
        row = QHBoxLayout()
        self._add_btn = QPushButton("Add")
        self._copy_btn = QPushButton("Copy")
        self._delete_btn = QPushButton("Delete")
        self._add_btn.clicked.connect(self._on_add)
        self._copy_btn.clicked.connect(self._on_copy)
        self._delete_btn.clicked.connect(self._on_delete)
        for btn in (self._add_btn, self._copy_btn, self._delete_btn):
            row.addWidget(btn)
        left.addLayout(row)
        self._generate_btn = QPushButton("Generate ASCE 7-16 LRFD…")
        self._generate_btn.setToolTip(
            "Add the ASCE 7-16 Section 2.3.1 basic strength combinations from cases "
            "tagged Dead, Live, Roof live, Snow, Rain, Wind and Earthquake."
        )
        self._generate_btn.clicked.connect(self._on_generate)
        left.addWidget(self._generate_btn)
        body.addLayout(left, stretch=1)

        right = QVBoxLayout()
        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("Name:", self._name)
        self._type = QComboBox()
        for kind in COMBINATION_TYPES:
            self._type.addItem(COMBINATION_LABELS[kind], kind)
        self._type.setToolTip(
            "Linear Add: factored sum. Envelope: maximum and minimum over the terms. "
            "Absolute Add: sum of magnitudes. SRSS: square root of the sum of squares."
        )
        form.addRow("Type:", self._type)
        right.addLayout(form)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Case / combination", "Scale factor"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        right.addWidget(self._table, stretch=1)

        term_row = QHBoxLayout()
        self._add_term_btn = QPushButton("Add term")
        self._remove_term_btn = QPushButton("Remove term")
        self._add_term_btn.clicked.connect(lambda: self.add_term())
        self._remove_term_btn.clicked.connect(self._on_remove_term)
        term_row.addWidget(self._add_term_btn)
        term_row.addWidget(self._remove_term_btn)
        term_row.addStretch(1)
        right.addLayout(term_row)

        self._message = MessageArea()
        right.addWidget(self._message)
        self._apply_btn = QPushButton("Apply changes")
        self._apply_btn.clicked.connect(self.apply)
        right.addWidget(self._apply_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self._editor = QWidget()
        self._editor.setLayout(right)
        body.addWidget(self._editor, stretch=2)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # ── list ─────────────────────────────────────────────────────────
    def _refresh_list(self) -> None:
        selected = self.selected_id()
        self._list.blockSignals(True)
        self._list.clear()
        project = self._vm.project
        for combo in project.combinations if project is not None else []:
            label = f"{combo.name or '(unnamed)'}  [{COMBINATION_LABELS[combo.combination_type]}]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, combo.id)
            self._list.addItem(item)
        self._list.blockSignals(False)
        if selected is not None:
            self.select(selected)
        if self._list.currentRow() < 0 and self._list.count():
            self._list.setCurrentRow(0)
        else:
            self._on_row_changed(self._list.currentRow())
        has_project = project is not None
        self._add_btn.setEnabled(has_project)
        self._generate_btn.setEnabled(has_project)
        self._copy_btn.setEnabled(self._list.count() > 0)
        self._delete_btn.setEnabled(self._list.count() > 0)

    def selected_id(self) -> int | None:
        item = self._list.currentItem()
        return None if item is None else int(item.data(Qt.ItemDataRole.UserRole))

    def select(self, combination_id: int) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) == combination_id:
                self._list.setCurrentRow(i)
                return

    def _selected(self) -> LoadCombination | None:
        cid = self.selected_id()
        project = self._vm.project
        if cid is None or project is None:
            return None
        return next((c for c in project.combinations if c.id == cid), None)

    def _on_row_changed(self, _row: int) -> None:
        combo = self._selected()
        self._editor.setEnabled(combo is not None)
        self._message.clear_message()
        self._table.setRowCount(0)
        self._rows = []
        if combo is None:
            self._name.clear()
            return
        self._name.setText(combo.name)
        self._type.setCurrentIndex(max(0, self._type.findData(combo.combination_type)))
        for term in combo.terms:
            self.add_term(term)

    # ── terms ────────────────────────────────────────────────────────
    def _source_choices(self, current: CombinationTerm | None) -> QComboBox:
        box = QComboBox()
        project = self._vm.project
        own_id = self.selected_id()
        if project is not None:
            for case in _combinable_cases(project):
                box.addItem(f"Case: {case.name or case.id}  [{case.type}]", _key("case", case.id))
            for combo in project.combinations:
                if combo.id != own_id:
                    box.addItem(
                        f"Combination: {combo.name or combo.id}", _key("combination", combo.id)
                    )
        if current is not None:
            key = _key(current.source, current.ref_id)
            index = box.findData(key)
            if index < 0:
                # A reference the list cannot offer (deleted, or not combinable):
                # shown as is, and refused when applied.
                box.addItem(f"(unavailable {current.source} {current.ref_id})", key)
                index = box.count() - 1
            box.setCurrentIndex(index)
        return box

    def add_term(self, term: CombinationTerm | None = None) -> None:
        """Append a term row (the first offered case at factor 1 when ``term`` is None)."""
        source = self._source_choices(term)
        factor = FloatField()
        factor.setRange(-1e12, 1e12)
        factor.setSingleStep(0.1)
        factor.setValue(term.factor if term is not None else 1.0)
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setCellWidget(row, 0, source)
        self._table.setCellWidget(row, 1, factor)
        self._rows.append(_TermRow(source, factor))

    def _on_remove_term(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            row = self._table.rowCount() - 1
        if row < 0:
            return
        self._table.removeRow(row)
        del self._rows[row]

    def term_count(self) -> int:
        return len(self._rows)

    def set_term(self, row: int, source: str, ref_id: int, factor: float) -> None:
        """Point term ``row`` at ``source`` ``ref_id`` with ``factor`` (for scripts and tests)."""
        cells = self._rows[row]
        index = cells.source.findData(_key(source, ref_id))
        if index < 0:
            raise ValueError(f"{source} {ref_id} is not offered.")
        cells.source.setCurrentIndex(index)
        cells.factor.setValue(factor)

    def set_name(self, name: str) -> None:
        self._name.setText(name)

    def set_type(self, combination_type: str) -> None:
        self._type.setCurrentIndex(self._type.findData(combination_type))

    # ── apply ────────────────────────────────────────────────────────
    def read(self) -> LoadCombination:
        """The combination the form describes (raises ``ValidationError``)."""
        cid = self.selected_id()
        if cid is None:
            raise ValueError("No combination is selected.")
        terms = []
        for cells in self._rows:
            data = cells.source.currentData()
            if data is None:
                continue
            source, ref_id = str(data).split(":")
            terms.append(
                CombinationTerm(
                    source=source,  # type: ignore[arg-type]
                    ref_id=int(ref_id),
                    factor=float(cells.factor.value()),
                )
            )
        return LoadCombination(
            id=cid,
            name=self._name.text().strip(),
            combination_type=self._type.currentData(),
            terms=terms,
        )

    def apply(self) -> bool:
        """Check the form and apply it as one undo step; False when refused."""
        project = self._vm.project
        if project is None or self.selected_id() is None:
            return False
        try:
            combo = self.read()
        except (ValidationError, ValueError) as exc:
            self._message.show_message(f"Combination rejected: {exc}", "error")
            return False
        trial = project.model_copy(
            update={
                "combinations": [combo if c.id == combo.id else c for c in project.combinations]
            }
        )
        problems = combination_problems(trial, combo)
        if problems:
            self._message.show_message("Combination rejected:\n" + "\n".join(problems), "error")
            return False
        self._vm.apply_command(UpdateCombinationCommand(self._vm, combo))
        warnings = superposition_warnings(project, combo)
        if warnings:
            self._message.show_message("\n".join(warnings), "warning")
        else:
            self._message.show_message(f"Combination '{combo.name}' updated.")
        return True

    def message_text(self) -> str:
        return self._message.text()

    def message_level(self) -> str:
        return self._message.level

    # ── add / copy / delete ─────────────────────────────────────────
    def _on_add(self) -> None:
        project = self._vm.project
        if project is None:
            return
        cases = _combinable_cases(project)
        if not cases:
            self._message.show_message(
                "Define a Static or Response Spectrum case first (Analyze → Cases…): "
                "a combination combines their results.",
                "error",
            )
            return
        new_id = project.next_combination_id()
        combo = LoadCombination(
            id=new_id, name=f"COMB{new_id}", terms=[CombinationTerm(ref_id=cases[0].id)]
        )
        self._vm.apply_command(AddCombinationsCommand(self._vm, [combo]))
        self.select(new_id)

    def _on_copy(self) -> None:
        project = self._vm.project
        combo = self._selected()
        if project is None or combo is None:
            return
        new_id = project.next_combination_id()
        copy = combo.model_copy(update={"id": new_id, "name": f"{combo.name} copy"}, deep=True)
        self._vm.apply_command(
            AddCombinationsCommand(self._vm, [copy], text=f"Copy load combination '{combo.name}'")
        )
        self.select(new_id)

    def _on_delete(self) -> None:
        project = self._vm.project
        combo = self._selected()
        if project is None or combo is None:
            return
        users = combinations_using_combination(project, combo.id)
        if users:
            names = ", ".join(f"'{u.name}'" for u in users)
            self._message.show_message(
                f"'{combo.name}' is included in {names}: remove it there first.", "error"
            )
            return
        self._vm.apply_command(DeleteCombinationsCommand(self._vm, {combo.id}))

    # ── ASCE 7-16 generator ─────────────────────────────────────────
    def _on_generate(self) -> None:
        project = self._vm.project
        if project is None:
            return
        cases = _combinable_cases(project)
        if not cases:
            self._message.show_message(
                "Define the load cases first: the generator combines Static and "
                "Response Spectrum cases tagged Dead, Live, Wind, …",
                "error",
            )
            return
        dlg = Asce7GeneratorDialog(cases, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.generate_asce7(dlg.roles(), envelope=dlg.envelope_wanted())

    def generate_asce7(self, roles: dict[str, list[int]], *, envelope: bool = True) -> int:
        """Add the ASCE 7-16 LRFD combinations for ``roles`` as one undo step.

        Returns how many combinations were added (the envelope included).
        """
        project = self._vm.project
        if project is None:
            return 0
        peaks = [c.id for c in project.analyses if c.type == "ResponseSpectrum"]
        generated = asce7_16_lrfd(roles, peak_cases=peaks)
        if not generated:
            self._message.show_message(
                "Nothing generated: every ASCE 7-16 combination needs a Dead (D) case.",
                "error",
            )
            return 0
        next_id = project.next_combination_id()
        combos = []
        for offset, (name, terms) in enumerate(generated):
            combos.append(LoadCombination(id=next_id + offset, name=name, terms=terms))
        if envelope and len(combos) > 1:
            combos.append(
                LoadCombination(
                    id=next_id + len(combos),
                    name=ENVELOPE_NAME,
                    combination_type="Envelope",
                    terms=[CombinationTerm(source="combination", ref_id=c.id) for c in combos],
                )
            )
        self._vm.apply_command(
            AddCombinationsCommand(
                self._vm, combos, text=f"Generate {len(combos)} ASCE 7-16 LRFD combination(s)"
            )
        )
        self.select(combos[-1].id)
        self._message.show_message(f"Added {len(combos)} ASCE 7-16 LRFD combination(s).")
        return len(combos)


class Asce7GeneratorDialog(FittedDialog):
    """Tag each case with its load role for the ASCE 7-16 LRFD generator."""

    def __init__(self, cases: list[Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ASCE 7-16 LRFD Combinations")
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Give each case the load it carries. Section 2.3.1: 1.4D; 1.2D + 1.6L + "
            "0.5(Lr or S or R); 1.2D + 1.6(Lr or S or R) + (L or 0.5W); 1.2D + 1.0W + L + "
            "0.5(Lr or S or R); 1.2D + 1.0E + L + 0.2S; 0.9D + 1.0W; 0.9D + 1.0E. Wind and "
            "static earthquake cases are applied in both signs. The live load factor in the "
            "last three is 1.0 (the 0.5 exception depends on occupancy)."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self._boxes: dict[int, QComboBox] = {}
        for case in cases:
            box = QComboBox()
            box.addItem("(not used)", None)
            for role in LOAD_ROLES:
                box.addItem(LOAD_ROLE_LABELS[role], role)
            guess = guess_load_role(case.name)
            if guess is not None:
                box.setCurrentIndex(box.findData(guess))
            form.addRow(f"{case.name or case.id} [{case.type}]:", box)
            self._boxes[case.id] = box
        layout.addLayout(form)
        self._envelope = QCheckBox(f"Also add an envelope of them ('{ENVELOPE_NAME}')")
        self._envelope.setChecked(True)
        layout.addWidget(self._envelope)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_role(self, case_id: int, role: str | None) -> None:
        box = self._boxes[case_id]
        box.setCurrentIndex(0 if role is None else box.findData(role))

    def roles(self) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for case_id, box in self._boxes.items():
            role = box.currentData()
            if role is not None:
                out.setdefault(str(role), []).append(case_id)
        return out

    def envelope_wanted(self) -> bool:
        return self._envelope.isChecked()
