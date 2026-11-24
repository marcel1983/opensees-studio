"""The draw tools and their Section boxes live in ``DrawingController``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMainWindow, QMessageBox

from opensees_studio.core import ElasticSection, Project
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.drawing import DrawingController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.tools import DrawFrameTool, DrawNodeTool, MeasureDistanceTool

pytestmark = pytest.mark.gui


class _Tools(QObject):
    """The window's ``ToolController``, as far as the controller uses it."""

    toolChanged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.active: object | None = None
        self.armed: list[object | None] = []

    def set_active(self, tool: object | None) -> None:
        self.active = tool
        self.armed.append(tool)
        self.toolChanged.emit(tool)


def _controller(qtbot, project: Project | None):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, no viewport."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    if project is not None:
        vm.adopt(project)
    tools = _Tools()
    ticked: list[str] = []
    canvas = SimpleNamespace()
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: canvas,  # type: ignore[arg-type, return-value]
        log=lambda _text: None,
        refresh_actions=lambda: None,
    )
    controller = DrawingController(
        shell,
        tools=tools,  # type: ignore[arg-type]
        check_select=lambda: ticked.append("select"),
        check_measure=lambda: ticked.append("measure"),
        offset_dialog=lambda: None,
    )
    return controller, tools, ticked, parent


def test_the_window_owns_one_controller_and_the_tool_buttons_reach_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6)
    assert isinstance(mw.drawing, DrawingController)
    assert mw.drawing.parent() is mw
    # The two Section boxes sit in the Tools bar, hidden until their tool is armed.
    for combo, entry in (
        (mw.drawing.section_combo, mw.drawing.section_action),
        (mw.drawing.shell_section_combo, mw.drawing.shell_section_action),
    ):
        assert combo.window() is mw
        assert entry is not None and not entry.isVisible()

    mw._act_tool_draw_node.trigger()
    assert isinstance(mw._tool_controller.active, DrawNodeTool)
    assert mw._tool_controller.active is mw.drawing.node_tool
    mw._act_tool_draw_frame.trigger()
    assert isinstance(mw._tool_controller.active, DrawFrameTool)
    assert mw.drawing.section_combo.count() >= 1  # at least "Default Section"
    mw._act_tool_select.trigger()
    assert mw._tool_controller.active is None

    # Move/Replicate arm Measure Distance through the controller, and let go of it.
    mw.transforms._arm_measure()
    assert mw._act_tool_measure.isChecked()
    assert isinstance(mw._tool_controller.active, MeasureDistanceTool)
    mw.transforms._release_measure()
    assert mw._act_tool_select.isChecked()
    assert mw._tool_controller.active is None
    mw._help_controller.uninstall()


def test_no_project_no_tool(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, tools, ticked, _parent = _controller(qtbot, None)
    for arm in (
        controller.draw_node,
        controller.draw_frame,
        controller.draw_truss,
        controller.quick_frame,
        controller.draw_shell,
        controller.quick_shell,
        controller.measure,
    ):
        arm()
    # Each one fell back to Select, and nothing was built.
    assert tools.armed == [None] * 7
    assert ticked.count("select") >= 7
    assert controller.node_tool is None and controller.measure_tool is None
    assert not controller.has_grid_lines()


def test_quick_draw_asks_for_grid_lines(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project = Project(ndm=3, ndf=6)
    for system in project.coord_systems:
        system.grid.hide_all = True
    controller, tools, _ticked, _parent = _controller(qtbot, project)
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, title, _text, *a, **k: told.append(title)
    )
    assert not controller.has_grid_lines()
    controller.quick_frame()
    controller.quick_shell()
    assert told == ["Quick Draw Frame", "Quick Draw Shell"]
    assert tools.armed == [None, None]
    assert controller.quick_frame_tool is None and controller.quick_shell_tool is None


def test_the_select_tool_says_so_and_the_section_box_lists_the_sections(qtbot) -> None:  # type: ignore[no-untyped-def]
    project = Project(ndm=3, ndf=6)
    controller, tools, ticked, parent = _controller(qtbot, project)
    controller.select()
    assert tools.armed == [None]
    assert ticked == ["select"]
    assert parent.statusBar().currentMessage() == "Select tool active."

    controller.fill_sections()
    combo = controller.section_combo
    assert [combo.itemData(i) for i in range(combo.count())] == [None]
    project.sections.append(ElasticSection(id=4, name="Beam", E=1, A=1, Iz=1, Iy=1, G=1, J=1))
    controller.fill_sections()
    assert [combo.itemData(i) for i in range(combo.count())] == [4]
    # Outside a window there is no Tools bar entry to refresh.
    controller.model_changed()
