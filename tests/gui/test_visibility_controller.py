"""What a viewport draws lives in ``VisibilityController`` and runs with no ``MainWindow``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMainWindow

from opensees_studio.core import Node, Project
from opensees_studio.core.view_settings import ViewSettings
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.controllers.visibility import VisibilityController
from opensees_studio.views.dialogs.view_colors import ViewColorsDialog

pytestmark = pytest.mark.gui


class _Canvas:
    """A viewport as the controller sees it: its settings, and a camera to fit."""

    def __init__(self) -> None:
        self.view_settings = ViewSettings()
        self.reframed = 0

    def set_view_settings(self, settings: ViewSettings) -> None:
        self.view_settings = settings

    def reframe(self) -> None:
        self.reframed += 1


class _Rig:
    """A controller on a bare window with a main viewport and a second one."""

    def __init__(self, qtbot, project: Project | None = None) -> None:  # type: ignore[no-untyped-def]
        self.parent = QMainWindow()
        qtbot.addWidget(self.parent)
        self.vm = ProjectViewModel(self.parent)
        if project is not None:
            self.vm.adopt(project)
        self.main = _Canvas()
        self.focused = self.main
        self.log: list[str] = []
        shell = Shell(
            window=self.parent,
            vm=self.vm,
            canvas=lambda: self.focused,  # type: ignore[arg-type, return-value]
            log=self.log.append,
            refresh_actions=lambda: None,
        )
        self.visibility = VisibilityController(shell, main_canvas=self.main)  # type: ignore[arg-type]
        self.nodes = self._tick("Nodes", checked=True)
        self.labels = self._tick("Node Labels")
        self.extruded = self._tick("Extruded Sections")
        self.extruded_twin = self._tick("Show Extruded Sections")
        self.colors = {mode: self._tick(mode) for mode in ("none", "section")}
        self.visibility.attach(
            toggles={
                "show_nodes": [self.nodes],
                "show_node_labels": [self.labels],
                "show_extruded": [self.extruded, self.extruded_twin],
            },
            color_by=self.colors,
        )

    def _tick(self, text: str, *, checked: bool = False) -> QAction:
        action = QAction(text, self.parent)
        action.setCheckable(True)
        action.setChecked(checked)
        return action


def test_the_window_owns_one_controller_and_its_ticks_reach_the_viewport(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.visibility, VisibilityController) and mw.visibility.parent() is mw
    assert mw._act_view_colors is mw.action("view.colors")
    assert mw._act_display_options is mw.action("display.display_options")
    mw._vm.new_project()

    mw._act_vis_nodes.trigger()
    assert not mw._main_canvas.view_settings.show_nodes
    mw._act_show_extruded.trigger()
    assert mw._main_canvas.view_settings.show_extruded
    assert mw._act_vis_extruded.isChecked()  # the Visibility twin ticks too
    mw._act_color_section.trigger()
    assert mw._main_canvas.view_settings.color_by == "section"
    # The main viewport is stored when the window closes: leave the defaults
    # for the windows of the tests that follow.
    mw._main_canvas.set_view_settings(ViewSettings())


def test_a_tick_changes_the_focused_viewport_and_nothing_else(qtbot) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot)
    second = _Canvas()
    rig.focused = second

    rig.nodes.trigger()
    rig.extruded_twin.trigger()

    assert not second.view_settings.show_nodes and second.view_settings.show_extruded
    assert rig.main.view_settings == ViewSettings()
    assert rig.extruded.isChecked()  # both ticks of one field follow

    # Focus returns to the main viewport: the ticks say what it shows.
    rig.focused = rig.main
    rig.visibility.sync_actions()
    assert rig.nodes.isChecked() and not rig.extruded.isChecked()
    assert not rig.extruded_twin.isChecked()
    assert rig.main.view_settings == ViewSettings()  # syncing fires nothing


def test_labels_are_remembered_for_the_display_options_dialog(qtbot) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot)
    assert not rig.visibility.node_labels

    rig.labels.trigger()

    assert rig.visibility.node_labels and not rig.visibility.element_labels
    assert rig.main.view_settings.show_node_labels


def test_color_by_and_the_colors_dialog(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot)
    rig.colors["section"].trigger()
    assert rig.main.view_settings.color_by == "section"

    rig.visibility.apply(color_by="none")
    assert rig.colors["none"].isChecked()

    monkeypatch.setattr(ViewColorsDialog, "exec", lambda _self: QDialog.DialogCode.Rejected)
    before = rig.main.view_settings
    rig.visibility.colors()
    assert rig.main.view_settings == before


def test_the_main_viewport_travels_in_the_project_file(qtbot) -> None:  # type: ignore[no-untyped-def]
    project = Project(ndm=3, ndf=6)
    project.nodes.append(Node(id=1, coords=(0, 0, 0)))
    rig = _Rig(qtbot, project)

    # Never customised: nothing is written, so the file stays as it was.
    rig.visibility.store_in_project()
    assert project.view is None

    rig.visibility.apply(show_nodes=False)
    rig.visibility.store_in_project()
    assert project.view is not None and not project.view.show_nodes

    # Another viewport state, then the project's is adopted again.
    rig.main.set_view_settings(ViewSettings())
    rig.visibility.restore_from_project()
    assert not rig.main.view_settings.show_nodes
    assert not rig.nodes.isChecked()
    assert rig.main.reframed == 1  # the camera stays on the model

    # A project that carries none gets the defaults.
    project.view = None
    rig.visibility.restore_from_project()
    assert rig.main.view_settings == ViewSettings()


def test_without_a_project_there_is_nothing_to_store_or_show(qtbot) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot)
    rig.visibility.store_in_project()
    rig.visibility.load_assigns()
    rig.visibility.restore_from_project()
    assert rig.main.view_settings == ViewSettings() and rig.main.reframed == 0
    assert rig.log == []
