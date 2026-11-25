"""Longitudinal roof stiffeners and the kinds of wall bracing of a generated warehouse.

**Roof stiffeners** run along the building from frame to frame on purlin lines:
one at mid-span of each nave and ``spec.stiffener_lines`` more on each side,
evenly between mid-span and the column lines. A *beam* is continuous and
framed into the rafters; a *truss* has that beam as its top chord, a bottom
chord ``spec.stiffener_depth`` below it, a vertical at every frame and one
diagonal per bay. Either takes the place of the purlin on its line, and its
load. With stiffeners the roof X braces are cut at their lines, so each X lies
within a space between two of them.

**Wall bracing** in the braced bays of the side walls is one of:

* ``"x"``: one X from the base to the eave;
* ``"double_x"``: two X, one above the other, with a strut between the two
  columns at mid-height (the girt line nearest it, when the wall has girts);
* ``"moment_frame"``: no X; the eave member of that bay is a beam framed into
  the two columns, which hold the wall along the building by bending.

No Qt, no OpenSees.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opensees_studio.core.warehouse import RoofStation, Warehouse, WarehouseSpec

#: What stiffens the roof along the building.
ROOF_STIFFENERS: tuple[str, ...] = ("none", "beam", "truss")
#: The kinds of bracing of a braced bay of a side wall.
WALL_BRACING_TYPES: tuple[str, ...] = ("x", "double_x", "moment_frame")
#: Section keys of the stiffeners and of the wall bracing, with their defaults.
STIFFENER_SECTION_SHAPES: dict[str, str] = {
    "stiffener": "W8X18",
    "stiffener_chord": "HSS4X4X1_4",
    "stiffener_web": "HSS3X3X3_16",
    "wall_strut": "HSS4X4X1_4",
    "wall_beam": "W12X26",
}


def check_stiffeners(spec: WarehouseSpec) -> str | None:
    """Why the stiffeners and wall bracing of ``spec`` cannot be built, or None."""
    if spec.roof_stiffeners not in ROOF_STIFFENERS:
        return f"Unknown roof stiffener {spec.roof_stiffeners!r}."
    if spec.wall_bracing_type not in WALL_BRACING_TYPES:
        return f"Unknown wall bracing {spec.wall_bracing_type!r}."
    if spec.stiffener_lines < 0:
        return "The number of stiffener lines cannot be negative."
    if spec.roof_stiffeners == "truss":
        if spec.has_truss:
            return "A stiffening truss needs a roof on rafters: the roof trusses take its place."
        if spec.stiffener_depth <= 0.0:
            return "The depth of the stiffening truss must be positive."
        if spec.stiffener_depth >= spec.eave_height:
            return "The depth of the stiffening truss must be less than the eave height."
    return None


def stiffener_section_keys(spec: WarehouseSpec) -> set[str]:
    """The section keys of :data:`STIFFENER_SECTION_SHAPES` ``spec`` has no members for."""
    used: set[str] = set()
    if spec.roof_stiffeners == "beam":
        used.add("stiffener")
    elif spec.roof_stiffeners == "truss":
        used |= {"stiffener_chord", "stiffener_web"}
    if spec.wall_bracing:
        if spec.wall_bracing_type == "double_x":
            used.add("wall_strut")
        elif spec.wall_bracing_type == "moment_frame":
            used.add("wall_beam")
    return set(STIFFENER_SECTION_SHAPES) - used


def stiffener_stations(spec: WarehouseSpec, stations: list[RoofStation]) -> list[int]:
    """Station indices of the stiffener lines, sorted; none without stiffeners.

    Each line goes on the purlin line nearest where it is wanted, never on a
    column line (the eaves, an interior column).
    """
    if spec.roof_stiffeners == "none":
        return []
    columns = spec.column_lines()
    out: set[int] = set()
    for nave in range(spec.n_naves):
        left, right = columns[nave], columns[nave + 1]
        middle = 0.5 * (left + right)
        half = 0.5 * (right - left)
        n = spec.stiffener_lines
        wanted = [middle] + [
            middle + side * half * k / (n + 1) for k in range(1, n + 1) for side in (-1, 1)
        ]
        for x in wanted:
            k = min(range(len(stations)), key=lambda i: (abs(stations[i].x - x), i))
            if all(abs(stations[k].x - c) > 1e-9 for c in columns):
                out.add(k)
    return sorted(out)


def roof_line_member(
    spec: WarehouseSpec, k: int, bay: int, stiffeners: set[int], eaves: tuple[int, int],
    wall_bays: set[int],
) -> tuple[str, str] | None:  # fmt: skip
    """``(group, section key)`` of the member on roof line ``k`` in ``bay`` when it is
    not a purlin (a stiffener, the beam of a moment frame), else None. It is
    framed in: no releases."""
    if k in stiffeners:
        return (
            "roof_stiffeners",
            "stiffener" if spec.roof_stiffeners == "beam" else "stiffener_chord",
        )
    if (
        spec.wall_bracing
        and spec.wall_bracing_type == "moment_frame"
        and k in eaves
        and bay in wall_bays
    ):
        return ("wall_beams", "wall_beam")
    return None


def double_x_level(spec: WarehouseSpec, girt_zs: list[float]) -> float | None:
    """Elevation of the strut of a double X: the girt line nearest mid-height, or mid-height."""
    if not spec.wall_bracing or spec.wall_bracing_type != "double_x":
        return None
    middle = 0.5 * spec.eave_height
    if girt_zs:
        return min(girt_zs, key=lambda z: (abs(z - middle), z))
    return middle


def add_wall_bracing(
    spec: WarehouseSpec,
    near: list[int],
    far: list[int],
    mid: int | None,
    add_element: Callable[..., int],
    *,
    brace_releases: Any,
    strut_needed: bool,
) -> None:
    """The bracing of one braced bay of a side wall between columns ``near`` and ``far``.

    ``near`` and ``far`` are the nodes of each column from the base up;
    ``mid`` is the index of the strut's level in them (a double X).
    """
    if spec.wall_bracing_type == "moment_frame":
        return  # the eave beam is the bracing; roof_line_member placed it
    if spec.wall_bracing_type == "double_x" and mid is not None:
        if strut_needed:
            add_element("wall_struts", near[mid], far[mid], "wall_strut", releases=brace_releases)
        panels = [(0, mid), (mid, len(near) - 1)]
    else:
        panels = [(0, len(near) - 1)]
    for lo, hi in panels:
        add_element("wall_bracing", near[lo], far[hi], "brace", releases=brace_releases)
        add_element("wall_bracing", near[hi], far[lo], "brace", releases=brace_releases)


def build_stiffener_truss(
    warehouse: Warehouse,
    roof_nodes: list[list[int]],
    stiffeners: list[int],
    add_node: Callable[[float, float, float], int],
    add_element: Callable[..., int],
    *,
    brace_releases: Any,
) -> None:
    """Bottom chord, verticals and diagonals of each stiffening truss (``build_warehouse`` calls it)."""
    spec = warehouse.spec
    if spec.roof_stiffeners != "truss":
        return
    for k in stiffeners:
        station = warehouse.stations[k]
        z = station.z - spec.stiffener_depth
        bottoms = [
            add_node(station.x, frame * spec.frame_spacing, z) for frame in range(spec.n_frames)
        ]
        for a, b in itertools.pairwise(bottoms):
            add_element("roof_stiffeners", a, b, "stiffener_chord")
        for frame, bottom in enumerate(bottoms):
            add_element(
                "stiffener_webs",
                bottom,
                roof_nodes[frame][k],
                "stiffener_web",
                releases=brace_releases,
            )
        for bay in range(spec.n_bays):
            # Alternating diagonals: a Warren web with verticals along the building.
            a, b = (
                (roof_nodes[bay][k], bottoms[bay + 1])
                if bay % 2 == 0
                else (bottoms[bay], roof_nodes[bay + 1][k])
            )
            add_element("stiffener_webs", a, b, "stiffener_web", releases=brace_releases)


__all__ = [
    "ROOF_STIFFENERS",
    "STIFFENER_SECTION_SHAPES",
    "WALL_BRACING_TYPES",
    "add_wall_bracing",
    "build_stiffener_truss",
    "check_stiffeners",
    "double_x_level",
    "roof_line_member",
    "stiffener_section_keys",
    "stiffener_stations",
]
