"""What the focused viewport shows and from where it is looked at."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QComboBox, QDialog

from opensees_studio.core import Project
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.grid_line_view import GridLineViewDialog


class ViewportController(QObject):
    """The camera, the working plane and its level, a grid line view, what is hidden.

    A plan or an elevation (Top, Front, Right) makes its plane the working
    plane and fills :attr:`level_combo` with the grid ordinates across it; Move
    Up/Down in List steps through them and shows only the objects on that
    level, which is a grid line view (:attr:`grid_view`: the line's label and
    the window around it). Hiding, isolating and inverting act on the focused
    viewport only: the project keeps every object. ``action`` is the window's
    ``action(id)``, for the commands this enables itself.
    """

    def __init__(self, shell: Shell, *, action: Callable[[str], QAction]) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._action = action
        #: The grid line being viewed, as ``(label, window)``; None shows everything.
        self.grid_view: tuple[str, float] | None = None
        #: The window the user last chose for a grid line view.
        self.grid_view_window: float | None = None
        #: The Level list of the View toolbar (the window puts it there).
        self.level_combo = QComboBox()
        self.level_combo.setMinimumWidth(120)
        self.level_combo.setToolTip(
            "Active plan / elevation level. Click a view button first "
            "(Top, Front, Right) to populate the list from the grid."
        )
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)

    def forget_grid_line(self) -> None:
        """Another project: its grid lines are not the ones being viewed."""
        self.grid_view = None
        self.grid_view_window = None

    def rotate_left(self) -> None:
        self._rotate(-1, 0)

    def rotate_right(self) -> None:
        self._rotate(1, 0)

    def rotate_up(self) -> None:
        self._rotate(0, 1)

    def rotate_down(self) -> None:
        self._rotate(0, -1)

    def level_up(self) -> None:
        self._step_level(1)

    def level_down(self) -> None:
        self._step_level(-1)

    def iso(self) -> None:
        """Isometric: clear any working plane (full 3D snap)."""
        self._shell.canvas().clear_working_plane()
        self._shell.canvas().view_isometric()
        self._populate_level_combo(None)

    def top(self) -> None:
        """Top (XY): camera looks down -Z. Level = perpendicular axis Z."""
        self._shell.canvas().view_xy()
        self._activate_working_plane("XY")

    def front(self) -> None:
        """Front (XZ): camera looks down -Y. Level = perpendicular axis Y."""
        self._shell.canvas().view_xz()
        self._activate_working_plane("XZ")

    def right(self) -> None:
        """Right (YZ): camera looks down -X. Level = perpendicular axis X."""
        self._shell.canvas().view_yz()
        self._activate_working_plane("YZ")

    def _rotate(self, left_right: int, up_down: int) -> None:
        """View → Rotate: turn the camera one step (15°) about the model."""
        self._leave_plane_view()
        step = self._shell.canvas().ROTATE_STEP_DEG
        self._shell.canvas().orbit(azimuth=left_right * step, elevation=up_down * step)

    def spin(self, on: bool) -> None:
        """View → Spin: turn the view continuously until switched off."""
        if on:
            self._leave_plane_view()
        self._shell.canvas().set_spinning(on)

    def toggle_parallel(self, on: bool) -> None:
        cam = self._shell.canvas().camera
        cam.parallel_projection = on
        self._shell.canvas().render()

    def _leave_plane_view(self) -> None:
        """Turning the camera leaves a plan or elevation: back to full 3D snapping."""
        self._shell.canvas().clear_working_plane()
        self._populate_level_combo(None)

    def _activate_working_plane(self, plane: str) -> None:
        """Populate the Level combo from the grid and default to the first
        ordinate on the perpendicular axis. Commits the working plane to
        the canvas so snap / drawing filter by that level."""
        ordinates = self._ordinates_for_plane(plane)
        self._populate_level_combo((plane, ordinates))
        if ordinates:
            # Default to the first level (usually 0). Sets working plane.
            self._shell.canvas().set_working_plane(plane, ordinates[0])
        else:
            # No grid on the perpendicular axis — keep the plane active at 0.
            self._shell.canvas().set_working_plane(plane, 0.0)

    def _ordinates_for_plane(self, plane: str) -> list[float]:
        """Return the ordinate list of the axis PERPENDICULAR to ``plane``.

        Pulls from every visible CoordinateGridSystem's Global-frame
        contribution — that's a conservative superset that works even
        when multiple coord systems overlap.
        """
        if self._vm.project is None:
            return []
        axis_to_attr = {"XY": "z_lines", "XZ": "y_lines", "YZ": "x_lines"}
        attr = axis_to_attr[plane]
        acc: set[float] = set()
        for cs in self._vm.project.coord_systems:
            if not cs.grid.shown or (cs.grid.is_cylindrical and plane != "XY"):
                # A cylindrical grid has levels (Z) but no X or Y lines.
                continue
            ords = cs.grid.visible_ordinates()[{"x_lines": 0, "y_lines": 1, "z_lines": 2}[attr]]
            # For non-Global systems we'd need to transform through the
            # coord system's origin+rotation. For the first cut we apply
            # a simple translation (ignore rotation) since only the
            # perpendicular component matters for plan/elevation choice.
            idx = {"z_lines": 2, "y_lines": 1, "x_lines": 0}[attr]
            for o in ords:
                acc.add(round(o + cs.coord.origin[idx], 6))
        return sorted(acc)

    def _populate_level_combo(self, state: tuple[str, list[float]] | None) -> None:
        """Fill or empty the Level combo.

        ``state`` is ``(plane_name, ordinates)`` — the combo shows each
        ordinate as e.g. "Z = 3.000". Passing ``None`` empties the
        combo (iso / no working plane).
        """
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        if state is not None and state[1]:
            plane, ordinates = state
            letter = {"XY": "Z", "XZ": "Y", "YZ": "X"}[plane]
            for o in ordinates:
                self.level_combo.addItem(f"{letter} = {o:g}", o)
            self.level_combo.setEnabled(True)
        else:
            self.level_combo.setEnabled(False)
        self.level_combo.blockSignals(False)
        stepping = self.level_combo.count() > 1
        self._action("view.level_up").setEnabled(stepping)
        self._action("view.level_down").setEnabled(stepping)

    def _on_level_changed(self, _idx: int) -> None:
        """User picked a different level from the combo."""
        data = self.level_combo.currentData()
        if data is None:
            return
        plane = self._shell.canvas().working_plane_type()
        if plane is None:
            return
        self._shell.canvas().set_working_plane(plane, float(data))
        if self.grid_view is not None:
            # Showing one level's objects: follow the level that was picked.
            self._show_level_only(plane, float(data))

    def _step_level(self, step: int) -> None:
        """View → Move Up/Down in List: the next level of the plan or elevation.

        As in SAP2000, the view then shows only the objects on that level
        (View → Show All Objects brings the rest back).
        """
        plane = self._shell.canvas().working_plane_type()
        count = self.level_combo.count()
        if plane is None or count == 0:
            return
        index = self.level_combo.currentIndex() + step
        if not 0 <= index < count:
            self._window.statusBar().showMessage("No further level in that direction.", 3000)
            return
        showing_level = self.grid_view is not None
        self.level_combo.setCurrentIndex(index)  # moves the working plane
        if not showing_level:
            self._show_level_only(plane, float(self.level_combo.itemData(index)))

    def _show_level_only(self, plane: str, level: float) -> None:
        """Show only the objects on the grid line at ``level`` (a grid line view)."""
        from opensees_studio.core.grid_view import default_window, line_at_level

        project = self._vm.project
        if project is None:
            return
        ref = line_at_level(project, {"YZ": 0, "XZ": 1, "XY": 2}[plane], level)
        if ref is None:
            return
        window = self.grid_view_window
        if window is None:
            window = default_window(project.meta.units)
        self.grid_view = (ref.label, window)
        self.apply_grid_line_view()

    def grid_line_view(self) -> None:
        """Show only the objects on one grid line (± a window) and look at it face on."""
        project = self._vm.project
        if project is None:
            return
        current = self.grid_view[0] if self.grid_view is not None else None
        dlg = GridLineViewDialog(
            project, current=current, window=self.grid_view_window, parent=self._window
        )
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.line() is None:
            return
        ref = dlg.line()
        assert ref is not None
        self.grid_view_window = dlg.tolerance()
        self.grid_view = (ref.label, self.grid_view_window)
        self.apply_grid_line_view()
        self._face_grid_line(ref)

    def apply_grid_line_view(self) -> None:
        """(Re)install the canvas filter for the current grid line view, if any."""
        from opensees_studio.core.grid_view import (
            filtered_project,
            find_grid_line,
            objects_on_line,
        )

        project = self._vm.project
        state = self.grid_view
        ref = find_grid_line(project, state[0]) if project is not None and state else None
        if state is None or ref is None:
            if state is not None:
                self._shell.log(
                    f"Grid line view: '{state[0]}' no longer exists, showing everything."
                )
            self.grid_view = None
            self._shell.canvas().set_view_filter(None)
            self.sync_show_all()
            return
        window = state[1]

        def keep(full: Project) -> Project:
            nodes, elements = objects_on_line(full, ref, window)
            return filtered_project(full, nodes, elements)

        self._shell.canvas().set_view_filter(keep)
        self.sync_show_all()
        nodes, elements = objects_on_line(project, ref, window)  # type: ignore[arg-type]
        self._window.statusBar().showMessage(
            f"Grid line view {ref.label} ± {window:g}: {len(nodes)} joint(s), "
            f"{len(elements)} element(s). View → Show All Objects to see everything."
        )

    def _face_grid_line(self, ref: Any) -> None:
        """Look at a plane line face on, with its level as the working plane."""
        if ref.cylindrical and ref.axis != 2:
            self.iso()
            return
        plane = ("YZ", "XZ", "XY")[ref.axis]
        project = self._vm.project
        system = next(cs for cs in project.coord_systems if cs.name == ref.system)  # type: ignore[union-attr]
        point = [0.0, 0.0, 0.0]
        point[ref.axis] = ref.ordinate
        offset = system.coord.local_to_world((point[0], point[1], point[2]))[ref.axis]
        {"YZ": self.right, "XZ": self.front, "XY": self.top}[plane]()
        index = next(
            (
                i
                for i in range(self.level_combo.count())
                if abs(float(self.level_combo.itemData(i)) - offset) < 1e-6
            ),
            -1,
        )
        if index >= 0:
            self.level_combo.setCurrentIndex(index)
        else:
            self._shell.canvas().set_working_plane(plane, offset)
        self._shell.canvas().reframe()

    def show_all_objects(self) -> None:
        self.grid_view = None
        self._shell.canvas().set_view_filter(None)
        self._shell.canvas().set_hidden(nodes=set(), elements=set())
        self._shell.canvas().reframe()
        self._shell.refresh_actions()
        self._window.statusBar().showMessage("Showing all objects.", 3000)

    def hide_selected(self) -> None:
        """Hide the selection in this viewport; the project keeps the entities."""
        selection = self._shell.canvas().selection
        hidden_nodes, hidden_elements = self._shell.canvas().hidden
        self._shell.canvas().set_hidden(
            nodes=set(hidden_nodes) | set(selection.nodes),
            elements=set(hidden_elements) | set(selection.elements),
        )
        self._shell.refresh_actions()

    def isolate_selected(self) -> None:
        """Show only the selection (and the joints of selected elements)."""
        project = self._vm.project
        selection = self._shell.canvas().selection
        if project is None or selection.is_empty:
            return
        selected_elements = set(selection.elements)
        visible_nodes = set(selection.nodes)
        for element in project.elements:
            if element.id in selected_elements:
                visible_nodes.update(element.nodes)
        all_nodes = {node.id for node in project.nodes}
        all_elements = {element.id for element in project.elements}
        self._shell.canvas().set_hidden(
            nodes=all_nodes - visible_nodes,
            elements=all_elements - selected_elements,
        )
        self._shell.refresh_actions()
        parts = []
        if visible_nodes:
            parts.append(f"{len(visible_nodes)} joint(s)")
        if selected_elements:
            parts.append(f"{len(selected_elements)} element(s)")
        self._window.statusBar().showMessage(
            f"Isolated {', '.join(parts)}. View > Show All Objects to restore.",
            5000,
        )

    def invert_visible(self) -> None:
        """Swap what this viewport shows: hidden becomes visible and vice versa."""
        project = self._vm.project
        if project is None:
            return
        hidden_nodes, hidden_elements = self._shell.canvas().hidden
        self._shell.canvas().set_hidden(
            nodes={n.id for n in project.nodes} - hidden_nodes,
            elements={e.id for e in project.elements} - hidden_elements,
        )
        self._shell.refresh_actions()

    def sync_show_all(self) -> None:
        """Enable Show All when a viewport filter or a hidden set is active."""
        hidden_nodes, hidden_elements = self._shell.canvas().hidden
        self._action("view.show_all_objects").setEnabled(
            self.grid_view is not None or bool(hidden_nodes) or bool(hidden_elements)
        )
