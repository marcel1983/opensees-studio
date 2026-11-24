"""Shells and distributed support springs live in ``AreasController``.

What each command does is pinned in ``test_create_shell.py``,
``test_shell_formulation_gui.py`` and ``test_support_springs_gui.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QMainWindow, QMessageBox

from opensees_studio.core import Node, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.areas import AreasController
from opensees_studio.views.controllers.shell import Shell

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
ON_ELEMENTS = {
    "assign.shell_formulation": "_act_shell_formulation",
    "assign.area_springs": "_act_assign_area_springs",
    "assign.edge_springs": "_act_assign_edge_springs",
    "assign.line_springs": "_act_assign_line_springs",
}
DECLARED = {"define.create_shell": "_act_create_shell"} | ON_ELEMENTS


def _controller(qtbot, nodes: set[int], elements: set[int]):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    project = Project(ndm=3, ndf=6)
    project.nodes.extend(Node(id=i, coords=(float(i), 0, 0)) for i in (1, 2, 3, 4))
    vm = ProjectViewModel()
    vm.adopt(project)
    canvas = SimpleNamespace(
        selection=SimpleNamespace(nodes=nodes, elements=elements), render=lambda: None
    )
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=lambda _text: None,
        refresh_actions=lambda: None,
    )
    return AreasController(shell), vm


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6)
    assert isinstance(mw.areas, AreasController)
    assert mw.areas.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id

    def enabled() -> set[str]:
        mw._refresh_action_enablement()
        return {i for i in DECLARED if mw.action(i).isEnabled()}

    mw._canvas.selection.clear()
    assert enabled() == set()
    # A shell goes on three or four joints.
    mw._canvas.selection.set_selection({1, 2}, set())
    assert enabled() == set()
    mw._canvas.selection.set_selection({1, 2, 3}, set())
    assert enabled() == {"define.create_shell"}
    mw._canvas.selection.set_selection({1, 2, 3, 4}, set())
    assert enabled() == {"define.create_shell"}
    mw._canvas.selection.set_selection(set(), {1})
    assert enabled() == set(ON_ELEMENTS)
    mw._help_controller.uninstall()


def test_each_command_says_what_to_select_first(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    told: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text, *a, **k: told.append((title, text)),
    )
    controller, vm = _controller(qtbot, {1, 2}, set())
    controller.create_shell()
    controller.shell_formulation()
    controller.assign_area_springs()
    controller.assign_line_springs()
    assert told == [
        (
            "Create shell",
            "Select four nodes (a quadrilateral) or three (a triangle) first (you have 2).",
        ),
        ("Shell Formulation", "Select one or more shells first."),
        ("Springs", "Select one or more shells first."),
        ("Springs", "Select one or more frame members first."),
    ]
    # Three joints but no plate section in the project yet.
    controller, vm = _controller(qtbot, {1, 2, 3}, set())
    controller.create_shell()
    assert told[-1][1].startswith("A shell needs a plate section.")
    assert vm.undo_stack.count() == 0
