"""The camera, the levels, the grid line view and hiding live in ``ViewportController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow

from opensees_studio.core import (
    CoordinateGridSystem,
    ElasticBeamColumn,
    GridSystem,
    Node,
    Project,
    make_grid_lines,
)
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.canvas3d.selection import SelectionState
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.controllers.viewport import ViewportController

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "view.iso": "_act_view_iso",
    "view.top": "_act_view_top",
    "view.front": "_act_view_front",
    "view.right": "_act_view_right",
    "view.level_up": "_act_level_up",
    "view.level_down": "_act_level_down",
    "view.rotate_left": "_act_rotate_left",
    "view.rotate_right": "_act_rotate_right",
    "view.rotate_up": "_act_rotate_up",
    "view.rotate_down": "_act_rotate_down",
    "view.grid_line_view": "_act_grid_line_view",
    "view.show_all_objects": "_act_show_all_objects",
    "view.hide_selected": "_act_hide_selected",
    "view.isolate_selected": "_act_isolate_selected",
    "view.invert_visible": "_act_invert_visible",
}
SHORTCUTS = {
    "view.iso": "Ctrl+1",
    "view.top": "Ctrl+2",
    "view.front": "Ctrl+3",
    "view.right": "Ctrl+4",
    "view.level_up": "Ctrl+Up",
    "view.level_down": "Ctrl+Down",
    "view.rotate_left": "Alt+Left",
    "view.rotate_right": "Alt+Right",
    "view.rotate_up": "Alt+Up",
    "view.rotate_down": "Alt+Down",
    "view.hide_selected": "Ctrl+H",
    "view.isolate_selected": "Ctrl+Shift+I",
}
#: The ones the controller enables itself.
SET_BY_THE_CONTROLLER = ("view.level_up", "view.level_down", "view.show_all_objects")


class _Canvas:
    """What the controller asks of a viewport, recorded."""

    ROTATE_STEP_DEG = 15.0

    def __init__(self, parent: QMainWindow) -> None:
        self.selection = SelectionState(parent)
        self.hidden: tuple[set[int], set[int]] = (set(), set())
        self.calls: list[tuple] = []  # type: ignore[type-arg]
        self.plane: tuple[str, float] | None = None
        self.camera = SimpleNamespace(parallel_projection=False)

    def set_hidden(self, *, nodes: set[int], elements: set[int]) -> None:
        self.hidden = (set(nodes), set(elements))

    def set_working_plane(self, plane: str, level: float) -> None:
        self.plane = (plane, level)

    def clear_working_plane(self) -> None:
        self.plane = None

    def working_plane_type(self) -> str | None:
        return self.plane[0] if self.plane else None

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        # view_xy, orbit, set_spinning, set_view_filter, reframe, render: just noted.
        return lambda *args, **kwargs: self.calls.append((name, args, kwargs))


def _project() -> Project:
    """Two storeys of one column line, with grid levels at 0, 3 and 6."""
    project = Project(ndm=3, ndf=6)
    project.nodes.extend(Node(id=i, coords=(0, 0, 3.0 * (i - 1))) for i in (1, 2, 3))
    project.elements.extend(ElasticBeamColumn(id=i, nodes=(i, i + 1), section_id=1) for i in (1, 2))
    project.coord_systems = [
        CoordinateGridSystem(
            name="Global",
            grid=GridSystem(
                x_grid_lines=make_grid_lines("X", [0.0, 5.0]),
                y_grid_lines=make_grid_lines("Y", [0.0]),
                z_grid_lines=make_grid_lines("Z", [0.0, 3.0, 6.0]),
            ),
        )
    ]
    return project


def _controller(qtbot, project: Project | None = None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, a recording viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    vm.adopt(project if project is not None else _project())
    canvas = _Canvas(parent)
    actions = {action_id: QAction(action_id, parent) for action_id in SET_BY_THE_CONTROLLER}
    refreshed: list[int] = []
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=lambda _text: None,
        refresh_actions=lambda: refreshed.append(1),
    )
    controller = ViewportController(shell, action=actions.__getitem__)
    return controller, canvas, actions, parent


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.viewport, ViewportController)
    assert mw.viewport.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    shortcuts = {i: mw.action(i).shortcut().toString() for i in DECLARED}
    assert {i: keys for i, keys in shortcuts.items() if keys} == SHORTCUTS
    # The Level list sits in the View toolbar and belongs to the controller.
    assert mw.viewport.level_combo.window() is mw
    # Nothing to step through and nothing hidden yet.
    assert not any(mw.action(i).isEnabled() for i in SET_BY_THE_CONTROLLER)

    def enabled() -> set[str]:
        mw._refresh_action_enablement()
        hiding = ("view.hide_selected", "view.isolate_selected", "view.invert_visible")
        return {i for i in hiding if mw.action(i).isEnabled()}

    assert enabled() == set()
    mw._vm.new_project(ndm=3, ndf=6)
    mw._vm.project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    assert enabled() == {"view.invert_visible"}
    mw._canvas.selection.set_selection({1}, set())
    assert enabled() == {"view.hide_selected", "view.isolate_selected", "view.invert_visible"}
    # Spin and Parallel projection are toggles: they reach the controller too.
    mw._act_toggle_parallel.setChecked(True)
    assert mw._canvas.camera.parallel_projection
    mw._act_toggle_parallel.setChecked(False)
    mw._help_controller.uninstall()


def test_a_plan_lists_the_levels_and_the_list_moves_the_working_plane(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, canvas, actions, _parent = _controller(qtbot)
    combo = controller.level_combo
    assert not combo.isEnabled() or combo.count() == 0

    controller.top()
    assert [combo.itemText(i) for i in range(combo.count())] == ["Z = 0", "Z = 3", "Z = 6"]
    assert canvas.plane == ("XY", 0.0)
    assert actions["view.level_up"].isEnabled() and actions["view.level_down"].isEnabled()

    controller.level_up()
    assert canvas.plane == ("XY", 3.0)
    # Stepping shows only that level: a grid line view, which Show All undoes.
    assert controller.grid_view is not None and "3" in controller.grid_view[0]
    assert actions["view.show_all_objects"].isEnabled()
    controller.level_down()
    controller.level_down()  # no level below the first one
    assert canvas.plane == ("XY", 0.0)

    controller.front()
    assert [combo.itemText(i) for i in range(combo.count())] == ["Y = 0"]
    assert not actions["view.level_up"].isEnabled()

    controller.iso()
    assert canvas.plane is None
    assert not combo.isEnabled()


def test_turning_the_camera_leaves_the_plan(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, canvas, _actions, _parent = _controller(qtbot)
    controller.top()
    controller.rotate_left()
    assert canvas.plane is None
    assert not controller.level_combo.isEnabled()
    assert ("orbit", (), {"azimuth": -15.0, "elevation": 0.0}) in canvas.calls
    controller.rotate_up()
    assert ("orbit", (), {"azimuth": 0.0, "elevation": 15.0}) in canvas.calls
    controller.top()
    controller.spin(True)
    assert canvas.plane is None
    assert ("set_spinning", (True,), {}) in canvas.calls
    controller.toggle_parallel(True)
    assert canvas.camera.parallel_projection


def test_hide_isolate_invert_and_show_all(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, canvas, actions, parent = _controller(qtbot)
    canvas.selection.set_selection({3}, set())
    controller.hide_selected()
    assert canvas.hidden == ({3}, set())
    controller.sync_show_all()
    assert actions["view.show_all_objects"].isEnabled()

    controller.invert_visible()
    assert canvas.hidden == ({1, 2}, {1, 2})

    # Isolating an element keeps its joints.
    canvas.selection.set_selection(set(), {1})
    controller.isolate_selected()
    assert canvas.hidden == ({3}, {2})
    assert parent.statusBar().currentMessage() == (
        "Isolated 2 joint(s), 1 element(s). View > Show All Objects to restore."
    )

    controller.show_all_objects()
    assert canvas.hidden == (set(), set())
    assert controller.grid_view is None
    controller.sync_show_all()
    assert not actions["view.show_all_objects"].isEnabled()


def test_another_project_forgets_the_grid_line(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, _canvas, _actions, _parent = _controller(qtbot)
    controller.top()
    controller.level_up()
    assert controller.grid_view is not None
    controller.forget_grid_line()
    assert (controller.grid_view, controller.grid_view_window) == (None, None)
    # A line that is no longer in the project shows everything again.
    controller.grid_view = ("Global: Z nowhere", 0.1)
    controller.apply_grid_line_view()
    assert controller.grid_view is None
