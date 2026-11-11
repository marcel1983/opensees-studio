"""Non-modal window with one member's diagrams side by side.

Opened by right-clicking a frame element while a force diagram or a deformed
shape is on screen. The window shows, in a horizontal row:

* the axial force;
* the shears (V2 and V3);
* the moments (M2, M3 and torsion);
* the absolute and relative deformations;
* the applied span loads (distributed and point).

An envelope combination draws both bounds in the force panels. The data comes
from :mod:`opensees_studio.services.element_diagrams`; this module only draws
it and converts model units to the display units.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from opensees_studio.core import UnitConverter
from opensees_studio.services.element_diagrams import (
    ElementDiagramBundle,
    LoadSegment,
    PointLoad,
)
from opensees_studio.services.element_forces import ForceComponent
from opensees_studio.views.plot_style import add_legend, axis_label, readable_plot

_COMPONENT_COLORS = {
    ForceComponent.N: "#1f77b4",
    ForceComponent.V2: "#ff7f0e",
    ForceComponent.V3: "#2ca02c",
    ForceComponent.T: "#9467bd",
    ForceComponent.M2: "#d62728",
    ForceComponent.M3: "#8c564b",
}

_LOAD_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c")
_ZERO_PEN = pg.mkPen("#888888", width=1)


class _DiagramPanel(QWidget):
    """A titled plot with a note under it."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        heading = QLabel(f"<b>{title}</b>")
        layout.addWidget(heading)
        self.plot = readable_plot()
        self.plot.setMinimumWidth(230)
        self.plot.setMinimumHeight(300)
        layout.addWidget(self.plot, 1)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(
            f"color: {self.palette().color(QPalette.ColorRole.WindowText).name()};"
        )
        layout.addWidget(self.note)
        self._legend = None

    def reset(self) -> None:
        self.plot.clear()
        self._legend = None
        self.note.setText("")

    def set_note(self, text: str) -> None:
        self.note.setText(text)

    def legend(self) -> Any:
        if self._legend is None:
            self._legend = add_legend(self.plot)
        return self._legend


