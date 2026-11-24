"""Main application window — Phase 4a integration.

Adds on top of Phase 3:
- Edit menu (Undo / Redo / Delete) with keyboard shortcuts
- Define menu (Grid System… → AddNodesCommand)
- Assign menu (Restraints…, Loads…) — both gated by current selection
- modelMutated path: command-driven re-renders preserve camera/selection
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Sequence
from functools import partial
from pathlib import Path
from typing import Any, ClassVar, cast

import shiboken6
from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from opensees_studio import __version__
from opensees_studio.commands import (
    AddNodesCommand,
    MeshCommand,
    SetProjectMetaCommand,
    SetRestraintCommand,
)
from opensees_studio.commands.generated import insert_generated
from opensees_studio.core import (
    SUPPORTED_NDF,
    ElasticSection,
    Project,
    UnitConverter,
    UnitSystem,
    build_portal_frame,
    frame_grid,
    labels_for,
    make_default_section,
    make_default_truss_material,
    shortcut_profiles,
)
from opensees_studio.core.generated import GeneratedModel
from opensees_studio.core.help import ACTION_TOPICS, TOPIC_PROPERTY
from opensees_studio.core.i18n import LANGUAGES
from opensees_studio.core.materials.library import is_uniaxial
from opensees_studio.core.mesh import pre_run_auto_mesh
from opensees_studio.core.model_check import check_model
from opensees_studio.core.object_info import element_info, node_info
from opensees_studio.core.view_settings import ViewSettings
from opensees_studio.services import (
    PROJECT_FILE_SUFFIX,
    engines,
    load_project,
    run_snapshot_path,
)
from opensees_studio.services.batch import StoredResults, stored_results
from opensees_studio.services.combination import MissingCaseResultsError
from opensees_studio.services.result_store import load_results
from opensees_studio.services.results import (
    CombinationResults,
    InfluenceLineResults,
    ModalResults,
    PushoverResults,
    ResponseSpectrumResults,
    TransientResults,
)
from opensees_studio.services.results_db import database_path, delete_all_results, record_results
from opensees_studio.services.shell_fields import shell_elements
from opensees_studio.services.stability import StabilityReport
from opensees_studio.viewmodels import AnalysisRunner, ProjectViewModel
from opensees_studio.viewmodels.results_session import ResultsSession, case_names
from opensees_studio.viewmodels.stability_checker import StabilityChecker
from opensees_studio.views.actions import ALL_ACTIONS, ActionState
from opensees_studio.views.actions.registry import ActionRegistry
from opensees_studio.views.canvas3d import ModelCanvas, SnapMode
from opensees_studio.views.canvas3d.design_ratio_renderer import DesignRatioRenderer
from opensees_studio.views.canvas3d.diagram_renderer import DiagramRenderer
from opensees_studio.views.canvas3d.model_renderer import RendererMode
from opensees_studio.views.canvas3d.shell_contour_renderer import ShellContourRenderer
from opensees_studio.views.controllers import Shell
from opensees_studio.views.controllers.areas import AreasController
from opensees_studio.views.controllers.building import BuildingController
from opensees_studio.views.controllers.design import DesignController
from opensees_studio.views.controllers.display import DisplayController
from opensees_studio.views.controllers.drawing import DrawingController
from opensees_studio.views.controllers.exports import ExportsController
from opensees_studio.views.controllers.generators import GeneratorsController
from opensees_studio.views.controllers.grids import GridsController
from opensees_studio.views.controllers.groups import GroupsController
from opensees_studio.views.controllers.imports import ImportsController
from opensees_studio.views.controllers.joints import JointsController
from opensees_studio.views.controllers.library import LibraryController
from opensees_studio.views.controllers.loads import LoadsController
from opensees_studio.views.controllers.members import MembersController
from opensees_studio.views.controllers.model_lock import ModelLockController
from opensees_studio.views.controllers.model_tools import ModelToolsController
from opensees_studio.views.controllers.patterns import PatternsController
from opensees_studio.views.controllers.property_edits import PropertyEditsController
from opensees_studio.views.controllers.select import SelectController
from opensees_studio.views.controllers.transforms import TransformsController
from opensees_studio.views.controllers.viewport import ViewportController
from opensees_studio.views.dialogs import (
    AddNodeDialog,
    AnalysisCaseManagerDialog,
    DisplayOptionsDialog,
    FrameWizard,
    ModelCheckDialog,
    MoveDialog,
    PerformanceDialog,
    ProjectInfoDialog,
    ReplicateDialog,
    RunAnalysisDialog,
)
from opensees_studio.views.dialogs.batch_run import BatchRunDialog
from opensees_studio.views.dialogs.load_combinations import LoadCombinationsDialog
from opensees_studio.views.dialogs.load_display import LoadDisplayDialog
from opensees_studio.views.dialogs.object_info import ObjectInfoDialog
from opensees_studio.views.dialogs.reactions import ReactionsDialog
from opensees_studio.views.dialogs.run_cases import RunCasesDialog
from opensees_studio.views.dialogs.solver_settings import SolverSettingsDialog
from opensees_studio.views.dialogs.view_colors import ViewColorsDialog
from opensees_studio.views.docks import (
    PropertyEditorDock,
    ReactionsPanel,
    ResultsPanel,
)
from opensees_studio.views.help_window import HelpController
from opensees_studio.views.i18n import stored_language, tr
from opensees_studio.views.project_dock import ProjectDock
from opensees_studio.views.ribbon import RibbonBar, build_ribbon_tabs
from opensees_studio.views.ribbon.icons import apply_command_icons
from opensees_studio.views.run_status import RunStatusWidget
from opensees_studio.views.start_page import RecentFiles, StartPage
from opensees_studio.views.theme import apply_theme, viewport_style
from opensees_studio.views.tools import (
    SelectTool,
    ToolController,
)
from opensees_studio.views.view_window import ViewWindow

#: Options → Autosave Recovery Copy: minutes between copies (0 = off), and where
#: the choice is kept.
AUTOSAVE_CHOICES = (0, 2, 5, 10)
AUTOSAVE_DEFAULT = 5
AUTOSAVE_KEY = "autosave/minutes"

#: File → New Model: the units chosen last, offered again.
NEW_MODEL_UNITS_KEY = "new_model/units"


def _portable_keys(action: QAction) -> tuple[str, ...]:
    """An action's keys as portable text ("Ctrl+T"), the form a profile names them in."""
    return tuple(
        key.toString(QKeySequence.SequenceFormat.PortableText) for key in action.shortcuts()
    )


def _snap_icon(kind: SnapMode) -> QIcon:
    """A small vector icon for the object-snap bar (the app ships no image assets)."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    line = QPen(QColor("#c8ced8"), 1.7)
    line.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(line)
    marker = {
        SnapMode.MIDPOINT: QColor("#ffd54f"),
        SnapMode.PERPENDICULAR: QColor("#26bfff"),
        SnapMode.ON_ELEMENT: QColor("#59e07a"),
    }[kind]
    if kind is SnapMode.MIDPOINT:
        painter.drawLine(QPointF(4, 19), QPointF(20, 5))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(marker)
        painter.drawEllipse(QPointF(12, 12), 2.8, 2.8)
    elif kind is SnapMode.PERPENDICULAR:
        painter.drawLine(QPointF(4, 19), QPointF(20, 19))
        painter.drawLine(QPointF(13, 19), QPointF(13, 5))
        painter.drawLine(QPointF(13, 15), QPointF(17, 15))
        painter.drawLine(QPointF(17, 15), QPointF(17, 19))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(marker)
        painter.drawEllipse(QPointF(13, 19), 2.8, 2.8)
    else:
        painter.drawLine(QPointF(4, 19), QPointF(20, 5))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(marker)
        painter.drawEllipse(QPointF(16, 8), 2.8, 2.8)
    painter.end()
    return QIcon(pixmap)


def _restraint_icon(preset: str) -> QIcon:
    """The support symbol of a restraint preset, drawn like the model draws it."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#3fbf7f"), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    joint = QPointF(12, 7)
    if preset == "Fix":
        painter.drawLine(QPointF(12, 3), QPointF(12, 14))
        painter.drawLine(QPointF(4, 14), QPointF(20, 14))
        for x in (6, 10, 14, 18):
            painter.drawLine(QPointF(x, 14), QPointF(x - 3, 19))
    elif preset in ("Pin", "Roller (Z)"):
        painter.drawPolygon([joint, QPointF(5, 16), QPointF(19, 16)])
        if preset == "Pin":
            for x in (6, 10, 14, 18):
                painter.drawLine(QPointF(x, 16), QPointF(x - 3, 21))
        else:
            painter.drawEllipse(QPointF(8, 19), 2.3, 2.3)
            painter.drawEllipse(QPointF(16, 19), 2.3, 2.3)
    else:  # Free: a joint with nothing under it
        painter.setPen(QPen(QColor("#c8ced8"), 1.8))
        painter.drawEllipse(QPointF(12, 12), 4.0, 4.0)
        painter.drawLine(QPointF(5, 19), QPointF(19, 5))
    painter.end()
    return QIcon(pixmap)


def _add_actions(menu: QMenu, actions: Sequence[QAction | None]) -> None:
    """Add ``actions`` to ``menu``; ``None`` is a separator."""
    for action in actions:
        if action is None:
            menu.addSeparator()
        else:
            menu.addAction(action)


