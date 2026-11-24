"""Groups and section cuts live in ``GroupsController`` (behaviour: ``test_groups_gui.py``)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QMainWindow, QMessageBox

from opensees_studio.core import Node, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.groups import GroupsController
from opensees_studio.views.controllers.shell import Shell

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "define.groups": "_act_groups",
    "define.section_cuts": "_act_section_cuts",
    "assign.group": "_act_assign_group",
}


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6)
    assert isinstance(mw.groups, GroupsController)
    assert mw.groups.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    assert mw.action("assign.group").shortcut().toString() == "Ctrl+Shift+G"

    def enabled() -> set[str]:
        mw._refresh_action_enablement()
        return {i for i in DECLARED if mw.action(i).isEnabled()}

    mw._vm.project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    mw._canvas.selection.clear()
    assert enabled() == {"define.groups", "define.section_cuts"}
    # Anything selected can go into a group.
    mw._canvas.selection.set_selection({1}, set())
    assert enabled() == set(DECLARED)
    mw._help_controller.uninstall()


def test_assigning_nothing_to_a_group_says_so(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    vm.adopt(Project(ndm=3, ndf=6))
    canvas = SimpleNamespace(selection=SimpleNamespace(nodes=[], elements=[]))
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=lambda _text: None,
        refresh_actions=lambda: None,
    )
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, text, *a, **k: told.append(text)
    )
    GroupsController(shell).assign_group()
    assert told == ["Select joints or elements first."]
    assert vm.undo_stack.count() == 0
