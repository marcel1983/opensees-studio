"""The wireframe a parametric wizard shows next to its fields.

An isometric sketch of the members a generator would create, one colour per
group, redrawn on every field change. It knows nothing of what the structure
is: a wizard hands it the joints, the members and which group each one is in.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from PySide6.QtCore import QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

_COS30 = math.cos(math.radians(30.0))


class WireframePreview(QWidget):
    """An isometric wireframe, one colour per member group."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lines: list[tuple[QColor, list[tuple[QPointF, QPointF]]]] = []
        self._bounds = (0.0, 0.0, 1.0, 1.0)
        self.setMinimumSize(300, 260)

    def sizeHint(self) -> QSize:
        return QSize(340, 320)

    def line_count(self) -> int:
        """Members drawn (for the tests)."""
        return sum(len(lines) for _colour, lines in self._lines)

    def clear(self) -> None:
        self._lines = []
        self.update()

    def set_members(
        self,
        nodes: Iterable[Any],
        elements: Iterable[Any],
        members: Mapping[str, Sequence[int]],
        colours: Mapping[str, str],
        *,
        origin: Sequence[float] = (0.0, 0.0, 0.0),
    ) -> None:
        """Draw ``elements`` between ``nodes``.

        ``members`` is group key -> element ids and ``colours`` group key ->
        colour; the groups are drawn in the order of ``colours``, so the last
        one lies on top.
        """
        ox, oy, oz = origin

        def project(coords: Sequence[float]) -> QPointF:
            x, y, z = coords[0] - ox, coords[1] - oy, coords[2] - oz
            return QPointF((x + y) * _COS30, (y - x) * 0.5 + z)

        points = {node.id: project(node.coords) for node in nodes}
        ends = {e.id: e.nodes for e in elements}
        self._lines = []
        for key, colour in colours.items():
            segments = [
                (points[ends[eid][0]], points[ends[eid][1]]) for eid in members.get(key, ())
            ]
            if segments:
                self._lines.append((QColor(colour), segments))
        if points:
            us = [p.x() for p in points.values()]
            vs = [p.y() for p in points.values()]
            self._bounds = (min(us), min(vs), max(us), max(vs))
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self.palette().base())
        if not self._lines:
            return
        u0, v0, u1, v1 = self._bounds
        margin = 12.0
        scale = min(
            (self.width() - 2 * margin) / max(u1 - u0, 1e-9),
            (self.height() - 2 * margin) / max(v1 - v0, 1e-9),
        )
        left = (self.width() - (u1 - u0) * scale) / 2.0
        top = (self.height() - (v1 - v0) * scale) / 2.0

        def screen(p: QPointF) -> QPointF:
            return QPointF(left + (p.x() - u0) * scale, top + (v1 - p.y()) * scale)

        for colour, segments in self._lines:
            painter.setPen(QPen(colour, 1.2))
            for a, b in segments:
                painter.drawLine(screen(a), screen(b))
        painter.end()


__all__ = ["WireframePreview"]
