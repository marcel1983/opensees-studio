"""The guided seven-stage steel-design workflow dialog."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from opensees_studio.core import Project
from opensees_studio.core.design.settings import DesignSettings
from opensees_studio.views.dialogs.steel_workflow import SteelWorkflowDialog


class _Controller:
    """Records the calls the workflow makes on the main window."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        def record() -> None:
            self.calls.append(name)

        return record


@pytest.mark.gui
def test_the_workflow_has_seven_stages_and_navigates(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = SteelWorkflowDialog(Project(), lambda: {}, _Controller())
    qtbot.addWidget(dialog)

    assert dialog._list.count() == 7
    assert dialog._list.currentRow() == 0
    assert dialog._pages.currentIndex() == 0
    assert dialog._statuses[0] == "PENDIENTE"
    assert dialog._statuses[4] == "OK"  # no seismic system: nothing to review

    dialog._next_stage()
    assert dialog._list.currentRow() == 1
    assert dialog._pages.currentIndex() == 1

    dialog._previous()
    assert dialog._list.currentRow() == 0
    assert dialog._pages.currentIndex() == 0


@pytest.mark.gui
def test_stage_buttons_call_the_existing_dialogs(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller = _Controller()
    dialog = SteelWorkflowDialog(Project(), lambda: {}, controller)
    qtbot.addWidget(dialog)

    dialog._buttons[0][0].click()
    assert controller.calls == ["edit_steel_settings"]

    dialog._buttons[4][0].click()
    assert controller.calls[-1] == "open_gussets"


@pytest.mark.gui
def test_the_design_menu_opens_the_workflow(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.dialogs import steel_workflow
    from opensees_studio.views.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window._vm.new_project(ndm=2, ndf=3)
    opened: list[object] = []

    def fake_exec(self):  # type: ignore[no-untyped-def]
        opened.append(self)
        return 0

    monkeypatch.setattr(steel_workflow.SteelWorkflowDialog, "exec", fake_exec)
    window._act_steel_workflow.trigger()

    assert len(opened) == 1


@pytest.mark.gui
def test_design_settings_are_reflected_in_the_first_stage(qtbot) -> None:  # type: ignore[no-untyped-def]
    project = Project()
    project.design = DesignSettings(method="ASD", seismic_system="SMF", p_delta=True)
    dialog = SteelWorkflowDialog(project, lambda: {}, _Controller())
    qtbot.addWidget(dialog)

    assert dialog._statuses[0] == "OK"
    summary = dialog._summaries[0].text()
    assert "ASD" in summary
    assert "SMF" in summary
    assert "on" in summary  # B1 P-delta
