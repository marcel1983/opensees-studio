"""The model lock lives in ``ModelLockController`` and runs with no ``MainWindow``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMessageBox

from opensees_studio.commands import AddNodesCommand, SetDesignSettingsCommand
from opensees_studio.core import Node, Project
from opensees_studio.core.design.settings import DesignSettings
from opensees_studio.services.results import StaticResults
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.viewmodels.results_session import ResultsSession
from opensees_studio.views.controllers.model_lock import ModelLockController
from opensees_studio.views.controllers.shell import Shell

pytestmark = pytest.mark.gui

#: The real question: conftest answers it with Yes for every other test.
_ASK = ModelLockController.confirm_unlock


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
    """A controller on a bare window, wired to the undo stack as the window wires it."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    # A child of the window, as in the application: the undo stack empties itself
    # when it is destroyed, and tells the controller, which must still be there.
    vm = ProjectViewModel(parent)
    if project is not None:
        vm.adopt(project)
    action = QAction("Lock Model", parent)
    action.setCheckable(True)
    results = ResultsSession()
    log: list[str] = []
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: None,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    controller = ModelLockController(
        shell, results=results, drop_results=results.clear, action=lambda _id: action
    )
    action.triggered.connect(controller.toggle)
    vm.undo_stack.indexChanged.connect(controller.on_undo_index_changed)
    return controller, vm, results, action, log, parent


def _project() -> Project:
    project = Project(ndm=3, ndf=6)
    project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    return project


def _add_node(vm: ProjectViewModel, node_id: int) -> None:
    vm.apply_command(AddNodesCommand(vm, [Node(id=node_id, coords=(float(node_id), 0, 0))]))


def test_the_window_owns_one_controller_and_lock_model_reaches_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.model_lock, ModelLockController)
    assert mw.model_lock.parent() is mw
    action = mw.action("options.lock_model")
    assert mw._act_lock_model is action and action.isCheckable()
    # The padlock sits in the status bar and says what the command says.
    assert mw.model_lock.button.window() is mw
    assert mw.model_lock.button.toolTip() == action.toolTip() != ""
    # Nothing to lock without a project.
    mw._refresh_action_enablement()
    assert not action.isEnabled() and not mw.model_lock.button.isEnabled()
    mw._vm.new_project(ndm=3, ndf=6)
    mw._refresh_action_enablement()
    assert action.isEnabled() and mw.model_lock.button.isEnabled()
    mw.model_lock.button.click()
    assert mw.model_lock.locked and action.isChecked()
    mw._help_controller.uninstall()


def test_no_project_nothing_to_lock(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, _vm, _results, action, _log, _parent = _controller(qtbot, None)
    controller.set_locked(True)
    assert not controller.locked
    assert not action.isChecked() and controller.button.text() == "Unlocked"


def test_results_lock_once_and_a_test_can_switch_that_off(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, _vm, _results, action, log, _parent = _controller(qtbot, _project())
    controller.after_analysis = False
    controller.lock_for_results()
    assert not controller.locked and log == []
    controller.after_analysis = True
    controller.lock_for_results()
    controller.lock_for_results()
    assert controller.locked and action.isChecked() and controller.button.isChecked()
    assert controller.button.text() == "Locked"
    assert len(log) == 1 and log[0].startswith("Model locked: it has analysis results")


def test_a_refused_edit_is_taken_back_and_an_accepted_one_drops_the_results(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch
) -> None:
    controller, vm, results, action, log, parent = _controller(qtbot, _project())
    answers: list[bool] = []
    asked: list[int] = []

    def _answer(_lock: ModelLockController) -> bool:
        asked.append(1)
        return answers.pop(0)

    monkeypatch.setattr(ModelLockController, "confirm_unlock", _answer)
    results.latest = StaticResults(case_id=1, case_name="DEAD", n_steps=1)
    controller.lock_for_results()

    # What no result depends on is not asked about.
    vm.apply_command(SetDesignSettingsCommand(vm, DesignSettings(method="ASD")))
    assert asked == [] and controller.locked

    answers.append(False)
    _add_node(vm, 2)
    assert asked == [1]
    assert [n.id for n in vm.project.nodes] == [1]
    assert controller.locked and results.latest is not None
    assert parent.statusBar().currentMessage() == "The model is locked: the change was not made."

    answers.append(True)
    _add_node(vm, 2)
    assert [n.id for n in vm.project.nodes] == [1, 2]
    assert not controller.locked and not action.isChecked()
    assert results.latest is None
    assert log[-1] == "Model unlocked: the results of this session were discarded."
    _add_node(vm, 3)  # unlocked: nobody is asked
    assert asked == [1, 1]


def test_lock_model_by_hand_and_the_unlock_question(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, _vm, results, action, log, _parent = _controller(qtbot, _project())
    asked: list[str] = []
    answer = [QMessageBox.StandardButton.No]

    def _question(_parent, _title, text, *_args):  # type: ignore[no-untyped-def]
        asked.append(text)
        return answer[0]

    monkeypatch.setattr(ModelLockController, "confirm_unlock", _ASK)
    monkeypatch.setattr(QMessageBox, "question", _question)
    action.trigger()
    assert controller.locked and log[-1] == "Model locked."

    # Unticking asks; No leaves the lock, and the command, as they were.
    action.trigger()
    assert asked[-1] == "The model is locked. Unlock it to change it?"
    assert controller.locked and action.isChecked() and controller.button.isChecked()

    # With results the question says that they go with the lock.
    results.latest = StaticResults(case_id=1, case_name="DEAD", n_steps=1)
    answer[0] = QMessageBox.StandardButton.Yes
    action.trigger()
    assert "discard the results of this session" in asked[-1]
    assert not controller.locked and results.latest is None
