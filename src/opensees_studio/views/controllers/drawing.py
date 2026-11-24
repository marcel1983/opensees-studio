"""The draw tools, Measure Distance and the Section boxes of the Tools bar."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QComboBox, QMessageBox

from opensees_studio.commands import AddSectionsCommand
from opensees_studio.core import make_default_slab_section
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import MoveDialog, ReplicateDialog
from opensees_studio.views.i18n import tr
from opensees_studio.views.tools import (
    DrawFrameTool,
    DrawNodeTool,
    DrawShellTool,
    DrawTrussTool,
    MeasureDistanceTool,
    ToolController,
)


class DrawingController(QObject):
    """Which tool the focused viewport is in, and what the draw tools create.

    A tool is built the first time it is armed and again when the focus moved
    to another viewport; ``tools`` (the window's ``ToolController``) makes it
    the active one. Draw Frame and Quick Draw Frame share :attr:`section_combo`,
    the two shell tools :attr:`shell_section_combo`; the window puts both boxes
    in its Tools bar and hands back the actions that show and hide them.

    The tool buttons are an exclusive group the window owns: ``check_select``
    and ``check_measure`` tick Select and Measure Distance when the tool
    changes without a click. ``offset_dialog`` is the open Move or Replicate
    window, which Measure Distance fills in.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        tools: ToolController,
        check_select: Callable[[], None],
        check_measure: Callable[[], None],
        offset_dialog: Callable[[], MoveDialog | ReplicateDialog | None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._tools = tools
        self._check_select = check_select
        self._check_measure = check_measure
        self._offset_dialog = offset_dialog
        # Each tool is created when it is first armed.
        self.node_tool: DrawNodeTool | None = None
        self.frame_tool: DrawFrameTool | None = None
        self.truss_tool: DrawTrussTool | None = None
        self.quick_frame_tool: DrawFrameTool | None = None
        self.shell_tool: DrawShellTool | None = None
        self.quick_shell_tool: DrawShellTool | None = None
        self.measure_tool: MeasureDistanceTool | None = None
        #: The section Draw Frame gives its frames.
        self.section_combo = QComboBox()
        self.section_combo.setMinimumWidth(110)
        self.section_combo.setToolTip(
            "Section of the frames Draw Frame creates. A fibre section draws "
            "force-based frames; the others elastic ones."
        )
        self.section_combo.currentIndexChanged.connect(self._on_section_changed)
        #: The plate section Draw Shell gives its shells.
        self.shell_section_combo = QComboBox()
        self.shell_section_combo.setMinimumWidth(110)
        self.shell_section_combo.setToolTip("Plate section of the shells Draw Shell creates.")
        self.shell_section_combo.currentIndexChanged.connect(self._on_shell_section_changed)
        #: The Tools bar entries of the two boxes; shown while their tool is armed.
        self.section_action: QAction | None = None
        self.shell_section_action: QAction | None = None
        tools.toolChanged.connect(self._on_tool_changed)

    def select(self) -> None:
        self._tools.set_active(None)

    def draw_node(self) -> None:
        if self._vm.project is None:
            self._abort()
            return
        if self.node_tool is None or self.node_tool.canvas is not self._shell.canvas():
            self.node_tool = DrawNodeTool(self._shell.canvas(), self._vm, self._window)
            self.node_tool.statusChanged.connect(
                lambda msg: self._window.statusBar().showMessage(msg)
            )
        self._tools.set_active(self.node_tool)

    def draw_frame(self) -> None:
        if self._vm.project is None:
            self._abort()
            return
        if self.frame_tool is None or self.frame_tool.canvas is not self._shell.canvas():
            self.frame_tool = DrawFrameTool(self._shell.canvas(), self._vm, self._window)
            self.frame_tool.statusChanged.connect(
                lambda msg: self._window.statusBar().showMessage(msg)
            )
        self._tools.set_active(self.frame_tool)

    def draw_truss(self) -> None:
        if self._vm.project is None:
            self._abort()
            return
        if self.truss_tool is None or self.truss_tool.canvas is not self._shell.canvas():
            self.truss_tool = DrawTrussTool(self._shell.canvas(), self._vm, self._window)
            self.truss_tool.statusChanged.connect(
                lambda msg: self._window.statusBar().showMessage(msg)
            )
        self._tools.set_active(self.truss_tool)

    def quick_frame(self) -> None:
        """Tools → Quick Draw Frame: a click on a grid line draws the member there."""
        from opensees_studio.views.tools.quick_draw import QuickDrawFrameTool

        if self._vm.project is None:
            self._abort()
            return
        if not self.has_grid_lines():
            self._abort()
            QMessageBox.information(
                self._window,
                "Quick Draw Frame",
                "Quick Draw Frame draws on grid lines, and this project has none. "
                "Define them in Define → Coordinate System/Grids.",
            )
            return
        if (
            self.quick_frame_tool is None
            or self.quick_frame_tool.canvas is not self._shell.canvas()
        ):
            self.quick_frame_tool = QuickDrawFrameTool(self._shell.canvas(), self._vm, self._window)
            self.quick_frame_tool.statusChanged.connect(
                lambda msg: self._window.statusBar().showMessage(msg)
            )
        self._tools.set_active(self.quick_frame_tool)

    def draw_shell(self) -> None:
        """Tools → Draw Shell: needs a plate section, as Create Shell does."""
        from opensees_studio.views.tools.draw_shell import shell_sections

        project = self._vm.project
        if project is None:
            self._abort()
            return
        if not shell_sections(project):
            self._add_default_slab()
        if self.shell_tool is None or self.shell_tool.canvas is not self._shell.canvas():
            self.shell_tool = DrawShellTool(self._shell.canvas(), self._vm, self._window)
            self.shell_tool.statusChanged.connect(
                lambda msg: self._window.statusBar().showMessage(msg)
            )
        self._tools.set_active(self.shell_tool)

    def quick_shell(self) -> None:
        """Tools → Quick Draw Shell: a click inside a grid bay draws the shell there."""
        from opensees_studio.views.tools.draw_shell import shell_sections
        from opensees_studio.views.tools.quick_draw import QuickDrawShellTool

        project = self._vm.project
        if project is None:
            self._abort()
            return
        if not self.has_grid_lines():
            self._abort()
            QMessageBox.information(
                self._window,
                "Quick Draw Shell",
                "Quick Draw Shell needs grid lines. Define them in "
                "Define → Coordinate System/Grids.",
            )
            return
        if not shell_sections(project):
            self._add_default_slab()
        if (
            self.quick_shell_tool is None
            or self.quick_shell_tool.canvas is not self._shell.canvas()
        ):
            self.quick_shell_tool = QuickDrawShellTool(self._shell.canvas(), self._vm, self._window)
            self.quick_shell_tool.statusChanged.connect(
                lambda msg: self._window.statusBar().showMessage(msg)
            )
        self._tools.set_active(self.quick_shell_tool)

    def measure(self) -> None:
        if self._vm.project is None:
            self._abort()
            return
        if self.measure_tool is None or self.measure_tool.canvas is not self._shell.canvas():
            self.measure_tool = MeasureDistanceTool(self._shell.canvas(), self._vm, self._window)
            self.measure_tool.statusChanged.connect(
                lambda msg: self._window.statusBar().showMessage(msg)
            )
        dialog = self._offset_dialog()
        if dialog is not None and dialog.isVisible():
            # Measure is being used from the open Move/Replicate window: its
            # fields are the destination of the vector between the two joints.
            target = "Move" if isinstance(dialog, MoveDialog) else "Replicate"
            self.measure_tool.measure_for(target, dialog.set_measurement)
        else:
            self.measure_tool.stop_measuring_for()
        self._tools.set_active(self.measure_tool)

    def arm_measure(self) -> None:
        """Switch to Measure Distance on behalf of the open Move/Replicate window."""
        self._check_measure()
        self.measure()

    def release_measure(self) -> None:
        """That window closed: Measure has no target, and the tool goes back to Select.

        A stray click after the window closed must not pick points for nothing.
        """
        if self.measure_tool is not None:
            self.measure_tool.stop_measuring_for()
            if self._tools.active is self.measure_tool:
                self._check_select()
                self._tools.set_active(None)

    def has_grid_lines(self) -> bool:
        """True when some visible coordinate system carries grid lines."""
        project = self._vm.project
        if project is None:
            return False
        return any(cs.grid.shown for cs in project.coord_systems)

    def _abort(self) -> None:
        """Fall back to Select when a draw tool refused to arm."""
        self._check_select()
        self._tools.set_active(None)

    def _add_default_slab(self) -> None:
        """Give a project with no plate section the default 20 cm concrete slab (undoable).

        The values live in ``core.defaults`` (shared with headless callers), as
        Draw Frame's default section does; this only owns the insert.
        """
        project = self._vm.project
        assert project is not None
        section = make_default_slab_section(project.next_section_id(), project)
        self._vm.apply_command(AddSectionsCommand(self._vm, [section]))
        self._shell.log(f"Added the default slab section '{section.name}' for the shells.")

    def _on_tool_changed(self, tool) -> None:  # type: ignore[no-untyped-def]
        drawing_shells = isinstance(tool, DrawShellTool)
        if drawing_shells:
            self._fill_shell_sections()
        if self.shell_section_action is not None:
            self.shell_section_action.setVisible(drawing_shells)
        drawing_frames = isinstance(tool, DrawFrameTool)
        if drawing_frames:
            self.fill_sections()
        if self.section_action is not None:
            self.section_action.setVisible(drawing_frames)
        if tool is None:
            self._check_select()
            self._window.statusBar().showMessage("Select tool active.", 3000)
        else:
            self._window.statusBar().showMessage(tool.prompt())

    def model_changed(self) -> None:
        """A section may have been added or renamed: refill the box Draw Frame shows."""
        if self.section_action is not None and self.section_action.isVisible():
            self.fill_sections()

    def fill_sections(self) -> None:
        """List the frame sections in the Section box, keeping the current choice."""
        from opensees_studio.views.tools.draw_frame import frame_sections

        combo = self.section_combo
        chosen = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        sections = frame_sections(self._vm.project)
        for section_id, name in sections:
            combo.addItem(name, section_id)
        if not sections:
            combo.addItem(tr("Default Section"), None)
        index = combo.findData(chosen)
        combo.setCurrentIndex(max(index, 0))
        combo.blockSignals(False)
        self._on_section_changed()

    def _on_section_changed(self, _index: int = 0) -> None:
        data = self.section_combo.currentData()
        # Draw Frame and Quick Draw Frame share the box, and so the choice.
        for tool in (self.frame_tool, self.quick_frame_tool):
            if tool is not None:
                tool.section_id = None if data is None else int(data)

    def _fill_shell_sections(self) -> None:
        """List the plate sections in the shell Section box, keeping the current choice."""
        from opensees_studio.views.tools.draw_shell import shell_sections

        combo = self.shell_section_combo
        chosen = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for section_id, name in shell_sections(self._vm.project):
            combo.addItem(name, section_id)
        combo.setCurrentIndex(max(combo.findData(chosen), 0))
        combo.blockSignals(False)
        self._on_shell_section_changed()

    def _on_shell_section_changed(self, _index: int = 0) -> None:
        data = self.shell_section_combo.currentData()
        # Draw Shell and Quick Draw Shell share the box, and so the choice.
        for tool in (self.shell_tool, self.quick_shell_tool):
            if tool is not None:
                tool.section_id = None if data is None else int(data)
