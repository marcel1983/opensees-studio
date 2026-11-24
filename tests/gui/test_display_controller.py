"""The post-processing views of the Display menu live in ``DisplayController``."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMainWindow, QMessageBox

from opensees_studio.core import ElasticBeamColumn, Node, Project, UnitSystem
from opensees_studio.services.results import StaticResults
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.viewmodels.results_session import ResultsSession
from opensees_studio.views.controllers.display import DisplayController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.docks import ForceDiagramView

pytestmark = pytest.mark.gui

#: Command id -> the name the ribbon, the icons and the help table know it by.
DECLARED = {
    "display.show_deformed": "_act_show_deformed",
    "display.show_mode_shape": "_act_show_mode_shape",
    "display.show_force_diagram": "_act_show_force_diagram",
    "display.shell_contours": "_act_shell_contours",
    "display.show_time_history": "_act_show_time_history",
    "display.export_th_animation": "_act_export_th_animation",
    "display.show_hysteresis": "_act_show_hysteresis",
    "display.show_pushover": "_act_show_pushover",
    "display.influence_line": "_act_influence_line",
    "display.show_response_spectrum": "_act_show_response_spectrum",
    "display.back_to_model": "_act_back_to_model",
}


class _Canvas:
    """A viewport, as far as a view uses it: a caption, a renderer mode, a render."""

    def __init__(self) -> None:
        self.label: str | None = None
        self.modes: list[object] = []
        self.renders = 0
        self._renderer = SimpleNamespace(set_mode=lambda mode, *_source: self.modes.append(mode))

    def set_result_label(self, text: str | None) -> None:
        self.label = text

    def mapFromGlobal(self, pos: QPoint) -> QPoint:
        return pos

    def frame_element_at(self, x: float, _y: float) -> int | None:
        """The member under the pointer: the only one, on the left half of the view."""
        return 10 if x < 100 else None

    def render(self) -> None:
        self.renders += 1


class _Overlay:
    """A diagram, contour or ratio renderer: what it was asked to draw, and cleared."""

    def __init__(self) -> None:
        self.drawn: list[tuple] = []  # type: ignore[type-arg]
        self.cleared = 0
        self._shown = False

    @property
    def is_drawn(self) -> bool:
        return self._shown

    def render(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.drawn.append((args, kwargs))
        self._shown = True

    def clear(self) -> None:
        self.cleared += 1
        self._shown = False


def _project() -> Project:
    project = Project(ndm=3, ndf=6)
    project.nodes.extend([Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0))])
    project.elements.append(ElasticBeamColumn(id=10, nodes=(1, 2), section_id=1))
    return project


def _results() -> StaticResults:
    forces = np.zeros((1, 12))
    forces[0, 0] = 100.0
    forces[0, 6] = -100.0
    return StaticResults(
        case_id=1,
        case_name="GRAVITY",
        n_steps=1,
        node_disp={1: np.zeros((1, 6)), 2: np.zeros((1, 6))},
        element_forces={10: forces},
    )


def _controller(qtbot):  # type: ignore[no-untyped-def]
    """A controller on a bare window: no ``MainWindow``, stand-in viewports and overlays."""
    parent = QMainWindow()
    qtbot.addWidget(parent)
    vm = ProjectViewModel()
    vm.adopt(_project())
    main, second = _Canvas(), _Canvas()
    overlays = SimpleNamespace(diagram=_Overlay(), contours=_Overlay(), ratios=_Overlay())
    shown: list[object] = []
    results = ResultsSession()
    shell = Shell(
        window=parent,
        vm=vm,
        canvas=lambda: main,  # type: ignore[arg-type, return-value]
        log=lambda _text: None,
        refresh_actions=lambda: None,
    )
    controller = DisplayController(
        shell,
        results=results,
        diagram=overlays.diagram,
        contours=overlays.contours,
        ratios=overlays.ratios,
        canvases=lambda: [main, second],  # type: ignore[list-item]
        busy=lambda _message: contextlib.nullcontext(),
        select_rows=lambda _nodes, _elements: None,
        results_for_key=lambda _key: None,
        show_results=shown.append,
        display_units=lambda: UnitSystem.SI_M_N,
        set_display_units=lambda _units: None,
    )
    return controller, results, (main, second), overlays, shown, parent


def test_the_window_owns_one_controller_and_the_commands_point_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.display, DisplayController)
    assert mw.display.parent() is mw
    for action_id, attribute in DECLARED.items():
        assert getattr(mw, attribute) is mw.action(action_id), action_id
    assert mw.action("display.back_to_model").shortcut().toString() == "Ctrl+Shift+B"
    # No results and no view: the window leaves every one of them disabled.
    mw._vm.new_project(ndm=3, ndf=6)
    mw._refresh_action_enablement()
    assert not any(mw.action(action_id).isEnabled() for action_id in DECLARED)
    assert (mw.display.dock, mw.display.mode, mw.display.title) == (None, None, None)

    # A static result enables its views, and a view enables Back to Model View.
    mw._vm.project.nodes.extend([Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0))])
    mw._vm.project.elements.append(ElasticBeamColumn(id=10, nodes=(1, 2), section_id=1))
    mw.model_lock.after_analysis = False
    mw.results_view.show(_results())
    assert mw.action("display.show_deformed").isEnabled()
    assert mw.action("display.show_force_diagram").isEnabled()
    assert not mw.action("display.show_mode_shape").isEnabled()
    mw.action("display.show_force_diagram").trigger()
    assert mw.display.mode == "force" and mw.display.dock is not None
    mw._refresh_action_enablement()
    assert mw.action("display.back_to_model").isEnabled()
    mw.action("display.back_to_model").trigger()
    assert mw.display.dock is None
    mw._help_controller.uninstall()


def test_a_view_without_its_results_says_what_to_run(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    controller, _results_session, _canvases, overlays, _shown, _parent = _controller(qtbot)
    told: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, title, _text, *a, **k: told.append(title)
    )
    for show in (
        controller.show_deformed,
        controller.show_mode_shape,
        controller.show_force_diagram,
        controller.shell_contours,
        controller.show_time_history,
        controller.export_th_animation,
        controller.show_hysteresis,
        controller.show_pushover,
        controller.show_response_spectrum,
        controller.influence_line,
    ):
        show()
    assert told == [
        "Deformed Shape",
        "Mode Shape",
        "Force Diagram",
        "Shell Contours",
        "Time-History Plot",
        "Export Time-History Animation",
        "Hysteresis Plot",
        "Pushover Curve",
        "Response Spectrum",
        "Influence Line",
    ]
    assert controller.dock is None and controller.mode is None
    assert not overlays.diagram.drawn


def test_a_force_diagram_opens_a_dock_names_itself_and_back_to_model_undoes_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, results, (main, second), overlays, _shown, parent = _controller(qtbot)
    results.latest = _results()

    controller.show_force_diagram()

    dock = controller.dock
    assert dock is not None and dock.windowTitle() == "Force Diagram"
    assert dock.parent() is parent and isinstance(dock.widget(), ForceDiagramView)
    assert controller.mode == "force"
    # The axial force is the only one that is not zero, so it is the one drawn...
    assert controller.title == "Force Diagram N"
    assert overlays.diagram.drawn and main.renders >= 1
    # ...and every viewport says so, ahead of the case.
    assert main.label == second.label == "Force Diagram N  ·  GRAVITY  ·  Static"

    # A change of display units re-shows the open view.
    drawn = len(overlays.diagram.drawn)
    assert controller.refresh_units()
    assert len(overlays.diagram.drawn) == drawn + 1

    controller.back_to_model()
    assert (controller.dock, controller.mode, controller.title) == (None, None, None)
    assert main.label is None and second.label is None
    assert overlays.diagram.cleared == overlays.contours.cleared == overlays.ratios.cleared == 1
    assert main.modes  # the renderer went back to the model
    assert not controller.refresh_units()


def test_the_caption_carries_the_title_of_the_view(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, results, (main, second), _overlays, _shown, _parent = _controller(qtbot)
    controller.set_caption("GRAVITY  ·  Static")
    assert main.label == second.label == "GRAVITY  ·  Static"
    # Without results on screen a title alone changes nothing.
    controller.set_title("Deformed Shape")
    assert main.label == "GRAVITY  ·  Static"
    results.latest = _results()
    controller.set_title("Deformed Shape")
    assert main.label == "Deformed Shape  ·  GRAVITY  ·  Static"
    controller.tear_down()
    assert controller.title is None
    assert main.label == "GRAVITY  ·  Static"


def test_the_hover_text_follows_the_view(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, results, _canvases, _overlays, _shown, _parent = _controller(qtbot)
    # In the model view a joint and a member say what they are.
    assert controller.node_tooltip(2).startswith("Joint 2")
    assert controller.element_tooltip(10).startswith("ElasticBeamColumn 10")
    assert controller.element_tooltip(99) is None
    assert controller.element_tooltips_enabled()

    # A deformed shape is read at the joints: the case and its displacements.
    results.latest = _results()
    controller.mode = "deformed"
    assert not controller.element_tooltips_enabled()
    text = controller.node_tooltip(2)
    assert "<b>Joint 2</b>" in text and "Case: GRAVITY" in text
    # A mode shape without a modal result on screen falls back to the summary.
    controller.mode = "mode"
    assert controller.node_tooltip(2).startswith("Joint 2")
    assert not controller.element_tooltips_enabled()


def test_a_right_click_on_a_member_of_a_force_diagram_opens_its_window(qtbot) -> None:  # type: ignore[no-untyped-def]
    controller, results, (main, second), _overlays, _shown, _parent = _controller(qtbot)
    results.latest = _results()
    on_the_member, off_it = QPoint(10, 10), QPoint(500, 10)
    # In the model view the right-click stays the normal menu.
    assert not controller.open_member_at(on_the_member, main)

    controller.show_force_diagram()
    assert not controller.open_member_at(off_it, main)
    assert not controller.open_member_at(on_the_member, second)  # only the main viewport
    assert controller.open_member_at(on_the_member, main)
    assert [w.bundle.element_id for w in controller.member_windows] == [10]
    controller.show_member(10)  # the same member: the same window
    assert len(controller.member_windows) == 1

    # The windows belong to the view: they close with it.
    controller.back_to_model()
    assert controller.member_windows == []
