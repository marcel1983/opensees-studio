"""Duplicates, merge, divide, join and mesh live in ``ModelToolsController``.

What each command does is pinned in ``test_duplicates_gui.py``,
``test_merge_and_divide.py``, ``test_join_frames_gui.py`` and ``test_mesh_gui.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox

from opensees_studio.core import ElasticBeamColumn, ElasticSection, Node, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.model_tools import ModelToolsController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import DuplicatesDialog

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "edit.check_duplicates": "_act_check_duplicates",
    "edit.merge_joints": "_act_merge_joints",
    "edit.divide_frames": "_act_divide_frames",
    "edit.join_frames": "_act_join_frames",
    "edit.mesh": "_act_mesh",
    "edit.delete": "_act_delete",
    "edit.table_editing": "_act_table_editing",
}


def _project() -> Project:
    """Two members in a straight line, and a joint drawn twice at the far end."""
    project = Project(ndm=3, ndf=6)
    project.sections.append(
        ElasticSection(id=1, name="S", E=200e9, A=0.01, Iz=1e-5, Iy=1e-5, G=80e9, J=1e-6)
    )
    project.nodes.extend(
        [
            Node(id=1, coords=(0, 0, 0)),
            Node(id=2, coords=(4, 0, 0)),
            Node(id=3, coords=(8, 0, 0)),
            Node(id=4, coords=(8, 0, 0)),
        ]
    )
    project.elements.append(ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1))
    project.elements.append(ElasticBeamColumn(id=2, nodes=(2, 3), section_id=1))
    return project


def _controller(qtbot, project: Project | None, elements: set[int] | None = None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``; the viewport is a stand-in."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    if project is not None:
        vm.adopt(project)
    log: list[str] = []
    shown: list[tuple[list[int], list[int]]] = []
    selection = SimpleNamespace(
        nodes=set(),
        elements=set(elements or ()),
        clear=lambda: selection.elements.clear(),
        set_selection=lambda nodes, picked: (
            selection.elements.clear(),
            selection.elements.update(picked),
        ),
    )
    canvas = SimpleNamespace(selection=selection, render=lambda: None)
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=log.append,
        refresh_actions=lambda: None,
    )
    controller = ModelToolsController(
        shell, select_rows=lambda nodes, picked: shown.append((list(nodes), list(picked)))
    )
    return controller, vm, log, shown, selection


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.model_tools, ModelToolsController)
    assert mw.model_tools.parent() is mw
    # The window's own geometry() is still Qt's.
    assert mw.geometry().width() > 0
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id

    def enabled() -> set[str]:
        mw._refresh_action_enablement()
        return {i for i in DECLARED if mw.action(i).isEnabled()}

    mw._vm.adopt(_project())
    mw._canvas.selection.clear()
    always = set(DECLARED) - {"edit.join_frames", "edit.delete"}
    assert enabled() == always
    # Delete waits for a selection.
    mw._canvas.selection.set_selection(set(), {1})
    assert enabled() == always | {"edit.delete"}
    assert mw.action("edit.table_editing").shortcut().toString() == "Ctrl+T"
    # Joining takes two members or more.
    mw._canvas.selection.set_selection(set(), {1, 2})
    assert enabled() == set(DECLARED)
    mw._help_controller.uninstall()


def test_duplicates_are_fixed_in_one_undo_step_and_rows_go_to_the_window(
    qtbot, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, shown, _selection = _controller(qtbot, _project())

    def accept(dialog: DuplicatesDialog) -> int:
        # The dialog's "show me this row" is the hook the window handed over.
        dialog._on_select([3, 4], [])
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(DuplicatesDialog, "exec", accept)
    controller.check_duplicates()
    assert shown == [([3, 4], [])]
    assert len(vm.project.nodes) == 3
    assert len(log) == 1 and log[0].startswith("Duplicates: ")
    assert vm.undo_stack.count() == 1
    vm.undo_stack.undo()
    assert len(vm.project.nodes) == 4


def test_joining_keeps_the_survivor_selected(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, vm, log, _shown, selection = _controller(qtbot, _project(), elements={1, 2})
    controller.join_frames()
    assert len(vm.project.elements) == 1
    assert selection.elements == {vm.project.elements[0].id}
    assert log[0].startswith("Join Frames: ")
    vm.undo_stack.undo()
    assert len(vm.project.elements) == 2


def test_nothing_to_join_is_a_message_not_an_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log, _shown, _selection = _controller(qtbot, _project(), elements={1})
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    controller.join_frames()
    assert len(told) == 1 and told[0].startswith("Nothing to join")
    assert vm.undo_stack.count() == 0
    # With no project the duplicates check says what is missing.
    controller, vm, _log, _shown, _selection = _controller(qtbot, None)
    controller.check_duplicates()
    assert told[-1] == "Open or create a project first."


def test_deleting_the_selection_is_one_undo_step(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, vm, _log, _shown, selection = _controller(qtbot, _project(), elements={2})
    selection.nodes = {4}
    selection.is_empty = False
    controller.delete_selection()
    assert [e.id for e in vm.project.elements] == [1]
    assert [n.id for n in vm.project.nodes] == [1, 2, 3]
    assert vm.undo_stack.count() == 1
    assert vm.undo_stack.undoText() == "Delete 2 object(s)"
    vm.undo_stack.undo()
    assert [e.id for e in vm.project.elements] == [1, 2]
    assert [n.id for n in vm.project.nodes] == [1, 2, 3, 4]

    # Nothing selected: nothing happens.
    selection.is_empty = True
    controller.delete_selection()
    assert vm.undo_stack.count() == 1
