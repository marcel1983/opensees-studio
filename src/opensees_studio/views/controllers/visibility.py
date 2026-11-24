"""What a viewport draws: the visibility ticks, the colours and the display options."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog

from opensees_studio.core.view_settings import ViewSettings
from opensees_studio.views.canvas3d import ModelCanvas
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import DisplayOptionsDialog
from opensees_studio.views.dialogs.load_display import LoadDisplayDialog
from opensees_studio.views.dialogs.view_colors import ViewColorsDialog


class VisibilityController(QObject):
    """The view settings of the focused viewport and the commands that change them.

    View → Visibility, Show Extruded Sections, Show Local Axes, Color By and
    Colors; Display → Display Options and Show Load Assigns. None of it touches
    the model: a :class:`ViewSettings` belongs to one canvas. The primary
    viewport's settings travel in the project file (:meth:`store_in_project`
    before a save, :meth:`restore_from_project` after an open).

    The ticks are the window's actions: it hands them over once they exist
    (:meth:`attach`), one or more per ``ViewSettings`` field, and
    :meth:`sync_actions` keeps them truthful after any change, whichever path
    made it. ``main_canvas`` is the primary viewport.
    """

    def __init__(self, shell: Shell, *, main_canvas: ModelCanvas) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._main_canvas = main_canvas
        self._toggles: dict[str, tuple[QAction, ...]] = {}
        self._color_by: dict[str, QAction] = {}
        #: The two label boxes of the Display Options dialog, as last set.
        self.node_labels = False
        self.element_labels = False

    def attach(
        self, *, toggles: Mapping[str, Sequence[QAction]], color_by: Mapping[str, QAction]
    ) -> None:
        """Take the window's ticks: ``toggles`` by ``ViewSettings`` field, ``color_by`` by mode."""
        self._toggles = {field: tuple(actions) for field, actions in toggles.items()}
        self._color_by = dict(color_by)
        for field, actions in self._toggles.items():
            for action in actions:
                action.toggled.connect(partial(self.toggle, field))
        for mode, action in self._color_by.items():
            action.triggered.connect(lambda _=False, mode=mode: self.color_by(mode))

    def apply(self, **changes: object) -> None:
        """Apply ``changes`` to this viewport's settings and resync the ticks."""
        self._shell.canvas().set_view_settings(
            self._shell.canvas().view_settings.with_changes(**changes)
        )
        self.sync_actions()

    def sync_actions(self) -> None:
        """Tick every visibility action from the canvas without re-firing it."""
        settings = self._shell.canvas().view_settings
        for field, actions in self._toggles.items():
            for action in actions:
                action.blockSignals(True)
                action.setChecked(getattr(settings, field))
                action.blockSignals(False)
        if self._color_by:
            color_by = self._color_by[settings.color_by]
            color_by.blockSignals(True)
            color_by.setChecked(True)
            color_by.blockSignals(False)

    def toggle(self, field: str, checked: bool) -> None:
        """Apply one visibility tick to the viewport."""
        # The labels are also the two boxes of the Display Options dialog.
        if field == "show_node_labels":
            self.node_labels = checked
        elif field == "show_element_labels":
            self.element_labels = checked
        self.apply(**{field: checked})

    def color_by(self, mode: str) -> None:
        """View → Color By: paint frames and shells by section, material or group."""
        self.apply(color_by=mode)

    def colors(self) -> None:
        """View → Colors: edit the six viewport colours in one dialog."""
        dialog = ViewColorsDialog(self._shell.canvas().view_settings, parent=self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply(**dialog.colors())

    def options(self) -> None:
        """Display → Display Options: the labels and the sizes of what the viewport draws."""
        dlg = DisplayOptionsDialog(
            show_node_labels=self.node_labels,
            show_element_labels=self.element_labels,
            view_settings=self._shell.canvas().view_settings,
            parent=self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.node_labels, self.element_labels = dlg.values()
        settings = dlg.view_settings()
        self._shell.canvas().set_view_settings(settings)
        self.sync_actions()
        self._shell.log(
            f"Display options updated: node labels={'on' if self.node_labels else 'off'}, "
            f"element labels={'on' if self.element_labels else 'off'}, "
            f"node size={settings.node_size_percent:g}% of the view height."
        )

    def load_assigns(self) -> None:
        """Display → Show Load Assigns: the pattern, kinds and values the canvas draws."""
        project = self._vm.project
        if project is None:
            return
        dlg = LoadDisplayDialog(
            project.load_patterns, self._shell.canvas().view_settings, parent=self._window
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        changes = dlg.changes()
        self.apply(**changes)
        pattern_id = changes["load_pattern_id"]
        pattern = next((p for p in project.load_patterns if p.id == pattern_id), None)
        self._shell.log(
            "Loads shown: "
            + ("every load pattern" if pattern is None else f"load pattern '{pattern.name}'")
            + "."
        )

    def restore_from_project(self) -> None:
        """Adopt the display settings the project carries."""
        project = self._vm.project
        stored = project.view if project is not None else None
        self._main_canvas.set_view_settings(stored if stored is not None else ViewSettings())
        self.sync_actions()
        # Re-rendering for the new settings may fit the camera to every actor
        # again (including furniture left from the previous file); keep it on
        # the new model.
        if project is not None and project.nodes:
            self._main_canvas.reframe()

    def store_in_project(self) -> None:
        """Write the primary viewport's settings into the model before saving.

        A viewport that was never customised stores ``None``, so the file stays
        byte-identical to one written before this feature existed.
        """
        project = self._vm.project
        if project is None:
            return
        settings = self._main_canvas.view_settings
        project.view = None if settings == ViewSettings() else settings
