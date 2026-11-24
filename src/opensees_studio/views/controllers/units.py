"""Display units: Options → Set Display Units and the picker of the status bar."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QComboBox, QInputDialog, QMessageBox

from opensees_studio.core import UnitConverter, UnitSystem
from opensees_studio.views.controllers.shell import Shell


class UnitsController(QObject):
    """The system every result is shown in, and the two ways to pick it.

    The choice is ``project.meta.display_units``; the model keeps
    ``project.meta.units`` and the numbers an engineer typed are never
    rewritten. :attr:`combo` is the picker the window puts at the right of
    the status bar; it and Options → Set Display Units drive the same state.

    ``refresh`` re-draws what shows a number with the new conversion (the
    results panel, the open post-processing view, the member windows): the
    window owns those, so it is the window's hook.
    """

    def __init__(self, shell: Shell, *, refresh: Callable[[UnitConverter], None]) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._refresh = refresh
        #: SAP2000-style bottom-right unit picker (the window adds it to the status bar).
        self.combo = QComboBox()
        self.combo.setToolTip(
            "Display units — results, diagrams and tables convert to this "
            "system. The model keeps the units its values were entered in."
        )
        for u in UnitSystem:
            self.combo.addItem(u.value, u)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)

    def current(self) -> UnitSystem:
        """The system results are shown in (the model's own when none was picked)."""
        if self._vm.project is None:
            return UnitSystem.SI_M_N
        meta = self._vm.project.meta
        return meta.display_units if meta.display_units is not None else meta.units

    def pick(self) -> None:
        """Options → Set Display Units — SAP2000 parity.

        The selection is stored in ``project.meta.display_units`` and converts
        every number a result view shows (force diagrams, displacements,
        tables, curves). The model keeps ``project.meta.units``: the values an
        engineer typed are never rewritten.
        """
        if self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Set Display Units",
                "Open or create a project first.",
            )
            return
        choices = [u.value for u in UnitSystem]
        current_value = self.current().value
        current_idx = choices.index(current_value)
        choice, ok = QInputDialog.getItem(
            self._window,
            "Set Display Units",
            "Unit system:",
            choices,
            current=current_idx,
            editable=False,
        )
        if not ok:
            return
        new_units = next(u for u in UnitSystem if u.value == choice)
        if new_units is self.current():
            return
        self.set_display(new_units)

    def _on_combo_changed(self, _idx: int) -> None:
        """Status-bar unit picker → ``project.meta.display_units``.

        Qt stores the userData as a bare string (UnitSystem inherits
        from str), so we re-cast to the enum before writing through
        and logging. The model's own system is untouched, and every view
        that shows a number is refreshed with the new conversion.
        """
        if self._vm.project is None:
            return

        raw = self.combo.currentData()
        if raw is None:
            return
        chosen = raw if isinstance(raw, UnitSystem) else UnitSystem(str(raw))
        if chosen is self.current():
            return
        self.set_display(chosen)

    def set_display(self, chosen: UnitSystem) -> None:
        """Change the display system and refresh everything that shows a number."""
        if self._vm.project is None:
            return
        self._vm.project.meta.display_units = chosen
        self._vm.mark_dirty()
        self.sync_combo()
        self._shell.log(f"Display units set to {chosen.value}.")
        self.apply()

    def apply(self) -> None:
        """Re-render every result view in the project's current display units.

        The model is untouched — OpenSees numbers do not move — but each number
        read off a diagram, table or curve is converted, so a unit change is
        visible without re-running anything.
        """
        if self._vm.project is None:
            return
        converter = UnitConverter.of(self._vm.project.meta)
        self._refresh(converter)
        self._shell.log(
            f"Displayed values converted to {converter.target.value} (model units unchanged).",
        )

    def sync_combo(self) -> None:
        """Reflect the project's current display units in the status-bar combo.

        Called after project load / menu-based unit change so the
        status-bar widget stays consistent with the model state. When the
        display system differs from the model's, the tooltip says so — the
        typed values are in the model's system, not in the picker's.
        """
        if self._vm.project is None:
            return
        target = self.current()
        idx = self.combo.findData(target)
        if idx >= 0 and idx != self.combo.currentIndex():
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(idx)
            self.combo.blockSignals(False)
        model = self._vm.project.meta.units
        tooltip = (
            "Display units — results, diagrams and tables convert to this "
            "system. The model keeps the units its values were entered in."
        )
        if target is not model:
            tooltip += f"  Model units: {model.value} — typed values are unchanged."
        self.combo.setToolTip(tooltip)
