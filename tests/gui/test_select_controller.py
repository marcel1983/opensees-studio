"""The Select menu lives in ``SelectController`` (the menu itself: ``test_select_menu_and_dead_case.py``)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu

from opensees_studio.core import ElasticBeamColumn, Node, Project
from opensees_studio.core.groups import Group
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.canvas3d.selection import SelectionState
from opensees_studio.views.controllers.select import SelectController
from opensees_studio.views.controllers.shell import Shell

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "select.all": "_act_select_all",
    "select.invert": "_act_invert_selection",
    "select.previous": "_act_previous_selection",
    "select.all_joints": "_act_select_all_joints",
    "select.all_elements": "_act_select_all_elements",
    "select.supports": "_act_select_supports",
    "select.joints_with_mass": "_act_select_joints_with_mass",
    "select.weighted": "_act_select_weighted",
    "select.joints_of_elements": "_act_select_joints_of_elements",
    "select.elements_within_joints": "_act_select_elements_within_joints",
    "select.loose_joints": "_act_select_loose_joints",
    "select.joints_in_bars": "_act_select_joints_in_bars",
    "select.shell_edge_joints": "_act_select_shell_edge_joints",
}
#: The ones the Select menu enables when it opens.
SET_BY_THE_MENU = (
    "select.invert",
    "select.previous",
    "select.joints_of_elements",
    "select.elements_within_joints",
)


def _project() -> Project:
    """Three joints in a row, the first one fixed, and a member between 1 and 2."""
    project = Project(ndm=3, ndf=6)
    project.nodes.extend(Node(id=i, coords=(float(i), 0, 0)) for i in (1, 2, 3))
    project.nodes[0].restraint = (True,) * 6
    project.elements.append(ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1))
    return project


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    if project is not None:
        vm.adopt(project)
    selection = SelectionState(parent)
    canvas = SimpleNamespace(selection=selection)
    actions = {action_id: QAction(action_id, parent) for action_id in SET_BY_THE_MENU}
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=lambda _text: None,
        refresh_actions=lambda: None,
    )
    return SelectController(shell, action=actions.__getitem__), selection, actions, parent


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6)
    assert isinstance(mw.select, SelectController)
    assert mw.select.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    shortcuts = {i: mw.action(i).shortcut().toString() for i in DECLARED}
    assert {i: keys for i, keys in shortcuts.items() if keys} == {
        "select.all": "Ctrl+A",
        "select.invert": "Ctrl+I",
        "select.previous": "Ctrl+P",
    }
    # The side buttons of the viewport read "all" and "ps".
    assert mw.action("select.all").iconText() == "all"
    assert mw.action("select.previous").iconText() == "ps"
    mw._help_controller.uninstall()


def test_the_queries_add_to_what_is_selected(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, selection, _actions, parent = _controller(qtbot, _project())
    controller.supports()
    assert (set(selection.nodes), set(selection.elements)) == ({1}, set())
    controller.all_elements()
    assert (set(selection.nodes), set(selection.elements)) == ({1}, {1})
    controller.joints_of_elements()
    assert set(selection.nodes) == {1, 2}
    assert parent.statusBar().currentMessage() == "Selected 2 joint(s), 1 element(s)."
    controller.loose_joints()
    assert set(selection.nodes) == {1, 2, 3}
    selection.set_selection({1, 2}, set())
    controller.elements_within_joints()
    assert set(selection.elements) == {1}


def test_all_invert_and_previous_replace_the_selection(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, selection, _actions, _parent = _controller(qtbot, _project())
    controller.all_objects()
    assert (set(selection.nodes), set(selection.elements)) == ({1, 2, 3}, {1})
    selection.set_selection({1}, set())
    controller.invert()
    assert (set(selection.nodes), set(selection.elements)) == ({2, 3}, {1})
    controller.previous()
    assert (set(selection.nodes), set(selection.elements)) == ({1}, set())
    # A joint deleted since is not brought back.
    selection.set_selection({3}, set())
    selection.set_selection(set(), set())
    del controller._vm.project.nodes[2]
    controller.previous()
    assert set(selection.nodes) == set()


def test_the_menu_enables_what_the_selection_allows(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, selection, actions, parent = _controller(qtbot, _project())
    menu = QMenu(parent)
    controller.add_by_menus(menu)
    titles = [action.text() for action in menu.actions()]
    assert titles == [
        "By Element &Type",
        "By Se&ction",
        "By Mate&rial",
        "By &Load Pattern",
        "By &Group",
    ]

    def enabled() -> set[str]:
        menu.aboutToShow.emit()
        return {i for i, action in actions.items() if action.isEnabled()}

    assert enabled() == {"select.invert"}
    selection.set_selection({1}, set())
    assert enabled() == {"select.invert", "select.elements_within_joints"}
    selection.set_selection(set(), {1})
    assert enabled() == {"select.invert", "select.previous", "select.joints_of_elements"}


def test_without_a_project_nothing_is_offered_and_nothing_happens(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, selection, actions, parent = _controller(qtbot, None)
    menu = QMenu(parent)
    controller.add_by_menus(menu)
    controller.refresh_menu()
    assert not any(action.isEnabled() for action in actions.values())
    assert not any(action.isEnabled() for action in menu.actions())
    controller.all_objects()
    controller.invert()
    controller.all_joints()
    assert selection.is_empty


def test_a_by_group_entry_selects_the_members_of_the_group(qtbot) -> None:  # type: ignore[no-untyped-def]
    project = _project()
    project.groups.append(Group(id=1, name="Bay A", node_ids=[2, 3], element_ids=[1]))
    controller, selection, _actions, parent = _controller(qtbot, project)
    menu = QMenu(parent)
    controller.add_by_menus(menu)
    controller.by_group_menu.aboutToShow.emit()
    (entry,) = controller.by_group_menu.actions()
    assert entry.text() == "Bay A (2 joint(s), 1 element(s))"
    entry.trigger()
    assert (set(selection.nodes), set(selection.elements)) == ({2, 3}, {1})
    controller.by_type_menu.aboutToShow.emit()
    assert [a.text() for a in controller.by_type_menu.actions()] == ["ElasticBeamColumn (1)"]
