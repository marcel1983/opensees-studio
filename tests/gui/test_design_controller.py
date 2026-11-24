"""The Design menu lives in ``DesignController``, which needs no ``MainWindow``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMainWindow

from opensees_studio.core.design.connections import RbsConnection
from opensees_studio.viewmodels import ProjectViewModel
from opensees_studio.views.actions.design import DESIGN_ACTIONS
from opensees_studio.views.controllers import Shell
from opensees_studio.views.controllers.design import DesignController
from opensees_studio.views.dialogs.connections import ConnectionsDialog

pytestmark = pytest.mark.gui


def _portal():  # type: ignore[no-untyped-def]
    from tests.integration.test_steel_design_run import _portal as portal

    return portal()


def test_the_window_owns_one_controller_and_every_design_command_points_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    assert isinstance(window.design, DesignController)
    assert window.design.parent() is window
    assert len(DESIGN_ACTIONS) == 19
    for spec in DESIGN_ACTIONS:
        # The names the ribbon, the icons and the help table use still find them.
        assert getattr(window, spec.attribute) is window.action(spec.id), spec.id
        assert callable(getattr(window.design, spec.handler.partition(".")[2])), spec.id

    window._vm.close()
    window._refresh_action_enablement()
    assert [s.id for s in DESIGN_ACTIONS if window.action(s.id).isEnabled()] == []
    window._vm.new_project(ndm=3, ndf=6)
    window._refresh_action_enablement()
    assert [s.id for s in DESIGN_ACTIONS if not window.action(s.id).isEnabled()] == []
    window._help_controller.uninstall()


def test_a_command_runs_with_a_shell_and_two_hooks_and_no_main_window(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    project = _portal()
    vm.adopt(project)
    log: list[str] = []
    asked: list[str] = []

    def no_canvas():  # type: ignore[no-untyped-def]
        raise AssertionError("Design → Connections does not look at the viewport")

    controller = DesignController(
        Shell(window=parent, vm=vm, canvas=no_canvas, log=log.append, refresh_actions=lambda: None),
        results=lambda: asked.append("results") or {},
        show_ratios=lambda *a, **k: asked.append("ratios"),
    )
    connection = RbsConnection(id=1, beam_element_id=2, column_element_id=1, a=4.5, b=13.0, c=1.0)
    monkeypatch.setattr(ConnectionsDialog, "exec", lambda self: int(QDialog.DialogCode.Accepted))
    monkeypatch.setattr(ConnectionsDialog, "connections", lambda self: [connection])

    controller.connections()
    assert project.connections == [connection]
    assert log == ["1 RBS connection(s)."]
    assert asked == []  # editing connections reads no results and paints nothing
    vm.undo_stack.undo()
    assert project.connections == []


def test_display_steel_ratios_reads_the_results_hook_and_explains_when_empty(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    vm.adopt(_portal())
    asked: list[str] = []
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    controller = DesignController(
        Shell(
            window=parent,
            vm=vm,
            canvas=lambda: None,  # type: ignore[arg-type, return-value]
            log=lambda _text: None,
            refresh_actions=lambda: None,
        ),
        results=lambda: asked.append("results") or {},
        show_ratios=lambda *a, **k: asked.append("ratios"),
    )
    controller.steel_ratios()
    # No results: it says why and paints nothing.
    assert asked == ["results"]
    assert len(told) == 1