class MainWindow(QMainWindow):
    """Top-level application shell."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"OpenSees Studio v{__version__}")
        self.resize(1600, 1000)

        self._vm = ProjectViewModel(self)
        # The solver is a separate program (Options → Solver); it may be absent.
        engines.activate(engines.load_settings().package_dir)
        self._solver = engines.current_status()  # the engine that runs the cases
        self._opensees = engines.opensees_status()  # stability check, Material Tester
        self._runner = AnalysisRunner(self)
        self._stability = StabilityChecker(self)
        #: The results in memory: the one on screen, every case's, the report's extras.
        self.results = ResultsSession()
        #: View → Grid Line View: (line label, window) while active, else None.
        self._analysis_error_box: QMessageBox | None = None  # last failure report
        self._stability_box: QMessageBox | None = None  # last stability check answer
        self._run_dialog: RunAnalysisDialog | None = None  # open while a Run dialog is shown
        self._show_node_labels = False
        self._show_element_labels = False
        self._user_close_requested = False  # File → Quit sets this before close()
        #: Top-level menus by role, so the startup gate can disable them all at
        #: once instead of grey-out every action they contain.
        self._menus: dict[str, QMenu] = {}
        #: Nesting depth of the busy cursor (see _begin_busy / _end_busy).
        self._busy_depth = 0
        #: Secondary viewports on the same project (View → New View Window).
        self._view_windows: list[ViewWindow] = []
        #: Object snaps enabled in every viewport (the left icon bar).
        self._snap_modes: set[SnapMode] = set(SnapMode)

        self._build_central_canvas()
        self._tool_controller = ToolController(self._canvas, self._vm, self)
        self._select_tool = SelectTool(self._canvas, self._vm, self)

        shell = Shell(
            window=self,
            vm=self._vm,
            canvas=lambda: self._canvas,
            log=self._log,
            refresh_actions=self._refresh_action_enablement,
        )
        #: The draw tools, Measure Distance and the Section boxes of the Tools bar.
        self.drawing = DrawingController(
            shell,
            tools=self._tool_controller,
            check_select=lambda: self._act_tool_select.setChecked(True),
            check_measure=lambda: self._act_tool_measure.setChecked(True),
            offset_dialog=lambda: self.transforms.offset_dialog,
        )
        #: Edit → Copy, Paste, Move, Replicate, Mirror, Extrude.
        self.transforms = TransformsController(
            shell,
            arm_measure=lambda: self.drawing.arm_measure(),
            release_measure=lambda: self.drawing.release_measure(),
        )

        #: Storeys, mass source, seismic loads, diaphragms, rigid links.
        self.areas = AreasController(shell)
        self.building = BuildingController(shell)
        #: Define → Create Building.
        self.generators = GeneratorsController(shell)
        #: Assign → Frame: section, material, formulation, frame member options.
        self.joints = JointsController(shell)
        self.model_tools = ModelToolsController(
            shell, select_rows=lambda nodes, elements: self._select_report_row(nodes, elements)
        )
        self.exports = ExportsController(
            shell,
            results=lambda: self.results.current(self._vm.project),
            report_results=lambda: self.report_results(),
        )
        #: Define → Coordinate System/Grids and Grid Wizard; View → Show Grids and labels.
        self.grids = GridsController(
            shell,
            new_project=lambda: self._on_new(),
            sync_actions=lambda: self._sync_grid_actions(),
        )
        self.groups = GroupsController(shell)
        self.imports = ImportsController(
            shell,
            confirm_discard=lambda action: self._confirm_discard_changes(action),
            apply_view_settings=lambda: self._apply_project_view_settings(),
        )
        self.library = LibraryController(shell, new_project=lambda: self._on_new())
        self.members = MembersController(shell)
        self.patterns = PatternsController(shell, new_project=self._on_new)
        #: The camera, the working plane and its level, a grid line view, what is hidden.
        self.viewport = ViewportController(shell, action=lambda action_id: self.action(action_id))
        #: The post-processing views of the Display menu and the dock each one opens.
        self.display = DisplayController(
            shell,
            results=self.results,
            diagram=self._diagram_renderer,
            contours=self._contour_renderer,
            ratios=self._ratio_renderer,
            canvases=lambda: [self._main_canvas, *(w.canvas for w in self._view_windows)],
            busy=lambda message: self._busy(message),
            select_rows=lambda nodes, elements: self._select_report_row(nodes, elements),
            results_for_key=lambda key: self._results_for_key(key),
            show_results=lambda results: self._display_results(results),
            display_units=lambda: self._current_display_units(),
            set_display_units=lambda units: self._set_display_units(units),
        )
        #: Options → Lock Model: results make an edit of the model ask first.
        self.model_lock = ModelLockController(
            shell,
            results=self.results,
            drop_results=lambda: self._drop_session_results(),
            action=lambda action_id: self.action(action_id),
        )
        #: What the Properties dock changes in the model.
        self.property_edits = PropertyEditsController(shell)
        #: The Select menu: everything, inverted, the previous one, the queries.
        self.select = SelectController(shell, action=lambda action_id: self.action(action_id))
        #: Loads on joints, frames and areas, joint patterns, Edit → Delete Loads.
        self.loads = LoadsController(shell)
        #: The Design menu: basis, members, steel and concrete checks, connections, footings.
        self.design = DesignController(
            shell,
            results=lambda: self.results.current(self._vm.project),
            show_ratios=lambda report, settings, concrete=False: self.display.design_ratios(
                report, settings, concrete=concrete
            ),
        )

        self._build_docks()
        self._log(f"OpenSees Studio {__version__} started.")
        self._log_solver_status()
        self._build_actions()
        self._build_menu_bar()
        self._build_view_toolbar()
        self._build_tools_toolbar()
        self._build_snap_toolbar()
        self._build_restraints_toolbar()
        self._build_selection_toolbar()
        self._build_status_bar()
        self._build_ribbon()
        self._wire()
        self._refresh_action_enablement()
        self._restore_session_state()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        self._set_autosave(self._stored_autosave_minutes(), remember=False)
        # Every action exists now: its keys are the defaults a profile starts from.
        self._default_shortcuts = {
            name: _portable_keys(action)
            for name, action in vars(self).items()
            if name.startswith("_act_") and isinstance(action, QAction)
        }
        self._set_shortcut_profile(self._stored_shortcut_profile(), remember=False)
        if self._stored_dark_mode():
            self._act_dark_mode.setChecked(True)

    # ── construction ─────────────────────────────────────────────────
    def _build_central_canvas(self) -> None:
        self._main_canvas = ModelCanvas(self)
        #: The viewport the menus and the tools act on. It starts as the main
        #: one and follows focus to a secondary ViewWindow when one is active.
        self._active_canvas: ModelCanvas = self._main_canvas
        # With no project the start page takes the viewport's place.
        self._recent = RecentFiles()
        self._start_page = StartPage(
            {
                "new_model": self._on_new_model,
                "new_3d": self._on_new,
                "new_2d": self._on_new_2d,
                "new_truss": self._on_new_2d_truss,
                "open": self._on_open,
            },
            self._recent,
        )
        self._start_page.openRequested.connect(self._on_open_recent)
        self._start_page.recoverRequested.connect(self._on_recover_untitled)
        untitled = run_snapshot_path(None)
        self._start_page.set_recovery(untitled if untitled.is_file() else None)
        self._central = QStackedWidget(self)
        self._central.addWidget(self._start_page)
        self._central.addWidget(self._main_canvas)
        self.setCentralWidget(self._central)
        # Diagram overlay paints onto the same plotter as the model.
        self._diagram_renderer = DiagramRenderer(self._main_canvas)
        self._contour_renderer = ShellContourRenderer(self._main_canvas)
        self._ratio_renderer = DesignRatioRenderer(self._main_canvas)

    @property
    def _canvas(self) -> ModelCanvas:
        """The focused viewport: where View-menu actions and picking land."""
        return self._active_canvas

    def action(self, action_id: str) -> QAction:
        """The command declared as ``action_id`` in ``views/actions`` (``"file.save"``)."""
        return self._actions.action(action_id)

    def _build_docks(self) -> None:
        # Model tree (left)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Model")
        # Allow Ctrl+click / Shift+click to build up a multi-row selection,
        # so Assign → Joint → Zero-Length Section (and other multi-entity
        # commands) work directly from the tree.
        self._tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection,
        )
        self._tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        # Top-level category items, populated lazily on refresh.
        self._tree_categories: dict[str, QTreeWidgetItem] = {}
        for label in (
            "Nodes",
            "Elements",
            "Materials",
            "Sections",
            "Time Series",
            "Patterns",
            "Analyses",
        ):
            cat = QTreeWidgetItem([label])
            self._tree_categories[label] = cat
            self._tree.addTopLevelItem(cat)
        tree_dock = QDockWidget("Model Explorer", self)
        tree_dock.setObjectName("modelExplorerDock")
        tree_dock.setWidget(self._tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tree_dock)

        self._props = PropertyEditorDock()
        self._props.on_apply_mass = self.property_edits.apply_mass
        self._props.on_change_element_type = self.property_edits.change_element_type
        self._props.on_change_element_material = self.property_edits.change_element_material
        self._props.on_change_element_section = self.property_edits.change_element_section
        self._props.on_change_element_fields = self.property_edits.change_element_fields
        self._props.on_assign_node_restraints = self.property_edits.assign_node_restraints
        self._props.on_assign_node_masses = self.property_edits.assign_node_masses
        self._props.on_assign_elements = self.property_edits.assign_elements
        props_dock = QDockWidget("Properties", self)
        props_dock.setObjectName("propertiesDock")
        props_dock.setWidget(self._props)
        # With nothing selected its content is one short label, which used to
        # leave the dock so narrow that its own title read "Proper…".
        props_dock.setMinimumWidth(220)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props_dock)

        self._console = QPlainTextEdit()
        self._console.setReadOnly(True)
        self._console.setPlaceholderText("Logs and OpenSeesPy output will appear here.")
        console_dock = QDockWidget("Console", self)
        console_dock.setObjectName("consoleDock")
        console_dock.setWidget(self._console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, console_dock)

        self._results_panel = ResultsPanel()
        results_dock = QDockWidget("Results", self)
        results_dock.setObjectName("resultsDock")
        results_dock.setWidget(self._results_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, results_dock)
        self._reactions_panel = ReactionsPanel()
        self._reactions_dock = QDockWidget("Reactions", self)
        self._reactions_dock.setObjectName("reactionsDock")
        self._reactions_dock.setWidget(self._reactions_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._reactions_dock)
        self.tabifyDockWidget(console_dock, results_dock)
        self.tabifyDockWidget(results_dock, self._reactions_dock)
        console_dock.raise_()
        #: The panels that always exist, in the order View → Panels lists them.
        #: Their layout is saved on close; the result docks opened later are not.
        self._layout_docks = [
            tree_dock,
            props_dock,
            console_dock,
            results_dock,
            self._reactions_dock,
        ]

    def _build_actions(self) -> None:
        # File: declared in views/actions/file.py. The registry builds each
        # action and stores it as ``_act_<name>`` too.
        self._actions = ActionRegistry(ALL_ACTIONS)
        self._actions.create(self)

        # Edit (created from QUndoStack so text auto-tracks "Undo Add 4 nodes" etc.)
        self._act_undo = self._vm.undo_stack.createUndoAction(self, "Undo")
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_redo = self._vm.undo_stack.createRedoAction(self, "Redo")
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._act_clear_selection = QAction("Clear &selection", self, shortcut="Esc")

        # Select menu: queries that add to (or invert) the current selection.
        self._act_select_line = QAction("Intersecting &Line", self, checkable=True)
        self._act_select_line.setToolTip(
            "Drag a line across the model: every member and shell it cuts is selected"
        )
        # SAP2000's side buttons read all / ps / clr / line.
        self.action("select.all").setIconText("all")
        self.action("select.previous").setIconText("ps")
        self._act_clear_selection.setIconText("clr")
        self._act_select_line.setIconText("line")

        # Edit → transforms

        # Tools (exclusive)
        self._tool_group = QActionGroup(self)
        self._tool_group.setExclusive(True)
        self._act_tool_select = QAction("Se&lect", self, checkable=True, checked=True)
        self._act_tool_draw_node = QAction("Draw &Node", self, checkable=True, shortcut="F4")
        self._act_tool_draw_frame = QAction("&Draw Frame", self, checkable=True, shortcut="F2")
        self._act_tool_draw_truss = QAction("Draw &Truss", self, checkable=True, shortcut="F3")
        self._act_tool_quick_frame = QAction("&Quick Draw Frame", self, checkable=True)
        self._act_tool_quick_shell = QAction("Quick Draw S&hell", self, checkable=True)
        self._act_tool_draw_shell = QAction(
            "Draw &Shell", self, checkable=True, shortcut=QKeySequence("F8")
        )
        self._act_tool_measure = QAction(
            "&Measure Distance", self, checkable=True, shortcut=QKeySequence("F7")
        )
        self._tool_group.addAction(self._act_tool_select)
        self._tool_group.addAction(self._act_tool_draw_node)
        self._tool_group.addAction(self._act_tool_draw_frame)
        self._tool_group.addAction(self._act_tool_draw_truss)
        self._tool_group.addAction(self._act_tool_quick_frame)
        self._tool_group.addAction(self._act_tool_quick_shell)
        self._tool_group.addAction(self._act_tool_draw_shell)
        self._tool_group.addAction(self._act_tool_measure)

        # Object snaps on frame members (independent checkable icons).
        self._snap_actions: dict[SnapMode, QAction] = {}
        for mode, label, tip in (
            (
                SnapMode.MIDPOINT,
                "Snap to midpoint",
                "Object snap: the midpoint of a member",
            ),
            (
                SnapMode.PERPENDICULAR,
                "Snap perpendicular",
                "Object snap: the perpendicular foot from the previous point",
            ),
            (
                SnapMode.ON_ELEMENT,
                "Snap to member",
                "Object snap: the nearest point on a member",
            ),
        ):
            action = QAction(label, self, checkable=True, checked=True)
            action.setIcon(_snap_icon(mode))
            action.setToolTip(tip)
            action.setStatusTip(tip)
            self._snap_actions[mode] = action

        # Define
        # No shortcut: Ctrl+N is File → New, and F4 draws nodes.
        self._act_add_node = QAction("Add &Node…", self)
        self._act_custom_commands = QAction("Custom OpenSees Co&mmands…", self)
        self._act_frame_wizard = QAction("Create Portal &Frame…", self)
        self._act_truss_wizard = QAction("Create &Truss…", self)
        self._act_warehouse_wizard = QAction("Create &Warehouse…", self)
        self._act_warehouse_wizard.setToolTip(
            "A 3D steel warehouse from a few numbers: portal frames, purlins, girts, "
            "bracing, roof loads and the combinations of a design code."
        )
        self._act_load_combinations = QAction("Load &Combinations…", self)

        # Assign
        # Assign — organized as Joint (nodes) / Frame (elements) for SAP2000 parity.
        # One click on the Restraints bar: the common supports, no dialog.
        self._act_restraint_fixed = QAction("&Fixed", self)
        self._act_restraint_pinned = QAction("&Pinned", self)
        self._act_restraint_roller = QAction("R&oller", self)
        self._act_restraint_free = QAction("F&ree", self)
        for action, preset, tip in (
            (self._act_restraint_fixed, "Fix", "every translation and rotation"),
            (self._act_restraint_pinned, "Pin", "the translations; rotations free"),
            (self._act_restraint_roller, "Roller (Z)", "the vertical translation only"),
            (self._act_restraint_free, "Free", "nothing (removes the support)"),
        ):
            action.setIcon(_restraint_icon(preset))
            text = f"Restrain the selected joints: {tip}."
            action.setToolTip(text)
            action.setStatusTip(text)
            action.setProperty("ownTip", text)
            action.setData(preset)

        # Display (post-processing)
        self._act_select_results = QAction("Show Results &Of…", self)
        self._act_show_reactions = QAction("Show &Reactions", self)
        self._act_show_reactions.setCheckable(True)
        self._act_reactions_table = QAction("Reactions &Table", self)
        self._act_reactions_dialog = QAction("R&eactions…", self)
        self._act_display_options = QAction("Display &Options…", self)
        self._act_use_ribbon = QAction("Use &Ribbon", self, checkable=True)
        self._act_use_ribbon.setToolTip(
            "Show the ribbon: the menu commands regrouped by the modelling workflow. "
            "Turn it off to work with the classic menus."
        )
        self._act_dark_mode = QAction("&Dark Mode", self, checkable=True)
        self._act_dark_mode.setToolTip(
            "Use the dark palette for the interface and the 3D viewport."
        )
        self._act_show_load_assigns = QAction("Show &Load Assigns…", self)
        self._act_show_load_assigns.setToolTip(
            "Choose the load pattern drawn (or all, one colour each), the kinds of load "
            "and whether their values are written."
        )

        # Analyze
        self._act_case_manager = QAction("&Cases…", self, shortcut="Ctrl+Shift+A")
        self._act_check_model = QAction("Check &Model…", self)
        self._act_check_model.setShortcut("F6")
        self._act_run = QAction("&Run…", self, shortcut="F5")
        # Batch doors: the whole model in one child process, or a ticked subset.
        self._act_run_all = QAction("Run &All Cases", self, shortcut=QKeySequence("Shift+F5"))
        self._act_run_selected = QAction("Run Se&lected Cases…", self)
        self._act_clear_results = QAction("Delete &All Results…", self)
        self._act_auto_mesh_frames = QAction("Auto-mesh &Frames Before Run", self)
        self._act_auto_mesh_frames.setCheckable(True)
        self._act_auto_mesh_frames.setChecked(True)
        self._act_auto_mesh_frames.setStatusTip(
            "Run divides frames where another frame ends on them or crosses them."
        )
        self._act_check_stability = QAction("Check Model &Stability…", self)
        self._act_cancel_stability = QAction("&Cancel Stability Check", self)

        # View
        self._act_zoom_extents = QAction("Zoom &Extents", self, shortcut="Ctrl+E")
        # Move Up/Down in List wait for a plan or an elevation with several levels.
        self.action("view.level_up").setEnabled(False)
        self.action("view.level_down").setEnabled(False)
        # View → Rotate: the camera turns, the model does not.
        self._act_spin = QAction("⟳ Spin", self, checkable=True)
        self._act_spin.setToolTip("Turn the view continuously, to present the model")
        self._act_toggle_parallel = QAction("&Parallel projection", self, checkable=True)
        self._act_show_extruded = QAction("Show &Extruded Sections", self, checkable=True)
        self._act_show_local_axes = QAction("Show Local A&xes", self, checkable=True)
        self._act_show_local_axes.setToolTip(
            "Show each frame member's local axes at its midpoint: x red, y green, z blue."
        )
        # View → Color By: one colour, or a colour per section, material or group.
        self._act_color_none = QAction("&Single Colour", self, checkable=True)
        self._act_color_section = QAction("By &Section", self, checkable=True)
        self._act_color_material = QAction("By &Material", self, checkable=True)
        self._act_color_group = QAction("By &Group", self, checkable=True)
        self._color_by_actions = {
            "none": self._act_color_none,
            "section": self._act_color_section,
            "material": self._act_color_material,
            "group": self._act_color_group,
        }
        self._color_by_group = QActionGroup(self)
        self._color_by_group.setExclusive(True)
        for action in self._color_by_actions.values():
            self._color_by_group.addAction(action)
        self._act_color_none.setChecked(True)
        self._act_show_grids = QAction("Show &Grids", self, checkable=True, checked=True)
        self.action("view.show_all_objects").setEnabled(False)
        self._act_show_grid_labels = QAction(
            "Show Grid &Labels", self, checkable=True, checked=True
        )

        # Camera dolly. The canvas multiplies its current zoom, so holding the
        # shortcut zooms smoothly rather than jumping to a fixed scale.
        self._act_zoom_in = QAction("Zoom &In", self, shortcut=QKeySequence("Ctrl++"))
        self._act_zoom_out = QAction("Zoom &Out", self, shortcut=QKeySequence("Ctrl+-"))
        # SAP2000's Rubber Band Zoom: the next left drag frames a rectangle.
        self._act_zoom_window = QAction("Zoom &Window", self, checkable=True)
        self._act_zoom_window.setToolTip("Drag a rectangle on the view to zoom into it")

        # Per-viewport hiding. These never touch the project: the ids stay in
        # the model, they are only not drawn in this one canvas.
        self._act_view_colors = QAction("&Colors…", self)

        # A second (third, …) viewport on the same project, in its own window.
        self._act_new_view = QAction(
            "New View &Window", self, shortcut=QKeySequence("Ctrl+Shift+N")
        )
        self._act_close_view = QAction("Close View Window", self)
        self._act_close_view.setEnabled(False)
        self._act_reset_layout = QAction("&Reset Window Layout", self)

        # Visibility toggles, one per ViewSettings field. _sync_visibility_actions
        # keeps their ticks truthful after any change, whichever path made it.
        self._act_vis_grids = QAction("Grids", self, checkable=True, checked=True)
        self._act_vis_grid_labels = QAction("Grid Labels", self, checkable=True, checked=True)
        self._act_vis_nodes = QAction("Nodes", self, checkable=True, checked=True)
        self._act_vis_frames = QAction("Frames", self, checkable=True, checked=True)
        self._act_vis_surfaces = QAction("Shells", self, checkable=True, checked=True)
        self._act_vis_supports = QAction("Restraints", self, checkable=True, checked=True)
        self._act_vis_footings = QAction("Footings", self, checkable=True, checked=True)
        self._act_vis_constraints = QAction("Constraints", self, checkable=True, checked=True)
        self._act_vis_frame_assignments = QAction(
            "Frame Assignments", self, checkable=True, checked=True
        )
        self._act_vis_releases = QAction("Releases", self, checkable=True, checked=True)
        self._act_vis_loads = QAction("Loads", self, checkable=True, checked=True)
        # Labels are off by default, matching ViewSettings.
        self._act_vis_node_labels = QAction("Node Labels", self, checkable=True)
        self._act_vis_element_labels = QAction("Element Labels", self, checkable=True)
        self._act_vis_extruded = QAction("Extruded Sections", self, checkable=True)

        self._act_about = QAction("&About OpenSees Studio…", self)
        # "\tF1" shows the key in the menu's shortcut column without binding it:
        # F1 belongs to the HelpController, which opens the page under the cursor.
        self._act_help_contents = QAction("&Help Contents\tF1", self)
        self._act_shortcuts = QAction("&Keyboard Shortcuts…", self)
        self._act_performance = QAction("&Performance monitor…", self)
        self._act_set_units = QAction("Set Display &Units…", self)
        self._act_solver_settings = QAction("&Solver…", self)

    def _annotate_help_topics(self) -> None:
        """Point every action at its help page (see ``core.help.ACTION_TOPICS``).

        One table, keyed by the action's attribute name, so an action added
        without help is visible in the coverage test rather than silently
        opening the contents page.
        """
        for attribute, topic_id in ACTION_TOPICS.items():
            action = getattr(self, attribute, None)
            if isinstance(action, QAction):
                action.setProperty(TOPIC_PROPERTY, topic_id)

    def _on_help_contents(self) -> None:
        """Help → Contents: the same F1, on the contents page."""
        self._help_controller.open_help("index")

    def _on_shortcuts(self) -> None:
        """Help → Keyboard Shortcuts: the page that lists every key."""
        self._help_controller.open_help("help.shortcuts")

    def _build_menu_bar(self) -> None:
        mb = self.menuBar()

        m_file = mb.addMenu("&File")
        act = self.action
        m_file.addActions(
            [
                act("file.new_model"),
                act("file.new"),
                act("file.new_2d"),
                act("file.new_2d_truss"),
                act("file.open"),
            ]
        )
        self._menu_recent = m_file.addMenu("Open &Recent")
        self._menu_recent.aboutToShow.connect(self._fill_recent_menu)
        self._menu_recent.menuAction().setProperty(TOPIC_PROPERTY, "file.recent")
        m_file.addSeparator()
        m_file.addActions([act("file.save"), act("file.save_as")])
        m_file.addAction(act("file.project_info"))
        m_file.addSeparator()
        m_import = m_file.addMenu("&Import")
        m_import.addAction(act("file.import_dxf"))
        m_import.addAction(act("file.import_s3d"))
        m_import.addAction(act("file.import_s2k"))
        m_import.addAction(act("file.import_ifc"))
        m_import.addAction(act("file.import_tcl"))
        m_export = m_file.addMenu("&Export")
        m_export.addAction(act("file.export_script"))
        m_export.addAction(act("file.export_ifc"))
        m_export.addAction(act("file.export_s2k"))
        m_export.addAction(act("file.export_report"))
        m_export.addAction(act("file.calc_memory"))
        m_file.addSeparator()
        m_file.addAction(act("file.run_batch"))
        m_file.addSeparator()
        m_file.addAction(act("file.quit"))

        m_edit = mb.addMenu("&Edit")
        m_edit.addActions([self._act_undo, self._act_redo])
        m_edit.addSeparator()
        m_edit.addActions([act("edit.copy"), act("edit.paste")])
        m_edit.addSeparator()
        m_edit.addActions(
            [self.action("edit.delete"), self.action("select.all"), self._act_clear_selection]
        )
        m_edit.addSeparator()
        m_edit.addActions(
            [act("edit.move"), act("edit.replicate"), act("edit.mirror"), act("edit.extrude")]
        )
        m_edit.addSeparator()
        m_edit.addAction(self.action("edit.table_editing"))
        m_edit.addAction(self.action("edit.check_duplicates"))
        m_edit.addAction(self.action("edit.merge_joints"))
        m_edit.addAction(self.action("edit.divide_frames"))
        m_edit.addAction(self.action("edit.join_frames"))
        m_edit.addAction(self.action("edit.mesh"))
        m_edit.addSeparator()
        m_edit.addAction(self.action("edit.delete_loads"))

        m_select = mb.addMenu("&Select")
        self._build_select_menu(m_select)

        m_define = mb.addMenu("&Define")
        m_define.addAction(self.action("define.grid"))
        m_define.addAction(self.action("define.grid_wizard"))
        m_define.addAction(self.action("define.storeys"))
        m_define.addAction(self.action("define.groups"))
        m_define.addAction(self.action("define.joint_patterns"))
        m_define.addAction(self.action("define.section_cuts"))
        m_define.addAction(self.action("define.mass_source"))
        m_define.addAction(self.action("define.seismic_loads"))
        m_define.addAction(self._act_add_node)
        m_define.addAction(self.action("define.create_shell"))
        m_define.addAction(self._act_frame_wizard)
        m_define.addAction(self._act_truss_wizard)
        m_define.addAction(self._act_warehouse_wizard)
        m_define.addAction(self.action("define.building_wizard"))
        m_define.addSeparator()
        m_define.addActions(
            [
                self.action("define.material_library"),
                self.action("define.default_materials"),
                self.action("define.mc2010"),
                self.action("define.friction_library"),
                self.action("define.material_tester"),
                self.action("define.ground_motions"),
                self.action("define.section_library"),
                self.action("define.concrete_section"),
                self.action("define.steel_deck"),
                self.action("define.section_designer"),
            ]
        )
        m_define.addSeparator()
        time_series_menu = m_define.addMenu("&Time Series")
        time_series_menu.addAction(self.action("define.linear_ts"))
        time_series_menu.addAction(self.action("define.path_ts"))
        time_series_menu.addAction(self.action("define.function_ts"))
        time_series_menu.addAction(self.action("define.constant_ts"))
        m_define.addAction(self.action("define.plain_pattern"))
        m_define.addAction(self.action("define.uniform_excitation"))
        m_define.addAction(self.action("define.multi_support"))
        m_define.addSeparator()
        m_define.addAction(self._act_load_combinations)
        m_define.addSeparator()
        m_define.addAction(self._act_custom_commands)

        m_assign = mb.addMenu("&Assign")
        # Joint submenu — operates on selected nodes.
        # The same lists feed the right-click menu of a selection (None = separator).
        self._joint_actions: list[QAction | None] = [
            self.action("assign.support"),
            self.action("assign.masses"),
            self.action("assign.springs"),
            self.action("assign.equal_dof"),
            self.action("assign.diaphragm"),
            self.action("assign.rigid_link"),
            self.action("assign.remove_constraints"),
            self.action("assign.load"),
            self.action("assign.imposed_displacement"),
            self.action("assign.zero_length"),
            self.action("assign.joint_pattern"),
            self.action("assign.zls"),
            self.action("assign.bearing"),
            self.action("assign.link"),
        ]
        self._frame_actions: list[QAction | None] = [
            self.action("assign.section"),
            self.action("assign.material"),
            self.action("assign.geom_transf"),
            self.action("assign.local_axes"),
            self.action("assign.integration"),
            None,
            self.action("assign.releases"),
            self.action("assign.end_offsets"),
            self.action("assign.insertion"),
            self.action("assign.modifiers"),
            self.action("assign.auto_mesh"),
            None,
            self.action("assign.distributed_load"),
            self.action("assign.trapezoidal_load"),
            self.action("assign.frame_point_load"),
            self.action("assign.temperature_load"),
            self.action("assign.tendon"),
            self.action("assign.hinge"),
            self.action("assign.wall"),
            None,
            self.action("assign.line_springs"),
            self.action("assign.pile"),
        ]
        self._area_actions: list[QAction | None] = [
            self.action("assign.shell_formulation"),
            None,
            self.action("assign.surface_load"),
            self.action("assign.floor_load"),
            None,
            self.action("assign.area_springs"),
            self.action("assign.edge_springs"),
        ]
        # Joint submenu — operates on selected nodes.
        m_joint = m_assign.addMenu("&Joint")
        _add_actions(m_joint, self._joint_actions)
        # The Restraints bar's presets, right under the dialog that does the rest.
        m_quick = QMenu("&Quick Restraint", m_joint)
        m_quick.addActions(self._restraint_actions())
        m_quick.menuAction().setProperty(TOPIC_PROPERTY, "assign.support")
        m_joint.insertMenu(m_joint.actions()[1], m_quick)
        # Frame submenu — operates on selected frame elements.
        _add_actions(m_assign.addMenu("&Frame"), self._frame_actions)
        _add_actions(m_assign.addMenu("A&rea"), self._area_actions)
        m_assign.addSeparator()
        m_assign.addAction(self.action("assign.group"))

        m_analyze = mb.addMenu("&Analyze")
        m_analyze.addAction(self._act_case_manager)
        m_analyze.addSeparator()
        m_analyze.addAction(self._act_check_model)
        m_analyze.addAction(self._act_check_stability)
        m_analyze.addAction(self._act_cancel_stability)
        m_analyze.addAction(self._act_run)
        m_analyze.addAction(self._act_auto_mesh_frames)
        m_analyze.addSeparator()
        m_analyze.addAction(self._act_run_all)
        m_analyze.addAction(self._act_run_selected)
        m_analyze.addSeparator()
        m_analyze.addAction(self._act_clear_results)

        m_display = mb.addMenu("&Display")
        m_display.addAction(self._act_show_load_assigns)
        m_display.addSeparator()
        m_display.addAction(self._act_select_results)
        m_display.addSeparator()
        m_display.addActions(
            [self.action("display.show_deformed"), self.action("display.show_mode_shape")]
        )
        m_display.addAction(self.action("display.show_force_diagram"))
        m_display.addActions(
            [self._act_show_reactions, self._act_reactions_table, self._act_reactions_dialog]
        )
        m_display.addAction(self.action("display.shell_contours"))
        m_display.addSeparator()
        m_display.addAction(self.action("display.show_time_history"))
        m_display.addAction(self.action("display.export_th_animation"))
        m_display.addAction(self.action("display.show_hysteresis"))
        m_display.addAction(self.action("display.show_pushover"))
        m_display.addAction(self.action("display.influence_line"))
        m_display.addAction(self.action("display.show_response_spectrum"))
        m_display.addSeparator()
        m_display.addAction(self._act_display_options)
        m_display.addSeparator()
        m_display.addAction(self.action("display.back_to_model"))

        # In the order a steel design is done: the basis and the analysis it
        # needs, the members, the check and its results, then the connections.
        # The single-connection calculators and the concrete check stand apart.
        m_design = mb.addMenu("Desi&gn")
        m_design.addActions(
            [
                self.action("design.design_basis"),
                self.action("design.direct_analysis"),
                self.action("design.notional_loads"),
            ]
        )
        m_design.addSeparator()
        m_design.addActions(
            [self.action("design.member_classification"), self.action("design.built_up")]
        )
        m_design.addSeparator()
        m_design.addActions(
            [
                self.action("design.steel_check"),
                self.action("design.steel_ratios"),
                self.action("design.drift_check"),
            ]
        )
        m_design.addSeparator()
        m_connections = m_design.addMenu("Steel &Connections")
        m_connections.addActions(
            [
                self.action("design.joint_connections"),
                self.action("design.base_plates"),
                self.action("design.connections"),
                self.action("design.gussets"),
                self.action("design.column_splices"),
                self.action("design.chapter_j"),
            ]
        )
        m_calculators = m_design.addMenu("Connection Calc&ulators")
        m_calculators.addActions([self.action("design.base_plate"), self.action("design.bolted")])
        m_design.addSeparator()
        m_design.addAction(self.action("design.concrete_check"))
        m_design.addAction(self.action("design.footings"))
        m_design.addAction(self.action("design.footing_pressures"))
        for menu, topic_id in (
            (m_connections, "design.joint_connections"),
            (m_calculators, "design.base_plate"),
        ):
            menu.menuAction().setProperty(TOPIC_PROPERTY, topic_id)

        m_view = mb.addMenu("&View")
        m_view.addAction(self._act_zoom_in)
        m_view.addAction(self._act_zoom_out)
        m_view.addAction(self._act_zoom_window)
        m_view.addAction(self._act_zoom_extents)
        m_view.addSeparator()
        m_view.addActions(
            [
                self.action("view.iso"),
                self.action("view.top"),
                self.action("view.front"),
                self.action("view.right"),
            ]
        )
        m_view.addActions([self.action("view.level_up"), self.action("view.level_down")])
        m_rotate = m_view.addMenu("&Rotate")
        m_rotate.addActions(
            [
                self.action("view.rotate_left"),
                self.action("view.rotate_right"),
                self.action("view.rotate_up"),
                self.action("view.rotate_down"),
            ]
        )
        m_rotate.addSeparator()
        m_rotate.addAction(self._act_spin)
        m_view.addSeparator()
        m_view.addAction(self._act_toggle_parallel)
        m_view.addAction(self._act_show_extruded)
        m_view.addAction(self._act_show_local_axes)
        m_color = m_view.addMenu("&Color By")
        m_color.addActions(list(self._color_by_actions.values()))
        m_view.addSeparator()
        # The model's own grid (a project entity) keeps its place next to the
        # other view furniture; the per-viewport toggles live in Visibility.
        m_view.addAction(self._act_show_grids)
        m_view.addAction(self._act_show_grid_labels)
        m_view.addSeparator()
        m_visibility = m_view.addMenu("&Visibility")
        m_visibility.addActions(
            [
                self._act_vis_grids,
                self._act_vis_grid_labels,
                self._act_vis_nodes,
                self._act_vis_frames,
                self._act_vis_surfaces,
                self._act_vis_supports,
                self._act_vis_footings,
                self._act_vis_constraints,
                self._act_vis_frame_assignments,
                self._act_vis_releases,
                self._act_vis_loads,
                self._act_show_local_axes,
                self._act_vis_node_labels,
                self._act_vis_element_labels,
                self._act_vis_extruded,
            ]
        )
        m_view.addSeparator()
        m_view.addAction(self.action("view.hide_selected"))
        m_view.addAction(self.action("view.isolate_selected"))
        m_view.addAction(self.action("view.invert_visible"))
        m_view.addAction(self.action("view.show_all_objects"))
        m_view.addSeparator()
        m_view.addAction(self.action("view.grid_line_view"))
        m_view.addAction(self._act_view_colors)
        m_view.addSeparator()
        m_view.addAction(self._act_new_view)
        m_view.addAction(self._act_close_view)
        m_view.addSeparator()
        # A closed panel comes back from here; Qt keeps each check in step.
        m_panels = m_view.addMenu("&Panels")
        m_panels.menuAction().setProperty(TOPIC_PROPERTY, "view.panels")
        for dock in self._layout_docks:
            toggle = dock.toggleViewAction()
            toggle.setProperty(TOPIC_PROPERTY, "view.panels")
            m_panels.addAction(toggle)
        m_view.addAction(self._act_reset_layout)

        m_tools = mb.addMenu("&Tools")
        m_tools.addActions(
            [
                self._act_tool_select,
                self._act_tool_draw_node,
                self._act_tool_draw_frame,
                self._act_tool_draw_truss,
                self._act_tool_quick_frame,
                self._act_tool_draw_shell,
                self._act_tool_quick_shell,
                self._act_tool_measure,
            ]
        )

        m_options = mb.addMenu("&Options")
        m_options.addAction(self._act_set_units)
        m_options.addAction(self._act_solver_settings)
        m_options.addAction(self.action("options.lock_model"))
        m_options.addAction(self._act_use_ribbon)
        m_options.addAction(self._act_dark_mode)
        m_language = m_options.addMenu("&Language")
        self._language_actions: dict[str, QAction] = {}
        for code, label in LANGUAGES.items():
            action = QAction(label, self, checkable=True)
            action.setProperty("_i18n_original", label)  # a language's own name stays
            action.triggered.connect(lambda _checked=False, c=code: self._on_language(c))
            m_language.addAction(action)
            self._language_actions[code] = action
        self._language_actions[stored_language()].setChecked(True)
        m_autosave = m_options.addMenu("&Autosave Recovery Copy")
        m_autosave.menuAction().setProperty(TOPIC_PROPERTY, "options.autosave")
        group = QActionGroup(self)
        self._autosave_actions: dict[int, QAction] = {}
        for minutes in AUTOSAVE_CHOICES:
            label = "Off" if minutes == 0 else f"Every {minutes} Minutes"
            action = QAction(label, self, checkable=True)
            action.setProperty(TOPIC_PROPERTY, "options.autosave")
            action.triggered.connect(lambda _checked=False, m=minutes: self._set_autosave(m))
            group.addAction(action)
            m_autosave.addAction(action)
            self._autosave_actions[minutes] = action
        m_shortcuts = m_options.addMenu("&Keyboard Shortcuts")
        m_shortcuts.menuAction().setProperty(TOPIC_PROPERTY, "options.keyboard_shortcuts")
        group = QActionGroup(self)
        self._shortcut_profile_actions: dict[str, QAction] = {}
        for profile, label in shortcut_profiles.PROFILES.items():
            action = QAction(label, self, checkable=True)
            action.setProperty(TOPIC_PROPERTY, "options.keyboard_shortcuts")
            action.triggered.connect(
                lambda _checked=False, p=profile: self._set_shortcut_profile(p)
            )
            group.addAction(action)
            m_shortcuts.addAction(action)
            self._shortcut_profile_actions[profile] = action

        m_help = mb.addMenu("&Help")
        m_help.addAction(self._act_help_contents)
        m_help.addAction(self._act_shortcuts)
        m_help.addSeparator()
        m_help.addAction(self._act_performance)
        m_help.addAction(self._act_about)

        # A greyed-out entry's tooltip says what it waits for (_explain_disabled_actions).
        for menu in mb.findChildren(QMenu):
            menu.setToolTipsVisible(True)

        self._menus = {
            "file": m_file,
            "edit": m_edit,
            "select": m_select,
            "define": m_define,
            "assign": m_assign,
            "analyze": m_analyze,
            "display": m_display,
            "design": m_design,
            "view": m_view,
            "options": m_options,
            "help": m_help,
        }

    def _build_view_toolbar(self) -> None:
        tb = QToolBar("View", self)
        tb.setObjectName("viewToolbar")
        tb.setMovable(True)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        tb.addAction(self._act_zoom_extents)
        tb.addAction(self._act_zoom_window)
        tb.addSeparator()
        tb.addAction(self.action("view.iso"))
        tb.addAction(self.action("view.top"))
        tb.addAction(self.action("view.front"))
        tb.addAction(self.action("view.right"))
        tb.addSeparator()
        for action in (
            self.action("view.rotate_left"),
            self.action("view.rotate_right"),
            self.action("view.rotate_up"),
            self.action("view.rotate_down"),
            self._act_spin,
        ):
            tb.addAction(action)
        tb.addSeparator()
        # SAP2000-style "Level" combo: when the user is in Top / Front /
        # Right mode AND the grid has multiple perpendicular-axis lines,
        # this picks which one is active for drawing + snap filtering.
        tb.addWidget(QLabel("Level: "))
        tb.addWidget(self.viewport.level_combo)
        tb.addAction(self.action("view.level_up"))
        tb.addAction(self.action("view.level_down"))
        tb.addSeparator()
        # Which results case the viewport represents: the layers (deformed
        # shape, diagrams, reactions) follow it.
        tb.addWidget(QLabel("Case: "))
        self._case_combo = QComboBox()
        self._case_combo.setMinimumWidth(190)
        self._case_combo.setToolTip(
            "Results case shown in the viewport. Deformed shape, force diagram, "
            "contours and reactions all read this case."
        )
        self._case_combo.currentIndexChanged.connect(self._on_case_changed)
        tb.addWidget(self._case_combo)
        self._step_back = QToolButton()
        self._step_back.setText("\u25c0")
        self._step_back.setToolTip("Previous step of this case")
        self._step_back.setEnabled(False)
        self._step_back.clicked.connect(lambda: self._shift_step(-1))
        tb.addWidget(self._step_back)
        self._step_forward = QToolButton()
        self._step_forward.setText("\u25b6")
        self._step_forward.setToolTip("Next step of this case")
        self._step_forward.setEnabled(False)
        self._step_forward.clicked.connect(lambda: self._shift_step(1))
        tb.addWidget(self._step_forward)
        self._step_label = QLabel("")
        tb.addWidget(self._step_label)
        tb.addSeparator()
        tb.addAction(self._act_toggle_parallel)
        tb.addAction(self._act_show_extruded)

    def _build_tools_toolbar(self) -> None:
        tb = QToolBar("Tools", self)
        tb.setObjectName("toolsToolbar")
        tb.setMovable(True)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb)
        tb.addAction(self._act_tool_select)
        tb.addAction(self._act_tool_draw_node)
        tb.addAction(self._act_tool_draw_frame)
        tb.addAction(self._act_tool_draw_truss)
        tb.addAction(self._act_tool_quick_frame)
        tb.addAction(self._act_tool_draw_shell)
        tb.addAction(self._act_tool_quick_shell)
        tb.addAction(self._act_tool_measure)
        # The plate section Draw Shell gives its shells; shown while it is armed.
        shell_sections = tb.addWidget(self.drawing.shell_section_combo)
        shell_sections.setVisible(False)
        self.drawing.shell_section_action = shell_sections
        # The section Draw Frame gives its frames; shown while it is armed.
        sections = tb.addWidget(self.drawing.section_combo)
        sections.setVisible(False)
        self.drawing.section_action = sections

    def _build_snap_toolbar(self) -> None:
        """The left-hand object-snap icon bar (midpoint / perpendicular / on member)."""
        tb = QToolBar("Object Snap", self)
        tb.setObjectName("objectSnapToolbar")
        tb.setMovable(True)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb)
        for action in self._snap_actions.values():
            tb.addAction(action)
        self._apply_snap_modes()

    def _build_restraints_toolbar(self) -> None:
        """Fixed / Pinned / Roller / Free on the selected joints, one click each."""
        tb = QToolBar("Restraints", self)
        tb.setObjectName("restraintsToolbar")
        tb.setMovable(True)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb)
        tb.addActions(self._restraint_actions())

    def _build_selection_toolbar(self) -> None:
        """SAP2000's side buttons: all, ps (previous selection), clr, line."""
        tb = QToolBar("Selection", self)
        tb.setObjectName("selectionToolbar")
        tb.setMovable(True)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb)
        tb.addActions(self._selection_toolbar_actions())

    def _selection_toolbar_actions(self) -> list[QAction]:
        return [
            self.action("select.all"),
            self.action("select.previous"),
            self._act_clear_selection,
            self._act_select_line,
        ]

    def _on_select_line(self, on: bool) -> None:
        """Select → Intersecting Line: the next left drag on the view draws a line."""
        for canvas in [self._main_canvas, *(window.canvas for window in self._view_windows)]:
            canvas.set_line_select(on and canvas is self._canvas)
        if on:
            self.statusBar().showMessage(
                "Drag a line across the members to select (Ctrl: deselect); Esc cancels."
            )

    def _on_zoom_window(self, on: bool) -> None:
        """View → Zoom Window: the next left drag on the active view frames a rectangle."""
        for canvas in [self._main_canvas, *(window.canvas for window in self._view_windows)]:
            canvas.set_zoom_window(on and canvas is self._canvas)
        if on:
            self.statusBar().showMessage(tr("Drag a rectangle to zoom into it; Esc cancels."))

    def _restraint_actions(self) -> list[QAction]:
        return [
            self._act_restraint_fixed,
            self._act_restraint_pinned,
            self._act_restraint_roller,
            self._act_restraint_free,
        ]

    def _on_quick_restraint(self) -> None:
        """A Restraints bar button: its preset on the selected joints, as one undo step."""
        from opensees_studio.views.dialogs.assign_support import PRESETS

        action = self.sender()
        sel_nodes = set(self._canvas.selection.nodes)
        if not isinstance(action, QAction) or not sel_nodes:
            return
        preset = str(action.data())
        try:
            self._vm.apply_command(SetRestraintCommand(self._vm, sel_nodes, PRESETS[preset]))
        except Exception as exc:
            QMessageBox.critical(self, "Assign Support failed", str(exc))
            return
        name = action.text().replace("&", "")
        self.statusBar().showMessage(f"{name}: {len(sel_nodes)} joint(s).", 4000)

    def _apply_snap_modes(self) -> None:
        """Push the checked icon states to every viewport."""
        self._snap_modes = {
            mode for mode, action in self._snap_actions.items() if action.isChecked()
        }
        canvases = [self._main_canvas, *(window.canvas for window in self._view_windows)]
        for canvas in canvases:
            canvas.set_snap_modes(self._snap_modes)

    def _on_snap_mode_toggled(self, _checked: bool = False) -> None:
        """An object-snap icon changed: apply it and say what is enabled."""
        self._apply_snap_modes()
        enabled = [mode.value for mode in SnapMode if mode in self._snap_modes]
        self.statusBar().showMessage(
            "Object snaps: " + (", ".join(enabled) if enabled else "none"), 4000
        )

    def _on_cursor_moved(self, point: object) -> None:
        """Show the model point under the pointer, in the project's length unit."""
        project = self._vm.project
        if project is None or not isinstance(point, tuple):
            self._cursor_label.setText("")
            return
        x, y, z, kind = point
        unit = labels_for(project.meta.units).length
        axes = (("X", x), ("Z", z)) if project.ndm == 2 else (("X", x), ("Y", y), ("Z", z))
        text = "  ".join(f"{name} {value:.3f}" for name, value in axes)
        # The snap behind the point: grid, plane, midpoint, perpendicular, on member.
        label = "on member" if kind == "on_element" else str(kind)
        self._cursor_label.setText(f"{text} {unit}" + (f"  ({tr(label)})" if label else ""))

    def _build_status_bar(self) -> None:
        # A run without a dialog (Run All, Run Selected) shows and stops here.
        self._run_status = RunStatusWidget(self._runner, self)
        self.statusBar().addPermanentWidget(self._run_status)
        # Where the pointer is in the model: the point a click would place.
        self._cursor_label = QLabel("")
        self._cursor_label.setToolTip(
            "Model coordinates under the pointer: the grid intersection or member "
            "snap a click would use, or the point on the working plane."
        )
        self.statusBar().addPermanentWidget(self._cursor_label)
        self._status_label = QLabel("No project")
        self.statusBar().addPermanentWidget(self._status_label)
        # The model lock, where SAP2000 users look for the padlock.
        self.model_lock.button.setToolTip(self.action("options.lock_model").toolTip())
        self.model_lock.button.clicked.connect(self.action("options.lock_model").trigger)
        self.statusBar().addPermanentWidget(self.model_lock.button)

        # SAP2000-style bottom-right unit picker. Drives the same state
        # as Options → Set Display Units — changes here are instantly
        # reflected in the menu dialog (and vice-versa).
        self._units_combo = QComboBox()
        self._units_combo.setToolTip(
            "Display units — results, diagrams and tables convert to this "
            "system. The model keeps the units its values were entered in."
        )
        for u in UnitSystem:
            self._units_combo.addItem(u.value, u)
        self._units_combo.currentIndexChanged.connect(
            self._on_units_combo_changed,
        )
        self.statusBar().addPermanentWidget(QLabel("Units:"))
        self.statusBar().addPermanentWidget(self._units_combo)

    # ── ribbon ────────────────────────────────────────────────────
    #: ribbon tab → the help page the Ayuda panel shows.
    RIBBON_HELP: ClassVar[dict[str, str]] = {
        "home": "file.new_model",
        "define": "define.grid",
        "draw": "tools.draw_frame",
        "select": "select.menu",
        "assign": "assign.support",
        "loads": "assign.load",
        "analyze": "analyze.run",
        "results": "display.deformed",
        "design": "design.steel_check",
        "view": "view.panels",
        "help": "help.contents",
    }

    def _build_ribbon(self) -> None:
        """The ribbon toolbar and the project dock.

        The ribbon places the menu actions by ``RIBBON_LAYOUT``, so every menu
        command has a button and the two cannot drift apart (see the coverage
        test). Every action takes its SVG icon first, so the menus, the toolbars
        and the ribbon show the same picture.
        """
        apply_command_icons(self)
        self._ribbon = RibbonBar(build_ribbon_tabs(self), self)
        self._ribbon.tabChanged.connect(self._on_ribbon_tab_changed)
        self._ribbon.menusRequested.connect(self._show_menu_bar)

        bar = QToolBar("Ribbon", self)
        bar.setObjectName("ribbonToolbar")
        bar.setMovable(False)
        bar.addWidget(self._ribbon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self._ribbon_toolbar = bar

        dock = QDockWidget(tr("Project"), self)
        dock.setObjectName("projectDock")
        self._project_dock = ProjectDock(dock)
        dock.setWidget(self._project_dock)
        dock.setMinimumWidth(260)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        props = self.findChild(QDockWidget, "propertiesDock")
        if props is not None:
            self.tabifyDockWidget(props, dock)
            dock.raise_()

        self._project_dock.editRequested.connect(self._on_project_edit)
        self._project_dock.tableRequested.connect(self.model_tools.table_editing)
        self._project_dock.deleteRequested.connect(self.model_tools.delete_selection)

        self._act_use_ribbon.toggled.connect(self._apply_interface_mode)
        self._menus_visible = True
        self._dark_mode = False
        self._vm.projectChanged.connect(self._on_project_changed_for_ribbon)
        self._vm.modelMutated.connect(self._on_model_mutated_for_ribbon)

        self._apply_interface_mode(self._stored_use_ribbon())

    # ── ribbon state ──────────────────────────────────────────────
    def _stored_use_ribbon(self) -> bool:
        """Whether the ribbon is on; the default is on."""
        settings = QSettings()
        stored = settings.value("useRibbon", "true")
        return str(stored).lower() not in {"false", "0", "no"}

    def _store_use_ribbon(self, on: bool) -> None:
        QSettings().setValue("useRibbon", "true" if on else "false")

    def _apply_interface_mode(self, ribbon: bool | None = None) -> None:
        """Show the ribbon and hide the menus, or the classic menus."""
        on = self._act_use_ribbon.isChecked() if ribbon is None else bool(ribbon)
        if on != self._act_use_ribbon.isChecked():
            self._act_use_ribbon.blockSignals(True)
            self._act_use_ribbon.setChecked(on)
            self._act_use_ribbon.blockSignals(False)
        self._ribbon_toolbar.setVisible(on)
        self.menuBar().setVisible(not on)
        # macOS draws the menu bar globally, so its widget visibility is not a
        # reliable signal: the window keeps the state it asked for.
        self._menus_visible = not on
        self._ribbon.set_menus_visible(not on)
        self._store_use_ribbon(on)
        if on:
            self._project_dock.show_topic(
                self.RIBBON_HELP.get(self._ribbon.currentTab(), "help.contents")
            )

    def _show_menu_bar(self) -> None:
        """The ribbon's **Menús** button: toggle the classic menu bar."""
        visible = not self._menus_visible
        self.menuBar().setVisible(visible)
        self._menus_visible = visible
        self._ribbon.set_menus_visible(visible)

    # ── dark mode ─────────────────────────────────────────────────
    def _stored_dark_mode(self) -> bool:
        stored = QSettings().value("darkMode", "false")
        return str(stored).lower() in {"true", "1", "yes"}

    def _store_dark_mode(self, on: bool) -> None:
        QSettings().setValue("darkMode", "true" if on else "false")

    def _apply_dark_mode(self, on: bool | None = None) -> None:
        """Swap the palette and the 3D viewport style; remember the choice."""
        dark = self._act_dark_mode.isChecked() if on is None else bool(on)
        if dark != self._act_dark_mode.isChecked():
            self._act_dark_mode.blockSignals(True)
            self._act_dark_mode.setChecked(dark)
            self._act_dark_mode.blockSignals(False)
        self._dark_mode = dark
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, dark)
        self._canvas.apply_style(viewport_style(dark))
        for window in self._view_windows:
            window.canvas.apply_style(viewport_style(dark))
        self._store_dark_mode(dark)

    def _on_ribbon_tab_changed(self, tab_id: str) -> None:
        topic_id = self.RIBBON_HELP.get(tab_id, "help.contents")
        self._project_dock.show_topic(topic_id)

    def _on_project_changed_for_ribbon(self, project: object) -> None:
        self._project_dock.set_project(project)

    def _on_model_mutated_for_ribbon(self) -> None:
        self._project_dock.set_project(self._vm.project)

    def _on_project_edit(self, category: str, entity_id: int) -> None:
        """Editar: select the row's entity and show it in Properties."""
        if category == "nodes":
            self._canvas.selection.set_selection({entity_id}, set())
        elif category == "elements":
            self._canvas.selection.set_selection(set(), {entity_id})
        else:
            self._log(f"Editar: {category} #{entity_id}")
            return
        self._log(f"Editar: {category} #{entity_id}")

        self.statusBar().showMessage(tr("Ready"))

    def _on_units_combo_changed(self, _idx: int) -> None:
        """Status-bar unit picker → ``project.meta.display_units``.

        Qt stores the userData as a bare string (UnitSystem inherits
        from str), so we re-cast to the enum before writing through
        and logging. The model's own system is untouched, and every view
        that shows a number is refreshed with the new conversion.
        """
        if self._vm.project is None:
            return

        raw = self._units_combo.currentData()
        if raw is None:
            return
        chosen = raw if isinstance(raw, UnitSystem) else UnitSystem(str(raw))
        if chosen is self._current_display_units():
            return
        self._set_display_units(chosen)

    def _current_display_units(self) -> UnitSystem:
        """The system results are shown in (the model's own when none was picked)."""
        if self._vm.project is None:
            return UnitSystem.SI_M_N
        meta = self._vm.project.meta
        return meta.display_units if meta.display_units is not None else meta.units

    def _set_display_units(self, chosen: UnitSystem) -> None:
        """Change the display system and refresh everything that shows a number."""
        if self._vm.project is None:
            return
        self._vm.project.meta.display_units = chosen
        self._vm.mark_dirty()
        self._sync_units_combo()
        self._log(f"Display units set to {chosen.value}.")
        self._apply_display_units()

    def _apply_display_units(self) -> None:
        """Re-render every result view in the project's current display units.

        The model is untouched — OpenSees numbers do not move — but each number
        read off a diagram, table or curve is converted, so a unit change is
        visible without re-running anything.
        """
        if self._vm.project is None:
            return
        converter = UnitConverter.of(self._vm.project.meta)
        # Results panel: displacements, reactions, element forces, curves.
        self._results_panel.refresh(self._vm.project)
        # Active post-processing dock (diagram, deformed shape, plots).
        if not self.display.refresh_units() and self.results.latest is not None:
            self._canvas.render()
        self.display.set_member_units(converter)
        self._log(
            f"Displayed values converted to {converter.target.value} (model units unchanged).",
        )

    def _sync_units_combo(self) -> None:
        """Reflect the project's current display units in the status-bar combo.

        Called after project load / menu-based unit change so the
        status-bar widget stays consistent with the model state. When the
        display system differs from the model's, the tooltip says so — the
        typed values are in the model's system, not in the picker's.
        """
        if self._vm.project is None:
            return
        target = self._current_display_units()
        idx = self._units_combo.findData(target)
        if idx >= 0 and idx != self._units_combo.currentIndex():
            self._units_combo.blockSignals(True)
            self._units_combo.setCurrentIndex(idx)
            self._units_combo.blockSignals(False)
        model = self._vm.project.meta.units
        tooltip = (
            "Display units — results, diagrams and tables convert to this "
            "system. The model keeps the units its values were entered in."
        )
        if target is not model:
            tooltip += f"  Model units: {model.value} — typed values are unchanged."
        self._units_combo.setToolTip(tooltip)

    def _wire(self) -> None:
        # File and every other declared command (views/actions).
        self._actions.wire(self)
        self._act_about.triggered.connect(self._on_about)
        self._act_help_contents.triggered.connect(self._on_help_contents)
        self._act_shortcuts.triggered.connect(self._on_shortcuts)
        self._act_performance.triggered.connect(self._on_performance)
        self._act_set_units.triggered.connect(self._on_set_units)
        self._act_solver_settings.triggered.connect(self._on_solver_settings)

        # Edit
        # Delete, Undo, Redo and the selection keys have to work while the ribbon
        # hides the menu bar and shows a tab without the Edit group: a shortcut
        # only fires when a visible widget carries its action.
        self.addActions(
            [
                self.action("edit.delete"),
                self._act_undo,
                self._act_redo,
                self.action("select.all"),
                self._act_clear_selection,
            ]
        )
        self._act_clear_selection.triggered.connect(self._on_clear_selection)

        # Tools
        self._act_tool_select.triggered.connect(self.drawing.select)
        self._act_tool_draw_node.triggered.connect(self.drawing.draw_node)
        self._act_tool_draw_frame.triggered.connect(self.drawing.draw_frame)
        self._act_tool_draw_truss.triggered.connect(self.drawing.draw_truss)
        self._act_tool_quick_frame.triggered.connect(self.drawing.quick_frame)
        self._act_tool_quick_shell.triggered.connect(self.drawing.quick_shell)
        self._act_tool_draw_shell.triggered.connect(self.drawing.draw_shell)
        self._act_tool_measure.triggered.connect(self.drawing.measure)
        for action in self._snap_actions.values():
            action.toggled.connect(self._on_snap_mode_toggled)

        # Define
        self._act_show_grids.triggered.connect(self.grids.set_shown)
        self._act_show_grid_labels.triggered.connect(self.grids.set_labels_shown)
        self._canvas.contextMenuRequested.connect(self._on_canvas_context_menu)
        self._canvas.cursorMoved.connect(self._on_cursor_moved)
        self._canvas.lineSelectFinished.connect(lambda: self._act_select_line.setChecked(False))
        self._act_select_line.toggled.connect(self._on_select_line)
        self._act_add_node.triggered.connect(self._on_add_node)
        self._act_frame_wizard.triggered.connect(self._on_frame_wizard)
        self._act_truss_wizard.triggered.connect(self._on_truss_wizard)
        self._act_warehouse_wizard.triggered.connect(self._on_warehouse_wizard)
        self._act_load_combinations.triggered.connect(self._on_load_combinations)

        # Assign
        for action in self._restraint_actions():
            action.triggered.connect(self._on_quick_restraint)
        self._act_custom_commands.triggered.connect(self._on_custom_commands)

        # Analyze
        self._act_case_manager.triggered.connect(self._on_case_manager)
        self._act_check_model.triggered.connect(self._on_check_model)
        self._act_run.triggered.connect(self._on_run_analysis)
        self._act_run_all.triggered.connect(self._on_run_all_cases)
        self._act_run_selected.triggered.connect(self._on_run_selected_cases)
        self._act_clear_results.triggered.connect(self._on_clear_results)
        self._act_auto_mesh_frames.toggled.connect(self._on_toggle_auto_mesh_frames)
        self._act_dark_mode.toggled.connect(self._apply_dark_mode)
        self._act_check_stability.triggered.connect(self._on_check_stability)
        self._act_cancel_stability.triggered.connect(self._stability.cancel)
        self._stability.log.connect(self._log)
        self._stability.progress.connect(self._on_stability_progress)
        self._stability.finished.connect(self._on_stability_report)
        self._stability.failed.connect(self._on_stability_failed)
        self._stability.runningChanged.connect(self._on_stability_running_changed)
        # The runner's own flag flips to False only after ``finished`` has been
        # handled (teardown emits it), so the batch actions would stay disabled
        # for the rest of the session without this connection.
        self._runner.runningChanged.connect(self._on_runner_running_changed)

        # Display
        self._act_select_results.triggered.connect(self._on_select_results)
        self._act_show_reactions.toggled.connect(self._on_show_reactions)
        self._act_reactions_table.triggered.connect(self._on_reactions_table)
        self._act_reactions_dialog.triggered.connect(self._on_reactions_dialog)
        self._act_display_options.triggered.connect(self._on_display_options)
        self._act_show_load_assigns.triggered.connect(self._on_show_load_assigns)
        self._vm.undo_stack.indexChanged.connect(self.model_lock.on_undo_index_changed)

        # AnalysisRunner: stream log to console + show results in panel
        self._runner.log.connect(self._console.appendPlainText)
        self._runner.caseFinished.connect(self._on_case_finished)
        self._runner.finished.connect(self._on_analysis_finished)
        self._runner.failed.connect(self._on_analysis_failed)
        self._runner.cancelled.connect(lambda: self._log("Analysis cancelled."))

        # View
        self._act_zoom_extents.triggered.connect(self._canvas.reset_camera)
        self._act_spin.toggled.connect(self.viewport.spin)
        self._act_toggle_parallel.toggled.connect(self.viewport.toggle_parallel)
        # Lambdas: ``triggered`` sends ``checked`` (False), which the canvas
        # would take as its zoom factor (Zoom Out divided by it), and the active
        # viewport is looked up on every click, not frozen at start-up.
        self._act_zoom_in.triggered.connect(lambda: self._canvas.zoom_in())
        self._act_zoom_out.triggered.connect(lambda: self._canvas.zoom_out())
        self._act_zoom_window.toggled.connect(self._on_zoom_window)
        self._canvas.zoomWindowFinished.connect(lambda: self._act_zoom_window.setChecked(False))
        self._act_view_colors.triggered.connect(self._on_view_colors)
        self._act_new_view.triggered.connect(self._on_new_view_window)
        self._act_reset_layout.triggered.connect(self._on_reset_layout)
        self._act_close_view.triggered.connect(self._on_close_view_window)
        # "Show Extruded Sections" and its Visibility twin are the same state,
        # so both drive it and _sync_visibility_actions keeps both ticked.
        self._act_show_extruded.toggled.connect(self._on_vis_extruded)
        for mode, action in self._color_by_actions.items():
            action.triggered.connect(lambda _=False, mode=mode: self._on_color_by(mode))
        self._act_vis_extruded.toggled.connect(self._on_vis_extruded)
        for action, field in (
            (self._act_vis_grids, "show_grids"),
            (self._act_vis_grid_labels, "show_grid_labels"),
            (self._act_vis_nodes, "show_nodes"),
            (self._act_vis_frames, "show_frames"),
            (self._act_vis_surfaces, "show_surfaces"),
            (self._act_vis_supports, "show_supports"),
            (self._act_vis_footings, "show_footings"),
            (self._act_vis_constraints, "show_constraints"),
            (self._act_vis_frame_assignments, "show_frame_assignments"),
            (self._act_vis_releases, "show_releases"),
            (self._act_vis_loads, "show_loads"),
            (self._act_show_local_axes, "show_local_axes"),
        ):
            action.toggled.connect(partial(self._on_visibility_toggle, field))
        self._act_vis_node_labels.toggled.connect(self._on_vis_node_labels)
        self._act_vis_element_labels.toggled.connect(self._on_vis_element_labels)

        # ViewModel
        self._vm.projectChanged.connect(self._on_project_changed)
        self._vm.modelMutated.connect(self._on_model_mutated)
        self._vm.dirtyChanged.connect(self._on_dirty_changed)
        self._vm.noticePosted.connect(lambda msg: self.statusBar().showMessage(msg, 10000))

        # Selection → properties + action enablement
        self._canvas.selection.selectionChanged.connect(self._on_selection_changed)
        self._canvas.element_tooltip = self.display.element_tooltip
        self._canvas.node_tooltip = self.display.node_tooltip
        # The deformed shape and the mode shapes are read at the joints: the
        # members would only get in the way of the pointer there.
        self._canvas.element_tooltips_enabled = self.display.element_tooltips_enabled

        # Contextual help: F1 anywhere, on the topic of what is on screen.
        self._annotate_help_topics()
        self._help_controller = HelpController(self)
        self._help_controller.install()

    # ── slots: file ──────────────────────────────────────────────────
    def _on_new(self) -> None:
        if not self._confirm_discard_changes("Creating a new project"):
            return
        self._vm.new_project(dead_case=True, default_materials=True)

    def _on_new_model(self) -> None:
        """File → New Model: units and a template, as SAP2000 starts a model."""
        from opensees_studio.views.dialogs.new_model import NewModelDialog

        stored = QSettings().value(NEW_MODEL_UNITS_KEY, UnitSystem.SI_M_N.value)
        try:
            units = UnitSystem(stored)
        except ValueError:
            units = UnitSystem.SI_M_N
        dlg = NewModelDialog(units, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._confirm_discard_changes("Creating a new model"):
            return
        units = dlg.units()
        QSettings().setValue(NEW_MODEL_UNITS_KEY, units.value)
        self._start_template(dlg.template(), units, dlg)

    def _start_template(self, key: str, units: UnitSystem, dlg: Any) -> None:
        """Create the model a New Model template asks for, then its wizard or members."""
        from opensees_studio.core.templates import (
            TEMPLATE_NDF,
            TEMPLATES,
            build_beam,
            build_space_frame,
        )

        ndm, ndf = TEMPLATE_NDF[key]
        self._vm.new_project(ndm, ndf, dead_case=True, units=units, default_materials=True)
        self._log(f"New model: {TEMPLATES[key]} ({units.value}).")
        if key == "grid":
            self.grids.wizard()
        elif key == "truss2d":
            self._on_truss_wizard()
        elif key == "frame2d":
            self._create_portal_frame(with_grid=True)
        elif key == "warehouse":
            self._on_warehouse_wizard()
        elif key == "building":
            self.generators.create_building()
        elif key in ("beam", "frame3d"):
            project = self._vm.project
            assert project is not None
            try:
                section = make_default_section(project.next_section_id(), project)
                if key == "beam":
                    spans, span = dlg.beam_numbers()
                    model = build_beam(spans, span, section_id=section.id)
                else:
                    model = build_space_frame(
                        *dlg.frame_numbers(),
                        column_section_id=section.id,
                        beam_section_id=section.id,
                    )
                insert_generated(
                    self._vm,
                    GeneratedModel(
                        sections=[section],
                        nodes=model.nodes,
                        elements=model.elements,
                        grid=model.grid,
                        replace_grids=True,
                    ),
                    text=f"New model: {TEMPLATES[key]}",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Cannot create the model", str(exc))
                return
            self._log(f"{TEMPLATES[key]}: {model.summary()}")
            if key == "beam":
                self.viewport.front()
            self._canvas.reframe()

    def _on_new_2d(self) -> None:
        """Planar frame model — (ndm=2, ndf=3): Ux, Uz, Ry per joint, then the wizard.

        Right choice when beam-columns are in the mix; for a pure truss use
        'New 2D Truss' so the solver doesn't face unrestrained rotational DOFs.

        An empty 2D frame project is just an empty canvas, and the only plane it
        can build in is the wizard's XZ (Z up), so the wizard opens here: it is what
        turns "new 2D frame" into a frame. Cancelling leaves the empty project,
        which is still the right start for drawing by hand.
        """
        if not self._confirm_discard_changes("Creating a new 2D frame"):
            return
        self._vm.new_project(ndm=2, ndf=3, dead_case=True, default_materials=True)
        self._log("New 2D frame project (ndm = 2, ndf = 3).")
        self._create_portal_frame(with_grid=True)

    def _on_new_2d_truss(self) -> None:
        """Planar truss model — (ndm=2, ndf=2): only Ux, Uz per joint (the X-Z plane).

        Matches OpenSees's ``model BasicBuilder -ndm 2 -ndf 2`` from
        the Basic Truss Example and keeps the stiffness matrix well
        posed (no empty rotational rows).
        """
        if not self._confirm_discard_changes("Creating a new project"):
            return
        self._vm.new_project(ndm=2, ndf=2, dead_case=True, default_materials=True)
        self._log("New empty project.")

    def _on_open(self) -> None:
        if not self._confirm_discard_changes("Opening another project"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open project",
            "",
            f"OpenSees Studio model (*{PROJECT_FILE_SUFFIX});;All files (*)",
        )
        if not path:
            return
        self.open_project(path)

    def _on_open_recent(self, path: str) -> None:
        """File → Open Recent, or a project picked on the start page."""
        if not self._confirm_discard_changes("Opening another project"):
            return
        self.open_project(path)

    def _fill_recent_menu(self) -> None:
        """Rebuild File → Open Recent from the stored list each time it opens."""
        menu = self._menu_recent
        menu.clear()
        paths = self._recent.paths()
        for number, path in enumerate(paths, 1):
            action = menu.addAction(f"&{number % 10} {path.name}")
            action.setToolTip(str(path))
            action.setStatusTip(str(path))
            action.triggered.connect(lambda _checked=False, p=str(path): self._on_open_recent(p))
        if not paths:
            menu.addAction("No recent projects").setEnabled(False)
        menu.addSeparator()
        clear = menu.addAction("&Clear List")
        clear.setEnabled(bool(paths))
        clear.triggered.connect(self._on_clear_recent)

    def _on_clear_recent(self) -> None:
        self._recent.clear()
        self._start_page.refresh()

    def open_project(self, path: str | Path) -> bool:
        """Open ``path``; offer to restore a newer pre-run snapshot if one exists.

        Returns True when the project was opened (with or without the
        recovered changes).
        """
        try:
            with self._busy(f"Opening {Path(path).name}…"):
                self._vm.open(path)
            self._log(f"Opened: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return False
        self._recent.add(path)
        snapshot = self._vm.pending_run_snapshot()
        if snapshot is None:
            self._apply_project_view_settings()
            self._confirm_custom_commands()
            self._offer_stored_results()
            return True
        if self._ask_restore_snapshot(snapshot):
            try:
                self._vm.restore_run_snapshot()
                self._log(f"Restored unsaved changes from {snapshot.name} (not yet saved).")
            except Exception as exc:
                QMessageBox.critical(self, "Restore failed", str(exc))
        else:
            self._vm.discard_run_snapshot()
            self._log(f"Discarded {snapshot.name}.")
        self._apply_project_view_settings()
        self._confirm_custom_commands()
        self._offer_stored_results()
        return True

    def _offer_stored_results(self) -> None:
        """Offer the results a batch stored for this model, so nothing has to run again."""
        stored = stored_results(self._vm.path, self._vm.project)
        if stored is None:
            return
        answer = QMessageBox.question(
            self,
            "Stored results",
            f"Results of {len(stored.entries)} case(s) from a batch run "
            f"({stored.finished_at or 'time unknown'}) are stored for this model, and the "
            "model has not changed since.\n\nLoad them to view without running again?\n\n"
            f"Folder: {stored.out_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.load_stored_results(stored)

    def load_stored_results(self, stored: StoredResults) -> int:
        """Load every case of ``stored`` as if it had just run; show the last one.

        They are already in the results database, so nothing is recorded again.
        Returns how many cases loaded.
        """
        loaded = []
        for entry in stored.entries:
            try:
                results = load_results(entry, stored.out_dir)
            except Exception as exc:
                self._log(
                    f"Warning: stored results of case {entry.get('case_id')} unreadable: {exc}"
                )
                continue
            self._keep_case_results(results)
            loaded.append(results)
        if loaded:
            self._display_results(loaded[-1])
            self._log(f"Loaded {len(loaded)} stored case result(s) from {stored.out_dir}.")
        return len(loaded)

    def _on_run_batch(self) -> None:
        """File → Run Batch…"""
        start_dir = self._vm.path.parent if self._vm.path is not None else None
        dlg = BatchRunDialog(self, start_dir=start_dir)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def _confirm_custom_commands(self) -> None:
        """A file's custom Python blocks run only once the user trusts them."""
        project = self._vm.project
        blocks = [b for b in project.custom_commands if b.enabled] if project is not None else []
        if not blocks:
            return
        names = ", ".join(b.name or str(b.id) for b in blocks)
        answer = QMessageBox.warning(
            self,
            "Custom OpenSees commands",
            f"This project contains {len(blocks)} custom Python block(s) ({names}) that run "
            "on this computer when the model is analysed.\n\nRun them only if you trust "
            "where the file came from. Enable them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            for block in blocks:
                block.enabled = False
            self._log(
                f"Custom command blocks disabled: {names}. "
                "Enable them in Define → Custom OpenSees Commands."
            )

    def _ask_restore_snapshot(self, snapshot: Path) -> bool:
        """Ask whether the newer pre-run snapshot should replace the file's content."""
        answer = QMessageBox.question(
            self,
            "Recover unsaved changes",
            "A snapshot written before the last analysis run is newer than this "
            "project file.\n\nRestore unsaved changes from the last analysis run?\n\n"
            f"Snapshot: {snapshot}\n"
            "Yes loads the snapshot as unsaved changes; No deletes it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        """Close: confirm unsaved work for a user-initiated close only.

        A close the user asked for (the window-manager button, Alt+F4, File →
        Quit) confirms unsaved changes. A programmatic ``close()`` — the test
        session teardown, ``closeAllWindows()`` while shutting down — does
        not: there is nobody to answer the dialog, and a modal prompt there
        would wedge the shutdown.
        """
        user_initiated = event.spontaneous() or self._user_close_requested
        self._user_close_requested = False
        if user_initiated and not self._confirm_discard_changes("Closing the application"):
            event.ignore()
            return
        self._vm.discard_run_snapshot()
        self._save_session_state()
        # Secondary viewports are children of the same session: they go with it.
        for window in list(self._view_windows):
            window.close()
        self._view_windows.clear()
        super().closeEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        """Give the menus back to the main canvas when this window is activated."""
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            main = getattr(self, "_main_canvas", None)
            active = getattr(self, "_active_canvas", None)
            if main is not None and active is not None and active is not main:
                self._active_canvas = main
                controller = getattr(self, "_tool_controller", None)
                if controller is not None:
                    controller.set_canvas(main)
                self._act_close_view.setEnabled(False)
                self._sync_visibility_actions()
                self._refresh_action_enablement()
        super().changeEvent(event)

    def _on_quit(self) -> None:
        """File → Quit — a user gesture, so unsaved changes are confirmed."""
        self._user_close_requested = True
        self.close()

    def _confirm_discard_changes(self, action: str) -> bool:
        """Ask before throwing away unsaved work. True when it is safe to go on.

        ``is_dirty`` used to drive only the ``*`` in the window title, so
        closing, opening and File → New dropped the model without a word.
        Returns False when the user cancels, or chooses Save and the save
        does not go through (dialog cancelled, write failed).
        """
        if self._vm.project is None or not self._vm.is_dirty:
            return True
        answer = QMessageBox.warning(
            self,
            "Unsaved changes",
            f"{action} will discard changes that have not been saved.\n\nSave the project first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._on_save()
        return True

    def _on_save(self) -> bool:
        """Save to the current path (asking for one if needed). True when written."""
        if self._vm.path is None:
            return self._on_save_as()
        try:
            self._store_view_settings_in_project()
            self._warn_case_references()
            self._vm.save()
            self._log(f"Saved: {self._vm.path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        return True

    def _on_project_info(self) -> None:
        """File → Project Information: the cover data of the calculation report."""
        project = self._vm.project
        if project is None:
            return
        dialog = ProjectInfoDialog(project.meta, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._vm.apply_command(SetProjectMetaCommand(self._vm, dialog.meta()))
        self._log("Project information updated.")

    def _on_save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save project as",
            "",
            f"OpenSees Studio model (*{PROJECT_FILE_SUFFIX})",
        )
        if not path:
            return False
        try:
            self._store_view_settings_in_project()
            self._warn_case_references()
            out = self._vm.save(path)
            self._log(f"Saved: {out}")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        self._recent.add(out)
        return True

    def report_results(self) -> list[Any]:
        """The results the report includes: every current case, plus the one on screen."""
        return self.results.for_report(self._vm.project)

    # ── slots: edit ──────────────────────────────────────────────────
    def _warn_case_references(self) -> None:
        project = self._vm.project
        if project is None:
            return
        errors = [
            error for case in project.analyses for error in project.case_reference_errors(case)
        ]
        if errors:
            QMessageBox.warning(self, "Saving with invalid case references", "\n".join(errors))

    # ── slots: select menu ──────────────────────────────────────────
    def _build_select_menu(self, menu: Any) -> None:
        """Select: everything, by property, by load pattern, inverted or the previous one.

        The "By …" submenus list what the model holds when the menu opens, and
        every query *adds* to the current selection (SAP2000 style), so "frames
        of section A" then "frames of section B" selects both.
        """
        menu.addActions([self.action("select.all"), self._act_clear_selection])
        menu.addActions([self.action("select.invert"), self.action("select.previous")])
        menu.addAction(self._act_select_line)
        menu.addSeparator()
        menu.addActions([self.action("select.all_joints"), self.action("select.all_elements")])
        self.select.add_by_menus(menu)
        menu.addSeparator()
        menu.addActions(
            [
                self.action("select.supports"),
                self.action("select.joints_with_mass"),
                self.action("select.weighted"),
            ]
        )
        menu.addSeparator()
        menu.addActions(
            [
                self.action("select.loose_joints"),
                self.action("select.joints_in_bars"),
                self.action("select.shell_edge_joints"),
            ]
        )
        menu.addSeparator()
        menu.addActions(
            [self.action("select.joints_of_elements"), self.action("select.elements_within_joints")]
        )

    def _on_clear_selection(self) -> None:
        """Esc: clear selection AND reset any in-progress tool gesture."""
        self._canvas.selection.clear()
        self._tool_controller.cancel()
        self._act_select_line.setChecked(False)
        self._act_zoom_window.setChecked(False)

    # ── slots: tools ────────────────────────────────────────────────
    @property
    def _offset_dialog(self) -> MoveDialog | ReplicateDialog | None:
        """The open Move/Replicate window (now the transforms controller's)."""
        return self.transforms.offset_dialog

    @property
    def _paste_offset(self) -> tuple[float, float, float]:
        return self.transforms.paste_offset

    # ── slots: define ────────────────────────────────────────────────
    def _select_report_row(self, node_ids: Sequence[int], element_ids: Sequence[int]) -> None:
        """Highlight the nodes/elements of a report row so they can be inspected."""
        self._canvas.selection.clear()
        for node_id in node_ids:
            self._canvas.selection.select_node(node_id, additive=True)
        for element_id in element_ids:
            self._canvas.selection.select_element(element_id, additive=True)
        self._canvas.render()

    def _on_language(self, code: str) -> None:
        """Options → Language: switch the interface now and remember it."""
        from PySide6.QtCore import QSettings

        from opensees_studio.views.i18n import SETTINGS_KEY, InterfaceTranslator

        QSettings().setValue(SETTINGS_KEY, code)
        for other, action in self._language_actions.items():
            action.setChecked(other == code)
        app = QApplication.instance()
        translator = (
            next((c for c in app.children() if isinstance(c, InterfaceTranslator)), None)
            if app is not None
            else None
        )
        if translator is not None:
            translator.set_language(code)
        elif isinstance(app, QApplication):
            InterfaceTranslator(app, code)  # parented to the application, which keeps it
        # Texts the code sets itself (the explorer, the status bar) follow by hand.
        self._refresh_tree(self._vm.project)
        self._ribbon.retranslate()
        self._project_dock.set_project(self._vm.project)
        self._log(f"Interface language: {LANGUAGES[code]}.")

    def _on_frame_wizard(self) -> None:
        """Define → Create Portal Frame: a parametric 2D frame, one undo step.

        This builds a frame into whatever project is open and touches nothing
        else. ``File → New 2D Frame`` (:meth:`_on_new_2d`) asks for the matching
        grid as well, because there the wizard is the whole point of the menu
        entry rather than one of the ways to draw a member.
        """
        self._create_portal_frame(with_grid=False)

    def _create_portal_frame(self, *, with_grid: bool) -> None:
        """Collect the wizard's answers and insert the frame (and, if asked, its grid).

        The geometry comes from ``core.frames``; this only collects it, resolves
        the two section choices (creating the canonical default one *inside* the
        macro when the project has none) and inserts the result.
        """
        project = self._vm.project
        if project is None:
            QMessageBox.information(self, "Portal frame", "Open or create a project first.")
            return
        if (project.ndm, project.ndf) not in SUPPORTED_NDF:
            QMessageBox.information(
                self,
                "Portal frame",
                "A plane frame needs a 2D frame model (ndm = 2, ndf = 3) or a 3D frame "
                f"model (ndm = 3, ndf = 6); this project is ndm = {project.ndm}, "
                f"ndf = {project.ndf}.",
            )
            return

        # The wizard builds ElasticBeamColumns directly; a nonprismatic template
        # is assigned afterwards, when it can subdivide the member and its loads.
        sections = [s for s in project.sections if isinstance(s, ElasticSection)]
        wizard = FrameWizard(
            sections,
            ndm=project.ndm,
            ndf=project.ndf,
            length_unit=labels_for(project.meta.units).length,
            parent=self,
        )
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        column_id, rafter_id = wizard.section_choice()

        try:
            new_sections = []
            if column_id is None or rafter_id is None:
                section = make_default_section(project.next_section_id(), project)
                new_sections.append(section)
                column_id = rafter_id = section.id
            spec = wizard.spec(column_section_id=column_id, rafter_section_id=rafter_id)
            frame = build_portal_frame(
                spec,
                ndm=project.ndm,
                ndf=project.ndf,
                first_node_id=project.next_node_id(),
                first_element_id=project.next_element_id(),
            )
            # The same undo step as the frame: one Ctrl+Z takes both back.
            grid = frame_grid(spec) if with_grid else None
            insert_generated(
                self._vm,
                GeneratedModel(
                    sections=new_sections, nodes=frame.nodes, elements=frame.elements, grid=grid
                ),
                text="Create portal frame",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Cannot create the frame", str(exc))
            return

        # Leave the frame selected: the next thing most users do is copy it.
        self._canvas.selection.clear()
        for node in frame.nodes:
            self._canvas.selection.select_node(node.id, additive=True)
        self._log(f"{frame.summary()} Left selected for Edit → Replicate.")
        if grid is not None:
            lines = (
                len(grid.grid.x_grid_lines)
                + len(grid.grid.y_grid_lines)
                + len(grid.grid.z_grid_lines)
            )
            self._log(f"Grid '{grid.name}' created with {lines} line(s) from the same numbers.")
            if project.ndm == 2:
                # A 2D model has one plane, X-Z: show it face on.
                self.viewport.front()

    def _on_warehouse_wizard(self) -> None:
        """Define → Create Warehouse: a parametric 3D warehouse, one undo step.

        Everything comes from ``core.warehouse`` (the plan) and
        ``commands.warehouse`` (its insertion as one macro, checked before
        anything is pushed); this only asks and reports.
        """
        from opensees_studio.commands.warehouse import insert_warehouse_plan
        from opensees_studio.core.warehouse import GROUPS, WAREHOUSE_NDF, plan_warehouse
        from opensees_studio.views.dialogs.warehouse_wizard import WarehouseWizard

        project = self._vm.project
        if project is None:
            QMessageBox.information(self, "Warehouse", "Open or create a project first.")
            return
        if (project.ndm, project.ndf) != WAREHOUSE_NDF:
            QMessageBox.information(
                self,
                "Warehouse",
                tr(
                    "A warehouse needs a 3D frame model (ndm = 3, ndf = 6); this project "
                    "is ndm = {ndm}, ndf = {ndf}."
                ).format(ndm=project.ndm, ndf=project.ndf),
            )
            return
        sections = [s for s in project.sections if isinstance(s, ElasticSection)]
        wizard = WarehouseWizard(sections, units=project.meta.units, parent=self)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            plan = plan_warehouse(
                project,
                wizard.spec(),
                sections=wizard.section_choice(),
                loads=wizard.loads(),
                group_names={key: tr(name) for key, name in GROUPS.items()},
            )
            insert_warehouse_plan(self._vm, plan)
        except Exception as exc:
            QMessageBox.critical(self, "Cannot create the warehouse", str(exc))
            return
        self._log(plan.warehouse.summary())
        if plan.sections:
            self._log("Sections created: " + ", ".join(s.name for s in plan.sections) + ".")
        if plan.combinations:
            self._log(f"{len(plan.combinations)} load combination(s) generated.")
        for note in plan.notes:
            self._log(note)
        self._canvas.reframe()

    def _on_truss_wizard(self) -> None:
        """Define → Create Truss: a parametric plane truss, one undo step.

        The geometry comes from ``core.trusses``; this collects it, resolves the
        material (creating the default truss steel *inside* the macro when the
        project has no uniaxial material) and inserts the result.
        """
        from opensees_studio.core import TRUSS_NDF, build_truss
        from opensees_studio.views.dialogs.truss_wizard import TrussWizard

        project = self._vm.project
        if project is None:
            QMessageBox.information(self, "Truss", "Open or create a project first.")
            return
        if (project.ndm, project.ndf) not in TRUSS_NDF:
            QMessageBox.information(
                self,
                "Truss",
                "A plane truss needs ndm = 2 (ndf 2 or 3) or ndm = 3 (ndf 3 or 6); "
                f"this project is ndm = {project.ndm}, ndf = {project.ndf}.",
            )
            return
        materials = [m for m in project.materials if is_uniaxial(m)]
        wizard = TrussWizard(
            materials,
            ndm=project.ndm,
            ndf=project.ndf,
            length_unit=labels_for(project.meta.units).length,
            parent=self,
        )
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        material_id = wizard.material_choice()

        try:
            new_materials = []
            if material_id is None:
                material = make_default_truss_material(project.next_material_id())
                new_materials.append(material)
                material_id = material.id
            truss = build_truss(
                wizard.spec(material_id=material_id),
                ndm=project.ndm,
                ndf=project.ndf,
                first_node_id=project.next_node_id(),
                first_element_id=project.next_element_id(),
            )
            insert_generated(
                self._vm,
                GeneratedModel(materials=new_materials, nodes=truss.nodes, elements=truss.elements),
                text="Create truss",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Cannot create the truss", str(exc))
            return

        self._canvas.selection.set_selection(
            {node.id for node in truss.nodes}, {element.id for element in truss.elements}
        )
        self._log(f"{truss.summary()} Left selected.")

    def _sync_grid_actions(self) -> None:
        """Tick View → Show Grids / Labels from the project (checked when any shows)."""
        project = self._vm.project
        systems = project.coord_systems if project is not None else []
        self._act_show_grids.setChecked(any(not cs.grid.hide_all for cs in systems))
        self._act_show_grid_labels.setChecked(any(cs.grid.show_labels for cs in systems))

    # ── View → zoom, hiding and per-viewport settings ───────────────
    def _apply_view_settings(self, **changes: object) -> None:
        """Apply ``changes`` to this viewport's settings and resync the ticks."""
        self._canvas.set_view_settings(self._canvas.view_settings.with_changes(**changes))
        self._sync_visibility_actions()

    def _sync_visibility_actions(self) -> None:
        """Tick every visibility action from the canvas without re-firing it."""
        settings = self._canvas.view_settings
        pairs: tuple[tuple[QAction, bool], ...] = (
            (self._act_vis_grids, settings.show_grids),
            (self._act_vis_grid_labels, settings.show_grid_labels),
            (self._act_vis_nodes, settings.show_nodes),
            (self._act_vis_frames, settings.show_frames),
            (self._act_vis_surfaces, settings.show_surfaces),
            (self._act_vis_supports, settings.show_supports),
            (self._act_vis_footings, settings.show_footings),
            (self._act_vis_constraints, settings.show_constraints),
            (self._act_vis_frame_assignments, settings.show_frame_assignments),
            (self._act_vis_releases, settings.show_releases),
            (self._act_vis_loads, settings.show_loads),
            (self._act_show_local_axes, settings.show_local_axes),
            (self._act_vis_node_labels, settings.show_node_labels),
            (self._act_vis_element_labels, settings.show_element_labels),
            (self._act_vis_extruded, settings.show_extruded),
            # "Show Extruded Sections" is the same field, so it ticks too.
            (self._act_show_extruded, settings.show_extruded),
        )
        for action, checked in pairs:
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)
        color_by = self._color_by_actions[settings.color_by]
        color_by.blockSignals(True)
        color_by.setChecked(True)
        color_by.blockSignals(False)

    def _on_visibility_toggle(self, field: str, checked: bool) -> None:
        """Apply one Visibility-menu toggle to the viewport."""
        self._apply_view_settings(**{field: checked})

    def _on_vis_node_labels(self, checked: bool) -> None:
        """Node labels, keeping the Display Options dialog's state in step."""
        self._show_node_labels = checked
        self._apply_view_settings(show_node_labels=checked)

    def _on_vis_element_labels(self, checked: bool) -> None:
        """Element labels, keeping the Display Options dialog's state in step."""
        self._show_element_labels = checked
        self._apply_view_settings(show_element_labels=checked)

    def _on_color_by(self, mode: str) -> None:
        """View → Color By: paint frames and shells by section, material or group."""
        self._apply_view_settings(color_by=mode)

    def _on_vis_extruded(self, checked: bool) -> None:
        """Show Extruded Sections, from either of its two actions."""
        self._apply_view_settings(show_extruded=checked)

    def _on_view_colors(self) -> None:
        """View → Colors: edit the six viewport colours in one dialog."""
        dialog = ViewColorsDialog(self._canvas.view_settings, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_view_settings(**dialog.colors())

    # ── View → secondary windows ────────────────────────────────────
    def _on_new_view_window(self) -> None:
        """Open another viewport on the same project, in its own window."""
        window = ViewWindow(self._main_canvas.selection, self._active_canvas.view_settings, self)
        window.activated.connect(self._on_view_window_activated)
        window.closed.connect(self._on_view_window_closed)
        # The right-click menu is the main window's, so every viewport gets the
        # same actions (assign, hide, delete) on the shared selection.
        window.canvas.contextMenuRequested.connect(self._on_canvas_context_menu)
        window.canvas.cursorMoved.connect(self._on_cursor_moved)
        window.canvas.lineSelectFinished.connect(lambda: self._act_select_line.setChecked(False))
        window.canvas.zoomWindowFinished.connect(lambda: self._act_zoom_window.setChecked(False))
        window.canvas.set_snap_modes(self._snap_modes)
        self._view_windows.append(window)
        window.show_project(self._vm.project)
        window.show()
        self._on_view_window_activated(window)

    def _on_close_view_window(self) -> None:
        """Close the viewport the menu targets; the main canvas never closes."""
        if self._active_canvas is self._main_canvas:
            return
        for window in list(self._view_windows):
            if window.canvas is self._active_canvas:
                window.close()
                return

    def _on_view_window_activated(self, window: object) -> None:
        """Follow focus: the View menu now acts on that window's canvas."""
        if not isinstance(window, ViewWindow):
            return
        self._active_canvas = window.canvas
        self._tool_controller.set_canvas(window.canvas)
        self._act_close_view.setEnabled(True)
        self._sync_visibility_actions()
        self._refresh_action_enablement()

    def _on_view_window_closed(self, window: object) -> None:
        """Forget a closed window and hand the menus back to the main canvas."""
        if not isinstance(window, ViewWindow):
            return
        if window in self._view_windows:
            self._view_windows.remove(window)
        if self._active_canvas is window.canvas:
            self._active_canvas = self._main_canvas
            self._tool_controller.set_canvas(self._main_canvas)
        self._act_close_view.setEnabled(False)
        self._sync_visibility_actions()

    def _refresh_view_windows(self, project: Project | None) -> None:
        """Re-render every secondary viewport, keeping its camera where it was."""
        for window in list(self._view_windows):
            window.refresh(project)

    # ── View settings that live in the project file ─────────────────
    def _apply_project_view_settings(self) -> None:
        """Adopt the display settings the project carries."""
        project = self._vm.project
        stored = project.view if project is not None else None
        self._main_canvas.set_view_settings(stored if stored is not None else ViewSettings())
        self._sync_visibility_actions()
        # Re-rendering for the new settings may fit the camera to every actor
        # again (including furniture left from the previous file); keep it on
        # the new model.
        if project is not None and project.nodes:
            self._main_canvas.reframe()

    def _store_view_settings_in_project(self) -> None:
        """Write the primary viewport's settings into the model before saving.

        A viewport that was never customised stores ``None``, so the file stays
        byte-identical to one written before this feature existed.
        """
        project = self._vm.project
        if project is None:
            return
        settings = self._main_canvas.view_settings
        project.view = None if settings == ViewSettings() else settings

    # ── display state that outlives the process ─────────────────────
    #: Bumped when the set of panels or toolbars changes, so a layout saved by an
    #: older build is ignored instead of restored half-way.
    LAYOUT_VERSION = 3  # 2: the Restraints toolbar; 3: the Selection toolbar

    def _restore_session_state(self) -> None:
        """Restore last session's geometry, panel layout and default viewport."""
        # The layout as built, for View → Reset Window Layout.
        self._default_layout = self.saveState(self.LAYOUT_VERSION)
        settings = QSettings()
        geometry = settings.value("window/geometry")
        if geometry is not None:
            with contextlib.suppress(Exception):  # a corrupt stored value
                self.restoreGeometry(geometry)
        state = settings.value("window/state")
        if state is not None:
            with contextlib.suppress(Exception):
                self.restoreState(state, self.LAYOUT_VERSION)
        raw = settings.value("view/default")
        if isinstance(raw, str) and raw:
            with contextlib.suppress(Exception):  # a settings format change
                self._main_canvas.set_view_settings(ViewSettings.model_validate_json(raw))

    def _save_session_state(self) -> None:
        """Persist the geometry, the panel layout and the default viewport."""
        # A result dock (force diagram, steel ratios, …) belongs to this session
        # only; drop it first so the saved layout holds the permanent panels.
        self.display.tear_down()
        settings = QSettings()
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState(self.LAYOUT_VERSION))
        settings.setValue("view/default", self._main_canvas.view_settings.model_dump_json())

    def _on_reset_layout(self) -> None:
        """View → Reset Window Layout: every panel and toolbar back where it started."""
        self.restoreState(self._default_layout, self.LAYOUT_VERSION)
        for dock in self._layout_docks:
            dock.setFloating(False)
            dock.show()
        self._layout_docks[2].raise_()  # the console in front of its tab group
        self.statusBar().showMessage(tr("Window layout reset."), 4000)

    def _on_canvas_context_menu(self, pos: QPoint) -> None:
        """Right-click on the model view: the element diagrams, or the usual menu.

        While a force diagram or a deformed shape is visible, a right-click on
        a frame member opens that member's diagram window instead of the
        context menu. Anywhere else - no post-processing view, empty space or
        a non-frame element - the menu is unchanged.
        """
        canvas = self._context_canvas()
        if self.display.open_member_at(pos, canvas):
            return
        menu = self._context_menu_at(pos, canvas)
        menu.exec(pos)
        menu.deleteLater()

    def _context_menu_at(self, pos: QPoint, canvas: ModelCanvas) -> QMenu:
        """The right-click menu, led by Object Information when an object is meant."""
        menu = self._canvas_context_menu()
        target = self._object_at(pos, canvas)
        if target is not None:
            kind, object_id = target
            label = tr("Joint") if kind == "node" else tr("Element")
            info = QAction(f"{tr('Object Information')}: {label} {object_id}…", menu)
            info.triggered.connect(lambda: self._show_object_info(kind, object_id))
            existing = menu.actions()
            if existing:
                menu.insertAction(existing[0], info)
                menu.insertSeparator(existing[0])
            else:
                menu.addAction(info)
        return menu

    def _object_at(self, pos: QPoint, canvas: ModelCanvas) -> tuple[str, int] | None:
        """The joint or member under a right-click, else the one object selected."""
        local = canvas.mapFromGlobal(pos)
        node_id = canvas.node_at(local.x(), local.y())
        if node_id is not None:
            return "node", node_id
        element_id = canvas.frame_element_at(local.x(), local.y())
        if element_id is not None:
            return "element", element_id
        selection = self._canvas.selection
        if len(selection.nodes) == 1 and not selection.elements:
            return "node", next(iter(selection.nodes))
        if len(selection.elements) == 1 and not selection.nodes:
            return "element", next(iter(selection.elements))
        return None

    def _show_object_info(self, kind: str, object_id: int) -> ObjectInfoDialog | None:
        """Open the Location / Assignments / Loads window of one joint or element."""
        project = self._vm.project
        if project is None:
            return None
        info = node_info(project, object_id) if kind == "node" else element_info(project, object_id)
        if info is None:
            return None
        dialog = ObjectInfoDialog(info, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()
        return dialog

    def _context_canvas(self) -> ModelCanvas:
        """The viewport whose right-click emitted the signal (the active one if unknown)."""
        sender = self.sender()
        return sender if isinstance(sender, ModelCanvas) else self._canvas

    def _canvas_context_menu(self) -> QMenu:
        """What the right-click shows: the selection's options, or grids and view."""
        selection = self._canvas.selection
        if not selection.is_empty:
            return self._selection_context_menu(selection.nodes, selection.elements)
        menu = QMenu(self)
        project = self._vm.project
        if project is not None:
            self._sync_grid_actions()
            menu.addAction(self._act_show_grids)
            if len(project.coord_systems) > 1:
                per_system = menu.addMenu("Grids by system")
                for cs in project.coord_systems:
                    action = per_system.addAction(cs.name)
                    action.setCheckable(True)
                    action.setChecked(not cs.grid.hide_all)
                    action.triggered.connect(
                        lambda checked, name=cs.name: self.grids.set_shown(checked, name)
                    )
            menu.addAction(self._act_show_grid_labels)
            menu.addSeparator()
        menu.addAction(self.action("define.grid"))
        menu.addAction(self.action("define.grid_wizard"))
        menu.addSeparator()
        menu.addAction(self.action("view.grid_line_view"))
        menu.addAction(self.action("view.show_all_objects"))
        menu.addSeparator()
        menu.addActions(
            [
                self.action("view.iso"),
                self.action("view.top"),
                self.action("view.front"),
                self.action("view.right"),
            ]
        )
        menu.addAction(self._act_zoom_extents)
        return menu

    def _selection_context_menu(self, nodes: frozenset[int], elements: frozenset[int]) -> QMenu:
        """Right-click with something selected: what can be assigned or edited on it."""
        from opensees_studio.core.geometry import (
            FRAME_ELEMENT_CLASSES,
            QuadElement,
            ShellMITC4Element,
        )

        self._refresh_action_enablement()
        menu = QMenu(self)
        project = self._vm.project
        kinds = [
            type(e) for e in (project.elements if project is not None else []) if e.id in elements
        ]
        frames = sum(1 for k in kinds if issubclass(k, FRAME_ELEMENT_CLASSES))
        areas = sum(1 for k in kinds if issubclass(k, QuadElement | ShellMITC4Element))
        parts = [f"{len(nodes)} joint(s)"] if nodes else []
        if elements:
            parts.append(f"{len(elements)} element(s)")
        header = menu.addAction(", ".join(parts) + " selected")
        header.setEnabled(False)
        menu.addSeparator()
        groups = [
            ("Joint", self._joint_actions, bool(nodes)),
            ("Frame", self._frame_actions, frames > 0),
            ("Area", self._area_actions, areas > 0),
        ]
        wanted = [(title, actions) for title, actions, on in groups if on]
        for title, actions in wanted:
            # One kind selected: its options straight in the menu; several: a submenu each.
            _add_actions(menu if len(wanted) == 1 else menu.addMenu(title), actions)
        if wanted:
            menu.addSeparator()
        menu.addAction(self.action("assign.group"))
        menu.addSeparator()
        menu.addActions(
            [self.action("edit.move"), self.action("edit.replicate"), self.action("edit.mirror")]
        )
        menu.addSeparator()
        if elements:
            hide = menu.addAction("Hide Selected Elements")
            hide.triggered.connect(self.viewport.hide_selected)
        menu.addAction(self.action("view.isolate_selected"))
        if self.action("view.show_all_objects").isEnabled():
            menu.addAction(self.action("view.show_all_objects"))
        menu.addSeparator()
        menu.addAction(self.action("edit.delete"))
        menu.addAction(self._act_clear_selection)
        return menu

    # ── View → Grid Line View ───────────────────────────────────────
    def _on_add_node(self) -> None:
        if self._vm.project is None:
            self._on_new()
        proj = self._vm.project
        assert proj is not None
        dlg = AddNodeDialog(
            next_node_id=proj.next_node_id(),
            grid=proj.grid_system,
            ndm=proj.ndm,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            node = dlg.node()
            self._vm.apply_command(
                AddNodesCommand(
                    self._vm,
                    [node],
                    text=f"Add node {node.id}",
                )
            )
            self._log(
                f"Added node {node.id} at "
                f"({node.coords[0]:g}, {node.coords[1]:g}, {node.coords[2]:g})."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add Node failed", str(exc))

    # ── define and assign: groups, section cuts, custom commands ────
    def _on_custom_commands(self) -> None:
        """Define → Custom OpenSees Commands: Python blocks run while the model is built."""
        from opensees_studio.commands import SetCustomCommandsCommand
        from opensees_studio.views.dialogs.custom_commands import CustomCommandsDialog

        project = self._vm.project
        if project is None:
            return
        dlg = CustomCommandsDialog(project, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetCustomCommandsCommand(self._vm, dlg.blocks()))
            enabled = sum(1 for b in project.custom_commands if b.enabled)
            self._log(f"Custom command blocks: {len(project.custom_commands)} ({enabled} enabled).")
        except Exception as exc:
            QMessageBox.critical(self, "Custom OpenSees Commands failed", str(exc))

    # ── property editor: live-edit callbacks ─────────────────────────
    # ── property editor: multi-selection edits (one undo step each) ──
    # ── slots: define ────────────────────────────────────────────────
    # ── slots: assign property ──────────────────────────────────────
    # ── area loads and imposed displacements ─────────────────────────
    # ── slots: analyze ──────────────────────────────────────────────
    def _on_check_stability(self) -> None:
        """Analyze → Check Model Stability: look for mechanisms before solving anything."""
        project = self._vm.project
        if project is None:
            return
        if not project.nodes:
            QMessageBox.information(self, "Check Model Stability", "The model has no joints yet.")
            return
        self._stability.check(project, self._vm.path)

    def _on_stability_progress(self, phase: str, message: str) -> None:
        """Show the coarse stability phase in the status bar and console."""
        self._log(f"Stability [{phase}]: {message}")

    def _on_stability_report(self, report: StabilityReport) -> None:
        summary = report.summary()
        self._log(summary)
        if report.nodes:
            # Show where the mechanisms are: their joints become the selection.
            self._canvas.selection.set_selection(set(report.nodes), set())
            self._refresh_action_enablement()
        box = QMessageBox(self)
        box.setWindowTitle("Check Model Stability")
        box.setIcon(QMessageBox.Icon.Information if report.stable else QMessageBox.Icon.Warning)
        if report.completion != "complete":
            headline = "The stability check is incomplete."
        elif report.classification == "no_free_equations":
            headline = "The model is fully restrained."
        elif report.stable:
            headline = "The model is statically stable."
        else:
            headline = "The model is not statically stable."
        box.setText(headline)
        box.setInformativeText(
            summary + ("\n\nThe joints that move are selected." if report.nodes else "")
        )
        box.open()
        self._stability_box = box

    def _on_stability_failed(self, message: str) -> None:
        self._log(message)
        box = QMessageBox(self)
        box.setWindowTitle("Check Model Stability")
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText("The stability check could not finish.")
        box.setInformativeText(message)
        box.open()
        self._stability_box = box

    def _on_case_manager(self) -> None:
        if self._vm.project is None:
            self._on_new()
        AnalysisCaseManagerDialog(self._vm, self).exec()

    def _on_run_all_cases(self) -> None:
        """Analyze → Run All Cases: every case, in one child process."""
        project = self._vm.project
        if project is None or self._runner.is_running:
            return
        if not project.analyses:
            self._log("No analysis cases. Define one in Analyze → Cases…")
            return
        self._log(f"Running all {len(project.analyses)} case(s).")
        self._start_batch(list(project.analyses))

    def _on_run_selected_cases(self) -> None:
        """Analyze → Run Selected Cases: tick the cases, then run them together."""
        project = self._vm.project
        if project is None or self._runner.is_running:
            return
        if not project.analyses:
            self._log("No analysis cases. Define one in Analyze → Cases…")
            return
        dialog = RunCasesDialog(project, self)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            chosen = set(dialog.selected_case_ids())
        finally:
            dialog.deleteLater()
        cases = [case for case in project.analyses if case.id in chosen]
        if not cases:
            self._log("No case selected.")
            return
        self._log(f"Running {len(cases)} selected case(s).")
        self._start_batch(cases)

    def _start_batch(self, cases: list[Any]) -> None:
        """Hand a set of cases to the runner in one child process."""
        project = self._vm.project
        if project is None:
            return
        self._auto_mesh_before_run()
        try:
            self._runner.run_cases(project, cases, project_path=self._vm.path)
        except Exception as exc:
            self._log(f"Could not start: {exc}")

    def _on_check_model(self) -> None:
        """Analyze → Check Model: loose nodes, unconnected elements, mechanisms."""
        project = self._vm.project
        if project is None:
            QMessageBox.information(self, "Check Model", "Open or create a project first.")
            return
        report = check_model(project)
        dlg = ModelCheckDialog(
            project, report=report, on_select=self._select_report_row, parent=self
        )
        try:
            dlg.exec()
            mechanism = dlg.mechanism_to_show()
        finally:
            dlg.deleteLater()
        self._log(report.summary())
        if mechanism is not None:
            self.display.mechanism(mechanism)

    def _auto_mesh_before_run(self) -> None:
        """Divide the frames that another frame ends on or crosses, in one undo step.

        So no member lying on another is left unconnected. Members with their own
        Auto Mesh off, and every member while Analyze → Auto-mesh Frames Before
        Run is off, are left as drawn.
        """
        project = self._vm.project
        if project is None:
            return
        plan = pre_run_auto_mesh(project)
        if plan.is_empty:
            return
        try:
            self._vm.apply_command(MeshCommand(self._vm, plan, text="Auto-mesh frames"))
        except Exception as exc:
            self._log(f"Auto-mesh before run failed: {exc}")
            return
        self._log(f"Auto-mesh before run: {plan.summary()}")

    def _on_toggle_auto_mesh_frames(self, checked: bool) -> None:
        """Analyze → Auto-mesh Frames Before Run (saved with the project)."""
        from opensees_studio.commands import SetAutoMeshFramesCommand

        project = self._vm.project
        if project is None or project.auto_mesh_frames == checked:
            return
        self._vm.apply_command(SetAutoMeshFramesCommand(self._vm, checked))

    def _review_model_before_run(self) -> bool:
        """Check the model on the way into Run; ``False`` means the run was called off.

        Errors stop at a dialog that offers *Run anyway* (the check is a linear,
        small-displacement test, so the person may know better). Warnings are
        written to the console and do not interrupt: a modeller who has seen
        "two separate parts" once does not want to click through it on every run.
        """
        project = self._vm.project
        if project is None:
            return True
        report = check_model(project)
        if report.has_errors:
            dlg = ModelCheckDialog(
                project,
                report=report,
                pre_run=True,
                on_select=self._select_report_row,
                parent=self,
            )
            try:
                proceed = dlg.exec() == QDialog.DialogCode.Accepted
                mechanism = dlg.mechanism_to_show()
            finally:
                dlg.deleteLater()
            self._log(report.summary() + (" Running anyway." if proceed else " Run cancelled."))
            if mechanism is not None:
                self.display.mechanism(mechanism)
            return proceed
        for finding in report.warnings:
            self._log(finding.summary())
        if not report.is_complete:
            # A partial check is not a pass: say what was left out.
            for finding in report.infos:
                self._log(finding.summary())
            self._log(report.summary())
        return True

    def _on_run_analysis(self) -> None:
        if self._vm.project is None:
            QMessageBox.information(self, "Run Analysis", "Open or create a project first.")
            return
        if not self._vm.project.analyses:
            QMessageBox.information(
                self,
                "Run Analysis",
                "No analysis cases defined. Open Analyze → Cases…",
            )
            return
        open_dialog = self._run_dialog
        if open_dialog is not None and open_dialog.isVisible():
            # One Run dialog at a time: F5 again brings it to the front.
            open_dialog.raise_()
            open_dialog.activateWindow()
            return
        self._auto_mesh_before_run()
        if not self._review_model_before_run():
            return
        dlg = RunAnalysisDialog(self._vm, self._runner, self, case_results=self.results.cases)
        combination_finished = getattr(dlg, "combinationFinished", None)
        if combination_finished is not None:
            combination_finished.connect(self._on_analysis_finished)
        self._run_dialog = dlg
        # Modeless: the model, the viewport and the results stay usable while
        # the case runs and after, next to the log.
        dlg.finished.connect(lambda _code, d=dlg: self._on_run_dialog_closed(d))
        dlg.show()

    def _on_run_dialog_closed(self, dlg: QWidget) -> None:
        if self._run_dialog is dlg:
            self._run_dialog = None
        self._keep_failure_report_alive(dlg)
        # The dialog connects seven signals of the long-lived runner and is
        # parented to this window, so without this it stays alive after it
        # closes and every later run keeps appending to its log widget.
        dlg.deleteLater()

    def _keep_failure_report_alive(self, dlg: QWidget) -> None:
        """Reparent an unread failure report so it outlives the Run dialog.

        The report is created with ``WA_DeleteOnClose``, so once the user has
        closed it Qt has destroyed the C++ object while this window still holds
        the Python wrapper. ``box.parent()`` then raises ``RuntimeError``, and
        an exception raised here — inside the ``finally`` of a Qt slot — used to
        take the whole application down with it. Hence the validity check, and
        the reference being dropped when the box is gone.
        """
        box = self._analysis_error_box
        if box is None:
            return
        if not shiboken6.isValid(box):
            self._analysis_error_box = None
            return
        if box.parent() is dlg:
            box.setParent(self, box.windowFlags())
            box.show()

    def _failure_parent(self) -> QWidget:
        """The dialog that started the run while it is open, else the main window."""
        dlg = self._run_dialog
        if dlg is not None and dlg.isVisible():
            return dlg
        return self

    def _on_analysis_finished(self, results) -> None:  # type: ignore[no-untyped-def]
        self._display_results(results)
        self._log(f"Analysis complete: {self.results.caption_for(self._vm.project, results)}.")
        if isinstance(results, TransientResults) and results.early_stop:
            self._log(f"Warning: transient run did not converge ({results.steps_summary()}).")
        if isinstance(results, ResponseSpectrumResults | CombinationResults):
            for warning in results.warnings:
                self._log(f"Warning: {warning}")
        self.display.set_caption(self.results.caption_for(self._vm.project, results))
        self._refresh_action_enablement()

    def _on_case_finished(self, results: object) -> None:
        """Keep each case result of a run for the load combinations."""
        self._keep_case_results(results)
        self._record_case_results(results)

    def _keep_case_results(self, results: object) -> None:
        self.results.keep(self._vm.project, results)
        self.model_lock.lock_for_results()

    # ── what the viewport is showing ────────────────────────────────
    def _on_clear_results(self) -> None:
        """Analyze → Delete All Results: forget every stored result."""
        db_path = database_path(self._vm.path)
        answer = QMessageBox.question(
            self,
            "Delete All Results",
            "Delete every stored result?\n\n"
            "  • the results of this session\n"
            f"  • {db_path}\n\n"
            "The model, its analysis cases and any other project's database are "
            "not touched.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._drop_session_results()
        self.model_lock.set_locked(False)
        removed = delete_all_results(db_path)
        self._log(
            "All results deleted."
            if removed
            else "All results deleted (the database was already empty)."
        )
        self._refresh_action_enablement()

    def _drop_session_results(self) -> None:
        """Forget the results held in memory and return to the model view."""
        self.results.clear()
        self._refresh_reactions()
        self._refresh_case_combo()
        self.display.back_to_model()
        self._results_panel.show_results(None, self._vm.project)

    def _record_case_results(self, results: object) -> None:
        """Append this case's results to the project's queryable database.

        A failure here must never fail the analysis: the run already happened,
        so the database is reported as a warning and the results stay in memory.
        """
        try:
            run_id = record_results(results, project_path=self._vm.path, project=self._vm.project)
        except Exception as exc:
            self._log(f"Warning: the results database was not written: {exc}")
            return
        if run_id is not None:
            self._log(f"Results recorded in {database_path(self._vm.path)} (run {run_id}).")

    # ── slots: load combinations ────────────────────────────────────
    def _on_load_combinations(self) -> None:
        """Define → Load Combinations…"""
        if self._vm.project is None:
            self._on_new()
        dlg = LoadCombinationsDialog(self._vm, self)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def show_results_of(self, key: str) -> bool:
        """Make ``case:<id>`` or ``combination:<id>`` the results Display shows.

        A combination is combined from the current case results; when some of its
        cases have none, the message says to run it from Analyze → Run.
        """
        results = self._results_for_key(key)
        if results is None:
            return False
        self.display.back_to_model()
        self._on_analysis_finished(results)
        return True

    def _results_for_key(self, key: str) -> object | None:
        """Resolve a ``case:<id>`` / ``combination:<id>`` key, or explain why not."""
        project = self._vm.project
        if project is None:
            return None
        kind, _, raw_id = key.partition(":")
        try:
            ref_id = int(raw_id)
        except ValueError:
            return None
        if kind == "case":
            results = self.results.cases.current(project).get(ref_id)
            if results is None:
                self._log(f"Case {ref_id} has no current results: run it first.")
                return None
            return cast(object, results)
        try:
            return cast(object, self.results.cases.combine(project, ref_id))
        except (MissingCaseResultsError, ValueError, KeyError) as exc:
            QMessageBox.information(
                self,
                "Show Results Of",
                f"{exc}\n\nAnalyze → Run, then pick the combination: it runs only the "
                "cases without current results.",
            )
            return None

    def _on_select_results(self) -> None:
        """Display → Show Results Of…: switch between stored case and combination results."""
        choices = self.results.choices(self._vm.project)
        if not choices:
            QMessageBox.information(
                self,
                "Show Results Of",
                "No results yet: run a case (Analyze → Run) or define a load combination.",
            )
            return
        label, ok = QInputDialog.getItem(
            self, "Show Results Of", "Results:", [c[0] for c in choices], 0, False
        )
        if ok:
            self.show_results_of(dict(choices)[label])

    def _on_analysis_failed(self, report: str) -> None:
        """Show the failure report (exit code, last error, stderr tail) without blocking."""
        self._console.appendPlainText(report)
        code = self._runner.last_exit_code
        headline = "Analysis failed."
        if code is not None:
            headline = f"Analysis process exited with code {code}."
        # A child of the modal Run dialog, so it is not blocked and opens in front of it.
        box = QMessageBox(self._failure_parent())
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Analysis failed")
        box.setText(headline)
        box.setInformativeText(
            "The application and your model are unaffected. "
            "The pre-run snapshot is kept for recovery. Details below and in the Console dock."
        )
        box.setDetailedText(report)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.setModal(False)
        box.finished.connect(self._forget_failure_report)
        self._analysis_error_box = box
        box.show()
        box.raise_()
        box.activateWindow()
        self._log(headline)

    def report_unexpected_error(self, traceback_text: str) -> None:
        """Show an unhandled exception instead of letting the process die.

        Called by :mod:`opensees_studio.views.error_reporting`, which is what
        ``sys.excepthook`` points at while the GUI is up. The model and the
        analysis child are untouched by a Python error in a slot, so the message
        says so and points at the Console dock, where the traceback is kept.
        """
        self._console.appendPlainText(traceback_text)
        self.statusBar().showMessage("Unexpected error — see the Console dock.", 15000)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unexpected error")
        box.setText(
            "Something went wrong in the interface. Your model and any running analysis "
            "are unaffected — save your work, then report this."
        )
        box.setDetailedText(traceback_text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.setModal(False)
        box.show()
        box.raise_()
        box.activateWindow()

    def _forget_failure_report(self, _result: int = 0) -> None:
        """The report is closed (and, with ``WA_DeleteOnClose``, about to be deleted)."""
        self._analysis_error_box = None

    def _on_display_options(self) -> None:
        dlg = DisplayOptionsDialog(
            show_node_labels=self._show_node_labels,
            show_element_labels=self._show_element_labels,
            view_settings=self._canvas.view_settings,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._show_node_labels, self._show_element_labels = dlg.values()
        settings = dlg.view_settings()
        self._canvas.set_view_settings(settings)
        self._sync_visibility_actions()
        self._log(
            f"Display options updated: node labels={'on' if self._show_node_labels else 'off'}, "
            f"element labels={'on' if self._show_element_labels else 'off'}, "
            f"node size={settings.node_size_percent:g}% of the view height."
        )

    def _on_show_load_assigns(self) -> None:
        """Display → Show Load Assigns: the pattern, kinds and values the canvas draws."""
        project = self._vm.project
        if project is None:
            return
        dlg = LoadDisplayDialog(project.load_patterns, self._canvas.view_settings, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        changes = dlg.changes()
        self._apply_view_settings(**changes)
        pattern_id = changes["load_pattern_id"]
        pattern = next((p for p in project.load_patterns if p.id == pattern_id), None)
        self._log(
            "Loads shown: "
            + ("every load pattern" if pattern is None else f"load pattern '{pattern.name}'")
            + "."
        )

    # ── slots: display (post-processing) ────────────────────────────
    # Animator emits an initial frame in its constructor; nothing to do.

    def _refresh_reactions(self) -> None:
        """Keep the table and the overlay on the same case, and enable the actions."""
        rows = self.results.reaction_rows(self._vm.project)
        self._reactions_panel.set_rows(rows)
        self._canvas.set_reactions(rows, show=self._act_show_reactions.isChecked())
        enabled = bool(rows)
        self._act_show_reactions.setEnabled(enabled)
        self._act_reactions_table.setEnabled(enabled)
        self._act_reactions_dialog.setEnabled(enabled)
        if not enabled and self._act_show_reactions.isChecked():
            self._act_show_reactions.setChecked(False)

    def _on_show_reactions(self, checked: bool) -> None:
        self._canvas.set_reactions(self.results.reaction_rows(self._vm.project), show=checked)

    def _on_reactions_dialog(self) -> None:
        dialog = ReactionsDialog(self.results.reaction_rows(self._vm.project), self)
        dialog.exec()

    def _on_reactions_table(self) -> None:
        self._reactions_dock.show()
        self._reactions_dock.raise_()

    def _refresh_case_combo(self) -> None:
        """List the cases that still hold results for this model, newest order."""
        project = self._vm.project
        entries = self.results.cases.current(project) if project is not None else {}
        current = getattr(self.results.latest, "case_id", None)
        names = case_names(self._vm.project)
        self._case_combo.blockSignals(True)
        self._case_combo.clear()
        for case_id, results in sorted(entries.items()):
            kind = type(results).__name__.removesuffix("Results")
            name = names.get(case_id) or getattr(results, "case_name", None) or f"Case {case_id}"
            self._case_combo.addItem(f"{name} · {kind}", case_id)
        if current is not None:
            index = self._case_combo.findData(current)
            if index >= 0:
                self._case_combo.setCurrentIndex(index)
        self._case_combo.blockSignals(False)
        self._case_combo.setEnabled(bool(entries))
        self._refresh_step_buttons()

    def _on_case_changed(self, index: int) -> None:
        """Show the chosen case; the layers read it from `results.latest`."""
        case_id = self._case_combo.itemData(index)
        project = self._vm.project
        if case_id is None or project is None:
            return
        results = self.results.cases.current(project).get(case_id)
        if results is not None and results is not self.results.latest:
            self._display_results(results)

    def _display_results(self, results: object) -> None:
        """Point the whole window at one results case."""
        self.results.latest = results
        self.model_lock.lock_for_results()
        self._results_panel.show_results(results, self._vm.project)
        self._refresh_reactions()
        self._refresh_case_combo()
        self.display.set_caption(self.results.caption_for(self._vm.project, results))
        self._refresh_action_enablement()
        self._refresh_step_buttons()

    def _refresh_step_buttons(self) -> None:
        """Enable the step arrows only when the shown case has more than one."""
        steps = self.results.steps()
        # Only a layer that knows how to redraw itself at another step registers
        # an applier; until one does, the arrows must not pretend to work.
        steppable = steps > 1 and getattr(self, "_step_apply", None) is not None
        self._step_index = min(getattr(self, "_step_index", 0), max(steps - 1, 0))
        self._step_back.setEnabled(steppable)
        self._step_forward.setEnabled(steppable)
        if steps > 1:
            self._step_label.setText(f"Step {self._step_index + 1}/{steps}")
        else:
            self._step_label.setText("")

    def _shift_step(self, delta: int) -> None:
        steps = self.results.steps()
        if steps <= 1:
            return
        target = min(max(self._step_index + delta, 0), steps - 1)
        if target == self._step_index:
            return
        self._step_index = target
        self._refresh_step_buttons()
        self._apply_step()

    def _apply_step(self) -> None:
        """Re-draw the step-based layer at the current step, if one is showing."""
        apply = getattr(self, "_step_apply", None)
        if apply is not None:
            apply(self._step_index)

    # ── SAP2000-style view switching + working level ───────────────
    # ── autosave ────────────────────────────────────────────────────
    @staticmethod
    def _stored_autosave_minutes() -> int:
        value = QSettings().value(AUTOSAVE_KEY, AUTOSAVE_DEFAULT)
        try:
            minutes = int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return AUTOSAVE_DEFAULT
        return minutes if minutes in AUTOSAVE_CHOICES else AUTOSAVE_DEFAULT

    @staticmethod
    def _stored_shortcut_profile() -> str:
        value = str(QSettings().value(shortcut_profiles.SETTINGS_KEY, shortcut_profiles.DEFAULT))
        return value if value in shortcut_profiles.PROFILES else shortcut_profiles.DEFAULT

    def _set_shortcut_profile(self, profile: str, *, remember: bool = True) -> None:
        """Options → Keyboard Shortcuts: the default keys, or SAP2000's F5/F6/F7/Ctrl+T."""
        self._shortcut_profile_actions[profile].setChecked(True)
        if remember:
            QSettings().setValue(shortcut_profiles.SETTINGS_KEY, profile)
        keys = shortcut_profiles.profile_shortcuts(self._default_shortcuts, profile)
        for name, wanted in keys.items():
            action = getattr(self, name)
            if _portable_keys(action) != wanted:
                action.setShortcuts([QKeySequence(key) for key in wanted])

    def _set_autosave(self, minutes: int, *, remember: bool = True) -> None:
        """Options → Autosave Recovery Copy: how often, or off."""
        self._autosave_actions[minutes].setChecked(True)
        if remember:
            QSettings().setValue(AUTOSAVE_KEY, minutes)
        if minutes:
            self._autosave_timer.start(minutes * 60_000)
        else:
            self._autosave_timer.stop()

    def _autosave(self) -> None:
        """Write the recovery copy of unsaved changes (the project file is not touched).

        It is the same copy a run writes before it starts: opening the project
        after a crash offers it, and a save removes it.
        """
        if self._vm.project is None or not self._vm.is_dirty or self._runner.is_running:
            return
        try:
            path = self._vm.write_run_snapshot()
        except OSError as exc:
            self._log(f"Autosave failed: {exc}")
            return
        self.statusBar().showMessage(f"Recovery copy saved ({path.name}).", 3000)

    def _on_recover_untitled(self) -> None:
        """Start page → Recover: the autosaved never-saved project, as unsaved changes."""
        snapshot = run_snapshot_path(None)
        try:
            project = load_project(snapshot)
        except Exception as exc:
            QMessageBox.critical(self, "Recover failed", str(exc))
            return
        self._vm.adopt(project)
        self._log(f"Recovered the unsaved project from {snapshot} (not yet saved).")

    def _on_project_changed(self, project: Project | None) -> None:
        if project is None:
            self._start_page.refresh()
            untitled = run_snapshot_path(None)
            self._start_page.set_recovery(untitled if untitled.is_file() else None)
        self._central.setCurrentWidget(
            self._main_canvas if project is not None else self._start_page
        )
        self._sync_grid_actions()
        # Another project: its grid lines are not the ones being viewed.
        self.viewport.forget_grid_line()
        self._main_canvas.set_view_filter(None)
        # Another project has its own ids; do not carry this viewport's hidden
        # set into it.
        self._main_canvas.set_hidden(nodes=set(), elements=set())
        self.action("view.show_all_objects").setEnabled(False)
        # Results belong to the previous project and never feed a combination of
        # this one: drop them, the shown case, its charts/tables and every
        # overlay (deformed shape, diagrams, contours, ratios). The new
        # project's stored results are offered afterwards.
        self.results.clear()
        self.model_lock.set_locked(False)
        self.display.back_to_model()
        self._results_panel.show_results(None, project)
        self._refresh_reactions()
        self._main_canvas.show_project(project)
        self._refresh_view_windows(project)
        if project is not None:
            if project.ndm == 2:
                # A 2D model lives in the X-Z plane (core.plane): face on,
                # drawing at y = 0.
                self.viewport.front()
            else:
                # `reset_camera()` only re-fits the bounds: it preserves the
                # previous direction. A 2D file left the camera face-on, and
                # the next 3D model would then open as a long, flat elevation.
                self.viewport.iso()
            if project.nodes:
                # `view_isometric`/`view_xz` change the direction but keep the
                # previous distance; fit the new model after choosing the view.
                self._canvas.reframe()
        self._props.set_project(project)
        self._refresh_tree(project)
        self._refresh_status()
        self._sync_units_combo()
        self._refresh_action_enablement()

    def _on_model_mutated(self) -> None:
        # Same project, contents changed: re-render but DON'T reset camera.
        # We still clear and re-add actors, which loses selection — but the
        # selection state persists, so highlights re-apply.
        if self.viewport.grid_view is not None:
            # The line may have moved or gone: re-resolve it (this redraws).
            self.viewport.apply_grid_line_view()
        elif self._vm.project is not None:
            self._canvas._renderer.render(self._vm.project)
            self._canvas.render()
        self._sync_grid_actions()
        self._refresh_tree(self._vm.project)
        self.drawing.model_changed()
        # Update the property editor with the (possibly new) entity values
        # at the current selection.
        self._props.update_for_selection(
            self._canvas.selection.nodes, self._canvas.selection.elements
        )
        self._refresh_action_enablement()
        # A case renamed elsewhere (or here) must read the same in the results
        # picker and, when results are on screen, in the viewport caption: the
        # numbers did not move, only the label.
        self._refresh_case_combo()
        if (
            self.results.latest is not None
            and self._canvas._renderer.mode is not RendererMode.MODEL
        ):
            self.display.set_caption(
                self.results.caption_for(self._vm.project, self.results.latest)
            )

    def _on_dirty_changed(self, _dirty: bool) -> None:
        self._refresh_status()

    def _on_selection_changed(self, nodes: frozenset[int], elements: frozenset[int]) -> None:
        self._props.update_for_selection(nodes, elements)
        self._refresh_action_enablement()

    def _on_performance(self) -> None:
        """Help → Performance monitor: opt-in timings, memory and cProfile."""
        dialog = getattr(self, "_performance_dialog", None)
        if dialog is None:
            dialog = PerformanceDialog(self._vm, self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.destroyed.connect(lambda _=None: setattr(self, "_performance_dialog", None))
            self._performance_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About OpenSees Studio",
            f"<h3>OpenSees Studio {__version__}</h3>"
            "<p>A modern desktop GUI for OpenSeesPy.</p>"
            "<p>GNU Affero General Public License v3.0 — see LICENSE.</p>",
        )

    def _log_solver_status(self) -> None:
        if self._solver.available:
            self._log(f"Solver: {self._solver.summary()}.")
        else:
            self._log(
                f"No solver: {self._solver.message} Modeling, export and reports work; "
                "running an analysis needs one (Options → Solver)."
            )

    def _on_solver_settings(self) -> None:
        """Options → Solver: where OpenSeesPy is installed."""
        dialog = SolverSettingsDialog(engines.load_settings(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        try:
            engines.save_settings(settings)
        except OSError as exc:
            QMessageBox.critical(self, "Solver", f"Could not save the setting: {exc}")
            return
        engines.activate(settings.package_dir)
        self._solver = engines.current_status(settings)
        self._opensees = engines.opensees_status(settings)
        self._log_solver_status()
        self._refresh_action_enablement()

    def _on_set_units(self) -> None:
        """Options → Set Display Units — SAP2000 parity.

        The selection is stored in ``project.meta.display_units`` and converts
        every number a result view shows (force diagrams, displacements,
        tables, curves). The model keeps ``project.meta.units``: the values an
        engineer typed are never rewritten.
        """
        from PySide6.QtWidgets import QInputDialog

        if self._vm.project is None:
            QMessageBox.information(
                self,
                "Set Display Units",
                "Open or create a project first.",
            )
            return
        choices = [u.value for u in UnitSystem]
        current_value = self._current_display_units().value
        current_idx = choices.index(current_value)
        choice, ok = QInputDialog.getItem(
            self,
            "Set Display Units",
            "Unit system:",
            choices,
            current=current_idx,
            editable=False,
        )
        if not ok:
            return
        new_units = next(u for u in UnitSystem if u.value == choice)
        if new_units is self._current_display_units():
            return
        self._set_display_units(new_units)

    # ── helpers ──────────────────────────────────────────────────────
    def _refresh_tree(self, project: Project | None) -> None:
        """Repopulate the model explorer with category counts AND children."""

        # The category's English name is the key the selection sync dispatches
        # on; only the text on screen is translated.
        self._tree.setHeaderLabel(tr("Model"))

        # Helper to refill one category in place.
        def _fill(cat: QTreeWidgetItem, items: list, label_fn) -> None:  # type: ignore[no-untyped-def]
            kind = next(k for k, c in self._tree_categories.items() if c is cat)
            cat.takeChildren()
            cat.setText(0, f"{tr(kind)} ({len(items)})")
            for it in items:
                child = QTreeWidgetItem([label_fn(it)])
                # Tag with kind + id so selection sync can dispatch.
                child.setData(0, Qt.ItemDataRole.UserRole, (kind, it.id))
                cat.addChild(child)

        if project is None:
            for kind, cat in self._tree_categories.items():
                cat.takeChildren()
                cat.setText(0, f"{tr(kind)} (0)")
            return

        _fill(
            self._tree_categories["Nodes"],
            project.nodes,
            lambda n: f"#{n.id}  {n.name or ''}".strip(),
        )
        _fill(
            self._tree_categories["Elements"],
            project.elements,
            lambda e: f"#{e.id}  [{e.type}]  {e.name or ''}".strip(),
        )
        _fill(
            self._tree_categories["Materials"],
            project.materials,
            lambda m: f"#{m.id}  [{m.type}]  {m.name or ''}".strip(),
        )
        _fill(
            self._tree_categories["Sections"],
            project.sections,
            lambda s: f"#{s.id}  [{s.type}]  {s.name or ''}".strip(),
        )
        _fill(
            self._tree_categories["Time Series"],
            project.time_series,
            lambda t: f"#{t.id}  [{t.type}]  {t.name or ''}".strip(),
        )
        _fill(
            self._tree_categories["Patterns"],
            project.load_patterns,
            lambda p: f"#{p.id}  [{p.type}]  {p.name or ''}".strip(),
        )
        _fill(
            self._tree_categories["Analyses"],
            project.analyses,
            lambda a: f"#{a.id}  [{a.type}]  {a.name or ''}".strip(),
        )

    def _on_tree_selection_changed(self) -> None:
        """Sync the canvas selection with every picked Node / Element row.

        Multi-select via Ctrl+click / Shift+click populates the canvas
        selection in one atomic set_selection call — so commands like
        'Zero-Length Section' (needs exactly 2 joints) can be driven
        entirely from the tree.
        """
        node_ids: set[int] = set()
        element_ids: set[int] = set()
        for item in self._tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data is None:
                continue
            kind, entity_id = data
            if kind == "Nodes":
                node_ids.add(entity_id)
            elif kind == "Elements":
                element_ids.add(entity_id)
        if node_ids or element_ids:
            self._canvas.selection.set_selection(node_ids, element_ids)

    def _refresh_status(self) -> None:
        if self._vm.project is None:
            self._status_label.setText("No project")
            return
        path = self._vm.path.name if self._vm.path else "Untitled"
        marker = "*" if self._vm.is_dirty else ""
        self._status_label.setText(
            f"{path}{marker}  |  ndm={self._vm.project.ndm}, ndf={self._vm.project.ndf}"
        )

    def _refresh_action_enablement(self) -> None:
        has_project = self._vm.project is not None
        has_selection = not self._canvas.selection.is_empty
        has_selected_nodes = bool(self._canvas.selection.nodes)
        has_selected_elements = bool(self._canvas.selection.elements)
        has_static = self.results.static() is not None
        has_modal = isinstance(self.results.latest, ModalResults)
        has_transient = isinstance(self.results.latest, TransientResults)
        has_pushover = isinstance(self.results.latest, PushoverResults)
        has_rs = isinstance(self.results.latest, ResponseSpectrumResults)
        n_sel = len(self._canvas.selection.nodes)
        has_series = has_project and bool(self._vm.project and self._vm.project.time_series)
        self._actions.refresh(
            ActionState(
                has_project=has_project,
                has_selection=has_selection,
                has_selected_nodes=has_selected_nodes,
                has_two_selected_nodes=n_sel == 2,
                has_time_series=has_series,
                has_selected_elements=has_selected_elements,
            )
        )
        # The side "ps" button shows it, so it cannot wait for the Select menu.
        self.action("select.previous").setEnabled(
            has_project and any(self._canvas.selection.previous)
        )
        self._act_select_line.setEnabled(has_project)
        self._act_add_node.setEnabled(True)
        self._act_frame_wizard.setEnabled(has_project)
        self._act_truss_wizard.setEnabled(has_project)
        self._act_warehouse_wizard.setEnabled(has_project)
        self.action("define.create_shell").setEnabled(has_project and n_sel in (3, 4))
        has_cases = has_project and bool(self._vm.project and self._vm.project.analyses)
        # Without a solver the model is still built, exported and reported; only
        # what calls OpenSees waits for one (Options → Solver).
        solver = self._solver.available
        opensees = self._opensees.available
        self._act_run.setEnabled(solver)
        self._act_run.setStatusTip("" if solver else self._solver.summary())
        run_batch = self.action("file.run_batch")
        run_batch.setEnabled(solver)
        run_batch.setStatusTip("" if solver else self._solver.summary())
        # The Material Tester and the stability check call OpenSees itself,
        # whatever engine runs the cases.
        self.action("define.material_tester").setEnabled(opensees)
        self.action("define.material_tester").setStatusTip(
            "" if opensees else self._opensees.summary()
        )
        batch_enabled = has_cases and solver and not self._runner.is_running
        self._act_run_all.setEnabled(batch_enabled)
        self._act_run_selected.setEnabled(batch_enabled)
        project_now = self._vm.project
        stored = self.results.has_stored(project_now)
        db_there = has_project and database_path(self._vm.path).exists()
        self._act_clear_results.setEnabled(bool(has_project and (stored or db_there)))
        self._act_auto_mesh_frames.setEnabled(has_project)
        with QSignalBlocker(self._act_auto_mesh_frames):
            self._act_auto_mesh_frames.setChecked(
                project_now is None or project_now.auto_mesh_frames
            )
        self._act_check_stability.setEnabled(
            has_project
            and opensees
            and not self._stability.is_running
            and not self._runner.is_running
        )
        self._act_cancel_stability.setEnabled(self._stability.is_running)
        # Only there while a check runs, rather than a permanent grey entry.
        self._act_cancel_stability.setVisible(self._stability.is_running)
        self._act_check_model.setEnabled(has_project)
        self.action("edit.join_frames").setEnabled(
            has_project and len(self._canvas.selection.elements) >= 2
        )
        for action in self._restraint_actions():
            action.setEnabled(has_project and has_selected_nodes)
        self._act_custom_commands.setEnabled(has_project)
        self.action("assign.floor_load").setEnabled(
            has_project
            and has_selected_nodes
            and self._vm.project is not None
            and self._vm.project.ndm == 3
        )
        self.action("edit.paste").setEnabled(bool(self.transforms.clipboard_contents()[0]))
        self._act_tool_draw_frame.setEnabled(has_project)
        self._act_tool_draw_node.setEnabled(has_project)
        self._act_tool_draw_truss.setEnabled(has_project)
        self._act_tool_quick_frame.setEnabled(has_project)
        self._act_tool_quick_shell.setEnabled(has_project)
        self._act_tool_draw_shell.setEnabled(has_project)
        self._act_tool_measure.setEnabled(has_project)
        self._act_select_results.setEnabled(has_project)
        self._act_load_combinations.setEnabled(True)
        self.action("display.show_deformed").setEnabled(has_static)
        self.action("display.show_mode_shape").setEnabled(has_modal)
        self.action("display.show_force_diagram").setEnabled(has_static)
        self.action("display.shell_contours").setEnabled(
            has_static and bool(shell_elements(self._vm.project)) if self._vm.project else False,
        )
        self.action("display.show_time_history").setEnabled(has_transient)
        self.action("display.export_th_animation").setEnabled(has_transient)
        self.action("display.show_hysteresis").setEnabled(has_transient)
        self.action("display.show_pushover").setEnabled(has_pushover)
        self.action("display.influence_line").setEnabled(
            isinstance(self.results.latest, InfluenceLineResults)
        )
        self.action("display.show_response_spectrum").setEnabled(has_rs)
        self._act_display_options.setEnabled(has_project)
        self._act_show_load_assigns.setEnabled(has_project)
        self.model_lock.button.setEnabled(has_project)
        self._act_show_local_axes.setEnabled(has_project)
        self.action("display.back_to_model").setEnabled(self.display.dock is not None)
        # Startup gate: with no project open only File and Help stay usable. The
        # whole menu is disabled rather than every action inside it, so it cannot
        # open onto a wall of grey entries.
        for role in (
            "edit",
            "select",
            "define",
            "assign",
            "analyze",
            "display",
            "design",
            "view",
            "options",
        ):
            menu = self._menus.get(role)
            if menu is not None:
                menu.setEnabled(has_project)
        self._explain_disabled_actions()
        self._sync_visibility_actions()
        self.viewport.sync_show_all()

    #: Why an action is greyed out, by the condition it waits for. The tooltip
    #: and the status bar say it, so a disabled entry is not a dead end.
    _DISABLED_REASONS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Select two or more frame members first.", ("_act_join_frames",)),
        (
            "Select one or more joints first.",
            (
                "_act_assign_support",
                "_act_restraint_fixed",
                "_act_restraint_pinned",
                "_act_restraint_roller",
                "_act_restraint_free",
                "_act_assign_masses",
                "_act_assign_springs",
                "_act_remove_constraints",
                "_act_assign_load",
                "_act_assign_imposed_displacement",
                "_act_assign_joint_pattern",
                "_act_assign_floor_load",
                "_act_add_multi_support",
            ),
        ),
        (
            "Select exactly two joints first.",
            (
                "_act_assign_equal_dof",
                "_act_assign_rigid_link",
                "_act_assign_zero_length",
                "_act_assign_zls",
                "_act_assign_bearing",
                "_act_assign_link",
            ),
        ),
        ("Select three or four joints first.", ("_act_create_shell",)),
        (
            "Select one or more elements first.",
            (
                "_act_assign_section",
                "_act_assign_material",
                "_act_assign_geom_transf",
                "_act_assign_local_axes",
                "_act_assign_integration",
                "_act_assign_releases",
                "_act_assign_end_offsets",
                "_act_assign_insertion",
                "_act_assign_modifiers",
                "_act_assign_auto_mesh",
                "_act_assign_distributed_load",
                "_act_assign_trapezoidal_load",
                "_act_assign_frame_point_load",
                "_act_assign_temperature_load",
                "_act_assign_tendon",
                "_act_assign_hinge",
                "_act_assign_wall",
                "_act_assign_line_springs",
                "_act_assign_pile",
                "_act_shell_formulation",
                "_act_assign_surface_load",
                "_act_assign_area_springs",
                "_act_assign_edge_springs",
            ),
        ),
        (
            "Select joints or elements first.",
            (
                "_act_assign_group",
                "_act_delete",
                "_act_move",
                "_act_replicate",
                "_act_mirror",
                "_act_extrude",
                "_act_copy",
                "_act_hide_selected",
                "_act_isolate_selected",
            ),
        ),
        ("Copy a selection first (Edit → Copy).", ("_act_paste",)),
        (
            "Define a time series first (Define → Time Series).",
            ("_act_add_plain_pattern", "_act_add_uniform_excitation"),
        ),
        (
            "Run a Static analysis or a load combination first.",
            ("_act_show_deformed", "_act_show_force_diagram", "_act_shell_contours"),
        ),
        ("Run a Modal analysis first.", ("_act_show_mode_shape",)),
        (
            "Run a Transient (time-history) analysis first.",
            ("_act_show_time_history", "_act_export_th_animation", "_act_show_hysteresis"),
        ),
        ("Run a Pushover analysis first.", ("_act_show_pushover",)),
        ("Run a Response-Spectrum analysis first.", ("_act_show_response_spectrum",)),
        ("Run an influence-line case first.", ("_act_influence_line",)),
    )

    def _explain_disabled_actions(self) -> None:
        """Put the reason on every greyed-out action that has one, and clear it after."""
        for reason, names in self._DISABLED_REASONS:
            for name in names:
                action: QAction = getattr(self, name)
                # A toolbar button keeps its own tip ("ownTip") while enabled.
                own = str(action.property("ownTip") or "")
                tip = own if action.isEnabled() else tr(reason)
                action.setStatusTip(tip)
                action.setToolTip(tip)

    # ── busy cursor ─────────────────────────────────────────────────
    def _begin_busy(self, message: str = "") -> None:
        """Show the wait cursor; nested calls are counted, not stacked."""
        if self._busy_depth == 0:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._busy_depth += 1
        if message:
            self.statusBar().showMessage(message)

    def _end_busy(self) -> None:
        """Drop one busy level; the cursor returns when the last one goes."""
        if self._busy_depth == 0:
            return
        self._busy_depth -= 1
        if self._busy_depth == 0:
            QApplication.restoreOverrideCursor()

    @contextlib.contextmanager
    def _busy(self, message: str = "") -> Iterator[None]:
        """Wait cursor for a synchronous operation, restored even on error."""
        self._begin_busy(message)
        try:
            yield
        finally:
            self._end_busy()

    def _on_runner_running_changed(self, running: bool) -> None:
        """No wait cursor while the solver runs: the window stays usable, and the
        status-bar strip (``RunStatusWidget``) shows the case, progress and Cancel."""
        del running
        self._refresh_action_enablement()

    def _on_stability_running_changed(self, running: bool) -> None:
        """Wait cursor while the stability check runs."""
        if running:
            self._begin_busy("Checking model stability…")
        else:
            self._end_busy()
        self._refresh_action_enablement()

    def _log(self, message: str) -> None:
        self._console.appendPlainText(message)
        self.statusBar().showMessage(message, 5000)
