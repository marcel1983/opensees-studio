"""File → New Model and the wizards live in ``GeneratorsController``, with no ``MainWindow``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QMainWindow

from opensees_studio.core import UnitSystem
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.generators import (
    NEW_MODEL_UNITS_KEY,
    GeneratorsController,
)
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import FrameWizard
from opensees_studio.views.dialogs.new_model import NewModelDialog

pytestmark = pytest.mark.gui


class _Canvas:
    def __init__(self) -> None:
        self.reframed = 0

    def reframe(self) -> None:
        self.reframed += 1


class _Rig:
    """A controller on a bare window, and a record of what it asked of the window."""

    def __init__(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        self.parent = QMainWindow()
        qtbot.addWidget(self.parent)
        self.vm = ProjectViewModel(self.parent)
        self.canvas = _Canvas()
        self.log: list[str] = []
        self.calls: list[str] = []
        self.discard = True
        shell = Shell(
            window=self.parent,
            vm=self.vm,
            canvas=lambda: self.canvas,  # type: ignore[arg-type, return-value]
            log=self.log.append,
            refresh_actions=lambda: None,
        )

        def _confirm(action: str) -> bool:
            self.calls.append(f"confirm: {action}")
            return self.discard

        self.generators = GeneratorsController(
            shell,
            confirm_discard=_confirm,
            grid_wizard=lambda: self.calls.append("grid_wizard"),
            front_view=lambda: self.calls.append("front_view"),
        )


class _Numbers:
    """The New Model dialog as a template reads it."""

    def beam_numbers(self) -> tuple[int, float]:
        return 2, 5.0


def test_the_window_owns_one_controller_and_the_menus_reach_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.generators, GeneratorsController) and mw.generators.parent() is mw
    assert mw._act_new_model is mw.action("file.new_model")
    assert mw._act_frame_wizard is mw.action("define.frame_wizard")
    assert mw._act_truss_wizard is mw.action("define.truss_wizard")
    assert mw._act_warehouse_wizard is mw.action("define.warehouse_wizard")
    # A wizard builds into the open project: none, no wizard.
    assert not mw.action("define.frame_wizard").isEnabled()
    mw._vm.new_project()
    assert mw.action("define.frame_wizard").isEnabled()


def test_a_beam_template_is_one_undo_step_seen_face_on(qtbot) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot)

    rig.generators.start_template("beam", UnitSystem.US_FT_KIP, _Numbers())

    project = rig.vm.project
    assert project is not None and project.meta.units is UnitSystem.US_FT_KIP
    assert len(project.elements) == 2 and len(project.sections) == 1
    assert rig.vm.undo_stack.count() == 1
    assert rig.calls == ["front_view"] and rig.canvas.reframed == 1
    assert rig.log[0].startswith("New model: ")

    rig.generators.start_template("grid", UnitSystem.SI_M_N, _Numbers())
    assert rig.calls[-1] == "grid_wizard"
    assert rig.vm.project is not project and not rig.vm.project.elements


def test_new_model_asks_before_it_replaces_the_project(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot)
    rig.vm.new_project()
    kept = rig.vm.project
    monkeypatch.setattr(NewModelDialog, "exec", lambda _self: QDialog.DialogCode.Rejected)

    rig.generators.new_model()
    assert rig.calls == [] and rig.vm.project is kept  # cancelled: nothing asked

    monkeypatch.setattr(NewModelDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(NewModelDialog, "units", lambda _self: UnitSystem.US_IN_KIP)
    monkeypatch.setattr(NewModelDialog, "template", lambda _self: "grid")
    rig.discard = False
    rig.generators.new_model()
    assert rig.calls == ["confirm: Creating a new model"] and rig.vm.project is kept

    rig.discard = True
    rig.generators.new_model()
    assert rig.vm.project is not kept and rig.calls[-1] == "grid_wizard"
    assert rig.vm.project.meta.units is UnitSystem.US_IN_KIP
    try:
        assert QSettings().value(NEW_MODEL_UNITS_KEY) == UnitSystem.US_IN_KIP.value
    finally:
        QSettings().remove(NEW_MODEL_UNITS_KEY)  # the next New Model starts in SI again


def test_new_2d_frame_leaves_the_empty_project_when_the_wizard_is_cancelled(
    qtbot, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot)
    monkeypatch.setattr(FrameWizard, "exec", lambda _self: QDialog.DialogCode.Rejected)

    rig.discard = False
    rig.generators.new_2d_frame()
    assert rig.vm.project is None

    rig.discard = True
    rig.generators.new_2d_frame()
    project = rig.vm.project
    assert project is not None and (project.ndm, project.ndf) == (2, 3)
    assert not project.elements and rig.log == ["New 2D frame project (ndm = 2, ndf = 3)."]
    assert rig.calls == ["confirm: Creating a new 2D frame"] * 2


def test_a_wizard_without_a_project_says_so(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QMessageBox

    rig = _Rig(qtbot)
    told: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text, *a, **k: told.append(text))

    rig.generators.portal_frame()
    rig.generators.create_truss()
    rig.generators.create_warehouse()
    rig.generators.create_building()

    assert told == ["Open or create a project first."] * 4
    assert rig.log == [] and rig.canvas.reframed == 0
