"""File → Export lives in ``ExportsController``.

What each export writes is pinned in ``test_export_script.py``,
``test_export_report.py``, ``test_calc_memory_gui.py`` and the IFC and SAP2000
text tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox

from opensees_studio.core import ElasticBeamColumn, ElasticSection, Node, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.exports import ExportsController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.report_options import ReportOptionsDialog

pytestmark = pytest.mark.gui

COMMANDS = {
    "file.export_script": "exports.script",
    "file.export_ifc": "exports.ifc",
    "file.export_s2k": "exports.s2k",
    "file.export_report": "exports.report",
    "file.calc_memory": "exports.calc_memory",
}


def _project() -> Project:
    project = Project(ndm=3, ndf=6)
    project.sections.append(
        ElasticSection(id=1, name="S", E=200e9, A=0.01, Iz=1e-5, Iy=1e-5, G=80e9, J=1e-6)
    )
    project.nodes.extend([Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0))])
    project.elements.append(ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1))
    return project


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport, no results store."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    if project is not None:
        vm.adopt(project)
    log: list[str] = []
    asked: list[str] = []
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: SimpleNamespace(),  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    controller = ExportsController(
        shell,
        results=lambda: asked.append("results") or {},
        report_results=lambda: asked.append("report") or [],
    )
    return controller, log, asked


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.actions import ALL_ACTIONS
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.exports, ExportsController)
    assert mw.exports.parent() is mw
    handlers = {spec.id: spec.handler for spec in ALL_ACTIONS}
    for action_id, handler in COMMANDS.items():
        assert handlers[action_id] == handler
        # Nothing to export without a project.
        assert not mw.action(action_id).isEnabled(), action_id
    mw._vm.new_project(ndm=3, ndf=6)
    mw._refresh_action_enablement()
    assert all(mw.action(action_id).isEnabled() for action_id in COMMANDS)
    mw._help_controller.uninstall()


def test_the_script_of_a_model_reads_no_results(qtbot, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    controller, log, asked = _controller(qtbot, _project())
    target = tmp_path / "beam.py"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    controller.script()
    assert "ops.model(" in target.read_text(encoding="utf-8")
    assert log == [f"Exported OpenSees script: {target}"]
    assert asked == []


def test_the_report_takes_its_results_from_the_window(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, log, asked = _controller(qtbot, _project())
    monkeypatch.setattr(ReportOptionsDialog, "exec", lambda self: int(QDialog.DialogCode.Rejected))
    controller.report()
    # The dialog lists what there is to report, so the results are asked for first.
    assert asked == ["report"]
    assert log == []


def test_every_export_needs_a_project(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, log, asked = _controller(qtbot, None)
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, title, _text, *a, **k: told.append(title)
    )
    controller.script()
    controller.ifc()
    controller.s2k()
    controller.report()
    controller.calc_memory()
    assert told == [
        "Export script",
        "Export IFC",
        "Export SAP2000 Text",
        "Export report",
        "Calculation memory",
    ]
    assert (log, asked) == ([], [])