class _LoadsPanel(QWidget):
    """Two stacked plots: distributed loads and point loads (different units)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("<b>Applied loads</b>"))

        layout.addWidget(QLabel("Distributed / self weight"))
        self.distributed = readable_plot()
        self.distributed.setMinimumWidth(250)
        self.distributed.setMinimumHeight(140)
        layout.addWidget(self.distributed, 1)
        self.distributed_note = QLabel("")
        self.distributed_note.setWordWrap(True)
        self.distributed_note.setStyleSheet(
            f"color: {self.palette().color(QPalette.ColorRole.WindowText).name()};"
        )
        layout.addWidget(self.distributed_note)

        layout.addWidget(QLabel("Point loads"))
        self.point = readable_plot()
        self.point.setMinimumWidth(250)
        self.point.setMinimumHeight(140)
        layout.addWidget(self.point, 1)
        self.point_note = QLabel("")
        self.point_note.setWordWrap(True)
        self.point_note.setStyleSheet(
            f"color: {self.palette().color(QPalette.ColorRole.WindowText).name()};"
        )
        layout.addWidget(self.point_note)

        self._dist_legend = None
        self._point_legend = None

    def reset(self) -> None:
        self.distributed.clear()
        self.distributed_note.setText("")
        self._dist_legend = None
        self.point.clear()
        self.point_note.setText("")
        self._point_legend = None

    def dist_legend(self) -> Any:
        if self._dist_legend is None:
            self._dist_legend = add_legend(self.distributed)
        return self._dist_legend

    def point_legend(self) -> Any:
        if self._point_legend is None:
            self._point_legend = add_legend(self.point)
        return self._point_legend


class ElementDiagramWindow(QWidget):
    """A top-level, non-modal window for one frame element."""

    def __init__(
        self,
        bundle: ElementDiagramBundle,
        converter: UnitConverter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(1500, 720)
        self.setMinimumSize(1100, 560)
        self._bundle = bundle
        self._converter = converter
        self._build_ui()
        self.refresh()

    @property
    def bundle(self) -> ElementDiagramBundle:
        """The data currently drawn."""
        return self._bundle

    def set_bundle(self, bundle: ElementDiagramBundle, converter: UnitConverter) -> None:
        """Replace the element and redraw the window."""
        self._bundle = bundle
        self._converter = converter
        self.refresh()

    def set_units(self, converter: UnitConverter) -> None:
        """Redraw in a new display-unit system."""
        self._converter = converter
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self._header = QLabel()
        self._header.setTextFormat(Qt.TextFormat.RichText)
        self._header.setWordWrap(True)
        root.addWidget(self._header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._axial = _DiagramPanel("Axial force")
        self._shear = _DiagramPanel("Shear")
        self._moments = _DiagramPanel("Moments and torsion")
        self._deformation = _DiagramPanel("Deformation")
        self._loads = _LoadsPanel()
        for panel in (self._axial, self._shear, self._moments, self._deformation, self._loads):
            splitter.addWidget(panel)
        splitter.setSizes([280, 280, 280, 280, 320])
        root.addWidget(splitter, 1)

        self._notes = QLabel()
        self._notes.setWordWrap(True)
        self._notes.setMinimumHeight(64)
        self._notes.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._notes.setStyleSheet(
            f"color: {self.palette().color(QPalette.ColorRole.WindowText).name()};"
        )
        root.addWidget(self._notes)

    def refresh(self) -> None:
        """Draw the current bundle in the display units."""
        bundle = self._bundle
        converter = self._converter
        labels = converter.labels
        length = bundle.length * converter.length

        name = f" — {bundle.element_name}" if bundle.element_name else ""
        case = f" · Case '{bundle.case_name}'" if bundle.case_name else ""
        bound = f" · {bundle.bound} bound" if bundle.bound else ""
        self._header.setText(
            f"<b>Element {bundle.element_id}</b>{name} · {bundle.element_type} · "
            f"L = {length:.4g} {labels.length}{case}{bound}"
        )
        self.setWindowTitle(f"Element {bundle.element_id} — Diagrams")

        self._plot_force_panel(
            self._axial,
            (ForceComponent.N,),
            "Axial force",
            "force",
        )
        self._plot_force_panel(
            self._shear,
            (ForceComponent.V2, ForceComponent.V3),
            "Shear",
            "force",
        )
        self._plot_force_panel(
            self._moments,
            (ForceComponent.T, ForceComponent.M2, ForceComponent.M3),
            "Moment",
            "moment",
        )
        self._plot_deformation()
        self._plot_loads()

        notes = [
            "Forces and loads are in the member's local axes; deformations are magnitudes.",
            *bundle.notes,
        ]
        self._notes.setText("<br>".join(f"• {note}" for note in notes))
        self._notes.setVisible(True)

    # ── panels ──────────────────────────────────────────────────────

    def _plot_force_panel(
        self,
        panel: _DiagramPanel,
        components: tuple[ForceComponent, ...],
        title: str,
        quantity: str,
    ) -> None:
        panel.reset()
        series = [item for item in self._bundle.forces if item.component in components]
        if not series:
            panel.set_note("Not reported for this element.")
            return

        converter = self._converter
        labels = converter.labels
        unit = labels.moment if quantity == "moment" else labels.force
        factor = converter.moment if quantity == "moment" else converter.force
        length = self._bundle.length * converter.length
        if len(series) > 1:
            panel.legend()
        for item in series:
            x = item.x * converter.length
            y = item.values * factor
            color = _COMPONENT_COLORS[item.component]
            style = Qt.PenStyle.DashLine if item.label.lower() == "min" else Qt.PenStyle.SolidLine
            pen = pg.mkPen(color, width=2, style=style)
            name = item.component.value
            if item.label:
                name = f"{name} ({item.label})"
            panel.plot.plot(x, y, pen=pen, name=name)

        panel.plot.addLine(y=0, pen=_ZERO_PEN)
        panel.plot.setLabel("bottom", axis_label("Distance along member", labels.length))
        left_title = series[0].component.value if len(series) == 1 else title
        panel.plot.setLabel("left", axis_label(left_title, unit))
        panel.plot.setXRange(0.0, max(length, 1e-12), padding=0.02)
        panel.plot.enableAutoRange(axis="y")

        missing = [c.value for c in components if c not in {item.component for item in series}]
        if missing:
            panel.set_note(f"Not reported: {', '.join(missing)}.")

    def _plot_deformation(self) -> None:
        panel = self._deformation
        panel.reset()
        bundle = self._bundle
        if bundle.absolute is None or bundle.relative is None:
            panel.set_note("No nodal displacements in this result.")
            return

        converter = self._converter
        labels = converter.labels
        panel.legend()
        for curve, name, color, style in (
            (bundle.absolute, "Absolute |u|", "#1f77b4", Qt.PenStyle.DashLine),
            (bundle.relative, "Relative to chord", "#ff7f0e", Qt.PenStyle.SolidLine),
        ):
            panel.plot.plot(
                curve[0] * converter.length,
                curve[1] * converter.length,
                pen=pg.mkPen(color, width=2, style=style),
                name=name,
            )
        panel.plot.addLine(y=0, pen=_ZERO_PEN)
        panel.plot.setLabel("bottom", axis_label("Distance along member", labels.length))
        panel.plot.setLabel("left", axis_label("Deformation", labels.length))
        length = bundle.length * converter.length
        panel.plot.setXRange(0.0, max(length, 1e-12), padding=0.02)
        panel.plot.enableAutoRange(axis="y")
        panel.set_note("Absolute: total section displacement. Relative: departure from the chord.")

    def _plot_loads(self) -> None:
        loads = self._loads
        loads.reset()
        self._plot_distributed(loads, self._bundle.segments)
        self._plot_points(loads, self._bundle.points)

    def _plot_distributed(self, panel: _LoadsPanel, segments: tuple[LoadSegment, ...]) -> None:
        if not segments:
            panel.distributed_note.setText("No distributed load or self weight on this member.")
            return

        converter = self._converter
        labels = converter.labels
        factor = converter.force / converter.length
        names = ("wx", "wy", "wz")
        available = [
            index
            for index, _name in enumerate(names)
            if any(
                abs(segment.w0[index]) > 0.0 or abs(segment.w1[index]) > 0.0 for segment in segments
            )
        ]
        if not available:
            panel.distributed_note.setText("The distributed loads are zero on this member.")
            return
        panel.dist_legend()
        for index in available:
            name = names[index]
            xs: list[float] = []
            ys: list[float] = []
            for segment in segments:
                xs.extend([segment.x0 * converter.length, segment.x1 * converter.length, np.nan])
                ys.extend([segment.w0[index] * factor, segment.w1[index] * factor, np.nan])
            panel.distributed.plot(
                np.asarray(xs),
                np.asarray(ys),
                pen=pg.mkPen(_LOAD_COLORS[index], width=2),
                name=name,
                connect="finite",
            )
        panel.distributed.addLine(y=0, pen=_ZERO_PEN)
        panel.distributed.setLabel("bottom", axis_label("Distance along member", labels.length))
        panel.distributed.setLabel(
            "left", axis_label("Distributed load", f"{labels.force}/{labels.length}")
        )
        length = self._bundle.length * converter.length
        panel.distributed.setXRange(0.0, max(length, 1e-12), padding=0.02)
        panel.distributed.enableAutoRange(axis="y")

    def _plot_points(self, panel: _LoadsPanel, points: tuple[PointLoad, ...]) -> None:
        if not points:
            panel.point_note.setText("No point load on this member.")
            return

        converter = self._converter
        labels = converter.labels
        names = ("Px", "Py", "Pz")
        available = [
            index
            for index, _name in enumerate(names)
            if any(abs(point.p[index]) > 0.0 for point in points)
        ]
        if not available:
            panel.point_note.setText("The point loads are zero on this member.")
            return
        panel.point_legend()
        for index in available:
            name = names[index]
            values = [point for point in points if abs(point.p[index]) > 0.0]
            xs: list[float] = []
            ys: list[float] = []
            top_x: list[float] = []
            top_y: list[float] = []
            for point in values:
                x = point.x * converter.length
                y = point.p[index] * converter.force
                xs.extend([x, x, np.nan])
                ys.extend([0.0, y, np.nan])
                top_x.append(x)
                top_y.append(y)
            color = _LOAD_COLORS[index]
            panel.point.plot(
                np.asarray(xs),
                np.asarray(ys),
                pen=pg.mkPen(color, width=2),
                name=name,
                connect="finite",
            )
            panel.point.plot(
                top_x,
                top_y,
                pen=None,
                symbol="o",
                symbolSize=7,
                symbolBrush=color,
                symbolPen=None,
            )
        panel.point.addLine(y=0, pen=_ZERO_PEN)
        panel.point.setLabel("bottom", axis_label("Distance along member", labels.length))
        panel.point.setLabel("left", axis_label("Point load", labels.force))
        length = self._bundle.length * converter.length
        panel.point.setXRange(0.0, max(length, 1e-12), padding=0.02)
        panel.point.enableAutoRange(axis="y")


__all__ = ["ElementDiagramWindow"]
