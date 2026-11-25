"""The eave overhangs (aleros) of a generated warehouse.

An overhang is a cantilever at each frame that carries the roof past a side
wall: it goes on from the eave along the slope of the last stretch of roof,
``spec.overhang`` in plan, with purlins on it at the purlin spacing (the last
one at its tip). It has its own section (key ``"overhang"``) and its own group.

What it carries is a strip of roof beyond the eave: half of each space between
its purlins goes to the purlin on either side, and the half space next to the
wall to the eave purlin. :func:`overhang_strips` lists those strips, which the
load functions of :mod:`opensees_studio.core.warehouse` add to the ones of the
roof between the walls. Under wind the strip takes the roof's pressure at the
eave on top and the pressure of the wall below on its underside (EN 1991-1-4
7.2.1 (3); the internal pressure, in both, cancels).

Built after the end walls, so a warehouse without overhangs keeps its ids.
No Qt, no OpenSees.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opensees_studio.core.warehouse import RoofStation, Warehouse, WarehouseSpec

#: Where a warehouse has overhangs: both side walls, or only one of them.
OVERHANG_SIDES: tuple[str, ...] = ("both", "x0", "x1")


@dataclass(frozen=True)
class OverhangStrip:
    """A half space of overhang roof and the purlin that carries it."""

    element_id: int
    wall: str
    """The side wall under the overhang, ``"x0"`` or ``"x1"``."""
    eave_x: float
    """Plan position of the eave: the wind on top is the roof's there."""
    plan_width: float
    slope_width: float
    normal: tuple[float, float, float]
    """Upward normal of the overhang's roof."""


@dataclass(frozen=True)
class Overhang:
    """The overhang over one side wall: its purlin lines from the eave out."""

    wall: str
    eave: int
    """Index of the eave's roof station."""
    eave_point: tuple[float, float]
    """``(x, z)`` of the eave."""
    xs: list[float]
    zs: list[float]
    """Purlin lines out from the eave (the eave not included), the last at the tip."""
    slope: float
    """dz/dx of the overhang."""

    @property
    def length(self) -> float:
        """Length of the cantilever, along its slope."""
        x0, z0 = self.eave_point
        return math.hypot(self.xs[-1] - x0, self.zs[-1] - z0)

    @property
    def normal(self) -> tuple[float, float, float]:
        """Upward normal of the overhang's roof."""
        n = math.hypot(self.slope, 1.0)
        return (-self.slope / n, 0.0, 1.0 / n)

    @property
    def angle(self) -> float:
        """``local_axis_angle`` that stands a purlin's web normal to the overhang."""
        return math.degrees(math.atan2(-self.slope, 1.0))


def overhangs(spec: WarehouseSpec, stations: list[RoofStation]) -> list[Overhang]:
    """The overhangs of ``spec``, on the stretch of roof the eave ends."""
    if spec.overhang <= 0.0:
        return []
    out: list[Overhang] = []
    for wall, eave, inner, outward in (
        ("x0", 0, 1, -1.0),
        ("x1", len(stations) - 1, len(stations) - 2, 1.0),
    ):
        if spec.overhang_sides not in ("both", wall):
            continue
        here, there = stations[eave], stations[inner]
        slope = (here.z - there.z) / (here.x - there.x)
        run = spec.overhang * math.hypot(1.0, slope)
        count = max(1, math.ceil(run / spec.purlin_spacing - 1e-9))
        xs = [here.x + outward * spec.overhang * k / count for k in range(1, count + 1)]
        zs = [here.z + slope * (x - here.x) for x in xs]
        out.append(
            Overhang(wall=wall, eave=eave, eave_point=(here.x, here.z), xs=xs, zs=zs, slope=slope)
        )
    return out


def build_overhangs(
    warehouse: Warehouse,
    roof_nodes: list[list[int]],
    add_node: Callable[[float, float, float], int],
    add_element: Callable[..., int],
    *,
    secondary_releases: Any,
    portable: Callable[[float], float],
) -> None:
    """Add the cantilevers and their purlins to ``warehouse`` (``build_warehouse`` calls it)."""
    spec = warehouse.spec
    for overhang in overhangs(spec, warehouse.stations):
        angle = portable(overhang.angle)
        lines: list[list[int]] = []  # [frame][purlin line out from the eave]
        for frame, tops in enumerate(roof_nodes):
            y = frame * spec.frame_spacing
            chain = [tops[overhang.eave]]
            chain += [add_node(x, y, z) for x, z in zip(overhang.xs, overhang.zs, strict=True)]
            for a, b in itertools.pairwise(chain):
                element_id = add_element("overhangs", a, b, "overhang")
                # The cantilever's bottom flange is in compression under gravity, and
                # the purlins on its top flange do not hold it: braced only at the eave.
                warehouse.unbraced[element_id] = portable(overhang.length)
            lines.append(chain[1:])
        for bay in range(spec.n_bays):
            for k in range(len(overhang.xs)):
                element_id = add_element(
                    "purlins",
                    lines[bay][k],
                    lines[bay + 1][k],
                    "purlin",
                    releases=secondary_releases,
                    angle=angle,
                )
                warehouse.overhang_purlins[element_id] = (overhang.wall, k)


def overhang_strips(warehouse: Warehouse) -> list[OverhangStrip]:
    """Each half space of overhang roof with the purlin that carries it."""
    spec = warehouse.spec
    eave_purlins: dict[int, list[int]] = {}
    for element_id, k in warehouse.purlin_station.items():
        eave_purlins.setdefault(k, []).append(element_id)
    by_line: dict[tuple[str, int], list[int]] = {}
    for element_id, key in warehouse.overhang_purlins.items():
        by_line.setdefault(key, []).append(element_id)
    strips: list[OverhangStrip] = []
    for overhang in overhangs(spec, warehouse.stations):
        points = [overhang.eave_point, *zip(overhang.xs, overhang.zs, strict=True)]
        purlins = [
            eave_purlins.get(overhang.eave, []),
            *(by_line.get((overhang.wall, k), []) for k in range(len(overhang.xs))),
        ]
        for k in range(len(points)):
            for other in (k - 1, k + 1):
                if not 0 <= other < len(points):
                    continue
                dx = points[other][0] - points[k][0]
                dz = points[other][1] - points[k][1]
                for element_id in purlins[k]:
                    strips.append(
                        OverhangStrip(
                            element_id=element_id,
                            wall=overhang.wall,
                            eave_x=overhang.eave_point[0],
                            plan_width=abs(dx) / 2.0,
                            slope_width=math.hypot(dx, dz) / 2.0,
                            normal=overhang.normal,
                        )
                    )
    return strips


def strip_widths(warehouse: Warehouse, *, projected: bool) -> dict[int, float]:
    """Purlin element id -> width of overhang roof it carries (plan or slope)."""
    out: dict[int, float] = {}
    for strip in overhang_strips(warehouse):
        width = strip.plan_width if projected else strip.slope_width
        out[strip.element_id] = out.get(strip.element_id, 0.0) + width
    return out


__all__ = [
    "OVERHANG_SIDES",
    "Overhang",
    "OverhangStrip",
    "build_overhangs",
    "overhang_strips",
    "overhangs",
    "strip_widths",
]
