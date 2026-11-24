"""The display units live in ``UnitsController`` and run with no ``MainWindow``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QInputDialog, QMainWindow, QMessageBox

from opensees_studio.core import Node, Project, UnitConverter, UnitSystem
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.controllers.units import UnitsController

pytestmark = pytest.mark.gui


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
    """A controller on a bare window; ``refreshed`` is what the window would re-draw."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel(parent)
    if project is not None:
        vm.adopt(project)
    log: list[str] = []
    refreshed: list[UnitConverter] = []
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: None,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    return UnitsController(shell, refresh=refreshed.append), vm, refreshed, log


def _project() -> Project:
    project = Project(ndm=3, ndf=6)
    project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    return project


def test_the_window_owns_one_controller_and_set_display_units_reaches_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.units, UnitsController)
    assert mw.units.parent() is mw
    assert mw._act_set_units is mw.action("options.set_units")
    # The picker sits in the status bar, one entry per system.
    assert mw.units.combo.window() is mw
    assert mw.units.combo.count() == len(list(UnitSystem))


def test_without_a_project_there_is_nothing_to_change(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    units, _vm, refreshed, log = _controller(qtbot, None)
    told: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text, *a, **k: told.append(text))

    assert units.current() is UnitSystem.SI_M_N
    units.pick()
    units.set_display(UnitSystem.US_IN_KIP)
    units.apply()
    units.sync_combo()

    assert told == ["Open or create a project first."]
    assert refreshed == [] and log == []


def test_the_display_system_is_the_models_own_until_one_is_picked(qtbot) -> None:  # type: ignore[no-untyped-def]
    units, vm, refreshed, log = _controller(qtbot, _project())
    assert vm.project is not None
    assert units.current() is vm.project.meta.units

    units.set_display(UnitSystem.US_IN_KIP)

    assert vm.project.meta.display_units is UnitSystem.US_IN_KIP
    assert vm.project.meta.units is UnitSystem.SI_M_N  # the typed values stay
    assert units.current() is UnitSystem.US_IN_KIP
    assert vm.is_dirty
    assert units.combo.currentData() == UnitSystem.US_IN_KIP
    assert "Model units: " in units.combo.toolTip()
    assert [c.target for c in refreshed] == [UnitSystem.US_IN_KIP]
    assert log[0] == f"Display units set to {UnitSystem.US_IN_KIP.value}."


def test_the_picker_of_the_status_bar_changes_the_system_once(qtbot) -> None:  # type: ignore[no-untyped-def]
    units, _vm, refreshed, _log = _controller(qtbot, _project())
    units.sync_combo()

    units.combo.setCurrentIndex(units.combo.findData(UnitSystem.US_FT_KIP))
    assert units.current() is UnitSystem.US_FT_KIP
    assert len(refreshed) == 1

    # Syncing the picker to the state it already shows changes nothing.
    units.sync_combo()
    assert len(refreshed) == 1


def test_the_menu_dialog_changes_it_only_when_accepted_with_another_system(
    qtbot, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    units, _vm, refreshed, _log = _controller(qtbot, _project())
    answers = [
        (UnitSystem.US_IN_KIP.value, False),  # cancelled
        (UnitSystem.SI_M_N.value, True),  # the system already shown
        (UnitSystem.US_IN_KIP.value, True),
    ]
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: answers.pop(0))

    units.pick()
    units.pick()
    assert refreshed == [] and units.current() is UnitSystem.SI_M_N

    units.pick()
    assert units.current() is UnitSystem.US_IN_KIP
    assert units.combo.currentData() == UnitSystem.US_IN_KIP
    assert len(refreshed) == 1
