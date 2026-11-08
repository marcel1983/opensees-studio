"""Design → Connection Checks: the Chapter J dialog and the undoable action."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog

from opensees_studio.core.design.chapter_j_model import ChapterJCheck
from opensees_studio.views.dialogs.chapter_j import ChapterJDialog
from opensees_studio.views.main_window import MainWindow


def _project():  # type: ignore[no-untyped-def]
    from tests.integration.test_steel_design_run import _portal

    return _portal()


@pytest.mark.gui
def test_the_dialog_adds_a_chapter_j_check(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = ChapterJDialog(_project())
    qtbot.addWidget(dialog)
    dialog._type.setCurrentIndex(dialog._type.findData("fillet_weld"))
    dialog._name.setText("Weld")
    dialog._demand.setValue(40.0)
    dialog._add()
    checks = dialog.checks()
    assert len(checks) == 1
    assert checks[0].check_type == "fillet_weld"
    assert checks[0].name == "Weld"
    assert checks[0].demand == pytest.approx(40.0)
    assert checks[0].fexx and checks[0].fexx > 0.0


@pytest.mark.gui
def test_the_action_stores_and_undoes_the_chapter_j_checks(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project = _project()
    window = MainWindow()
    qtbot.addWidget(window)
    window._vm.adopt(project)
    check = ChapterJCheck(
        id=1,
        name="Weld",
        check_type="fillet_weld",
        demand=40.0,
        fexx=70.0,
        weld_leg=0.25,
        weld_length=10.0,
    )
    monkeypatch.setattr(ChapterJDialog, "exec", lambda self: int(QDialog.DialogCode.Accepted))
    monkeypatch.setattr(ChapterJDialog, "checks", lambda self: [check])
    window._on_chapter_j()
    assert project.chapter_j_checks == [check]
    window._vm.undo_stack.undo()
    assert project.chapter_j_checks == []
