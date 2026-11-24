"""File → Import lives in ``ImportsController``."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.imports import ImportsController
from opensees_studio.views.controllers.shell import Shell

pytestmark = pytest.mark.gui

PORTAL = Path(__file__).parents[1] / "fixtures" / "s2k" / "portal_2d.s2k"
COMMANDS = ("dxf", "s3d", "s2k", "ifc", "tcl")


def _controller(qtbot, *, discard: bool):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    log: list[str] = []
    asked: list[str] = []

    def confirm(action: str) -> bool:
        asked.append(action)
        return discard

    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: SimpleNamespace(),  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    controller = ImportsController(
        shell, confirm_discard=confirm, apply_view_settings=lambda: asked.append("view")
    )
    return controller, vm, log, asked


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.actions import ALL_ACTIONS
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.imports, ImportsController)
    assert mw.imports.parent() is mw
    handlers = {spec.id: spec.handler for spec in ALL_ACTIONS}
    for name in COMMANDS:
        assert handlers[f"file.import_{name}"] == f"imports.{name}"
        assert getattr(mw, f"_act_import_{name}") is mw.action(f"file.import_{name}")
    mw._help_controller.uninstall()


def test_a_model_replaces_the_project_and_takes_its_view(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, asked = _controller(qtbot, discard=True)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(PORTAL), ""))
    )
    controller.s2k()
    # It asked about unsaved work first and had the window adopt the saved viewport after.
    assert asked == ["Importing a SAP2000 text file", "view"]
    assert vm.project is not None and vm.project.nodes
    assert log[0].startswith("Imported portal_2d.s2k (")


def test_keeping_the_unsaved_work_imports_nothing(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, asked = _controller(qtbot, discard=False)

    def no_dialog(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AssertionError("the file dialog must not open")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(no_dialog))
    controller.s2k()
    controller.ifc()
    assert asked == ["Importing a SAP2000 text file", "Importing an IFC file"]
    assert vm.project is None
    assert log == []


def test_a_drawing_needs_a_project_to_go_into(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, _vm, _log, asked = _controller(qtbot, discard=True)
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    controller.dxf()
    assert told == ["Open or create a project first."]
    # A drawing adds to the project: nothing is discarded, so nothing is asked.
    assert asked == []
