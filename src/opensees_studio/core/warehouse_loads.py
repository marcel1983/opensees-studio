"""The loads of a generated warehouse on the members the cladding hangs from.

The roof loads (the weight of the cladding, the live load, snow and ash, the
mass of the roof) go on the purlins, each the strip of roof half way to its
neighbours, and so do the eave overhangs' (:mod:`opensees_studio.core.warehouse_overhang`).
The wind goes on the purlins, the girts, the columns and the end rafters.
Split out of :mod:`opensees_studio.core.warehouse`, which re-exports them.

No Qt, no OpenSees.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np

from opensees_studio.core.frames import GRID_TOLERANCE
from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.units import UnitSystem, length_scale
from opensees_studio.core.warehouse_overhang import overhang_strips, strip_widths

if TYPE_CHECKING:
    from opensees_studio.core.geometry.elements import ElasticBeamColumn
    from opensees_studio.core.geometry.node import Node
    from opensees_studio.core.snow import SnowCase
    from opensees_studio.core.warehouse import Warehouse
    from opensees_studio.core.wind import WindCase


def _components(vector: Any) -> tuple[float, ...]:
    from opensees_studio.core.warehouse import _components as components

    return components(vector)


def _gravity_components(nodes: Mapping[int, Node], element: ElasticBeamColumn) -> np.ndarray:
    """Local ``(x, y, z)`` components of a unit downward (-Z) load on ``element``."""
    axes = frame_local_axes(
        3,
        nodes[element.nodes[0]].coords,
        nodes[element.nodes[1]].coords,
        element.local_axis_angle,
    )
    assert axes is not None  # a warehouse has no zero-length member
    return np.array([-float(axis[2]) for axis in axes])


def _purlin_widths(warehouse: Warehouse, *, projected: bool) -> dict[int, float]:
    """Purlin element id -> width of roof it carries, the overhangs' included."""
    widths: dict[int, float] = {}
    for element_id, k in warehouse.purlin_station.items():
        station = warehouse.stations[k]
        widths[element_id] = station.tributary_plan if projected else station.tributary_slope
    for element_id, width in strip_widths(warehouse, projected=projected).items():
        widths[element_id] = widths.get(element_id, 0.0) + width
    return widths


def roof_pressure_loads(warehouse: Warehouse, pressure: float, *, projected: bool) -> list[Any]:
    """A downward load per roof area as uniform loads on the purlins.

    ``projected`` reads ``pressure`` per area of horizontal projection (a live
    load); otherwise per area of roof surface (the weight of the cladding).
    """
    from opensees_studio.core.loads import UniformElementLoad

    if pressure == 0.0:
        return []
    nodes = {n.id: n for n in warehouse.nodes}
    purlins = {e.id: e for e in warehouse.elements}
    loads: list[Any] = []
    for element_id, width in _purlin_widths(warehouse, projected=projected).items():
        _wx, wy, wz = _components(
            _gravity_components(nodes, purlins[element_id]) * pressure * width
        )
        loads.append(UniformElementLoad(element_id=element_id, wy=wy, wz=wz))
    return loads


def midspan_point_loads(warehouse: Warehouse, force: float) -> tuple[list[Any], list[Any]]:
    """A downward force at mid-span of every nave of every frame.

    Returns ``(nodal loads, point element loads)``: the force goes on the node
    when a purlin line falls at mid-span (the ridge of a single-nave gable) and
    inside the rafter element otherwise.
    """
    from opensees_studio.core.loads import NodalLoad, PointElementLoad

    if force == 0.0:
        return [], []
    spec = warehouse.spec
    stations = warehouse.stations
    nodes = {n.id: n for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    nodal: list[Any] = []
    inside: list[Any] = []
    for rafters in warehouse.rafter_elements:
        for nave in range(spec.n_naves):
            x = (nave + 0.5) * spec.span
            at = next((k for k, s in enumerate(stations) if abs(s.x - x) <= GRID_TOLERANCE), None)
            if at is not None:
                # Either element at the station shares the node: its end there.
                element = elements[rafters[min(at, len(rafters) - 1)]]
                node_id = element.nodes[0] if at < len(rafters) else element.nodes[1]
                nodal.append(NodalLoad(node_id=node_id, forces=(0.0, 0.0, -force, 0.0, 0.0, 0.0)))
                continue
            k = max(i for i, s in enumerate(stations) if s.x < x)
            element = elements[rafters[k]]
            px, py, pz = _components(_gravity_components(nodes, element) * force)
            inside.append(
                PointElementLoad(
                    element_id=element.id,
                    px=px,
                    py=py,
                    pz=pz,
                    x=(x - stations[k].x) / (stations[k + 1].x - stations[k].x),
                )
            )
    return nodal, inside


def wind_loads(warehouse: Warehouse, case: WindCase, units: UnitSystem) -> list[Any]:
    """One wind case as uniform loads on the members the cladding hangs from.

    * Roof: each purlin takes half the strip to each neighbour, normal to that
      strip of roof.
    * A wall with girts: each girt takes half the strip to the line below and
      above; the top half strip goes to the eave purlin (side walls) or to the
      rafter (end walls), the bottom half strip into the ground.
    * A wall without girts: each column takes the wall half way to its
      neighbours, over its whole height.

    A positive pressure of ``case`` pushes the surface inwards. The loads are in
    each element's local axes and in the project's units; an element loaded
    from two surfaces (a corner column, the ridge purlin) gets one load.
    """
    from opensees_studio.core.loads import UniformElementLoad

    spec = warehouse.spec
    stations = warehouse.stations
    profile = spec.profile
    metres = length_scale(units, UnitSystem.SI_M_N)
    from opensees_studio.core.warehouse import end_wall_layout, pressure_from_kpa

    pascal = pressure_from_kpa(1e-3, units)
    origin = np.array(spec.origin, dtype=float)
    nodes = {n.id: n for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    forces: dict[int, np.ndarray] = {}

    def local(node_id: int) -> np.ndarray:
        out: np.ndarray = np.array(nodes[node_id].coords, dtype=float) - origin
        return out

    def add(element_id: int, pressure: float, width: float, outward: np.ndarray) -> None:
        """``pressure`` (N/m²) over ``width`` of surface per length of the element."""
        forces[element_id] = forces.get(element_id, np.zeros(3)) - (
            pressure * pascal * width * outward
        )

    def mean(pressure: Any, a: float, b: float) -> float:
        return float(pressure.mean(a * metres, b * metres))

    def on_wall(wall: str, a: float, b: float, lo: float, hi: float) -> float:
        """Mean pressure on ``wall`` from ``a`` to ``b`` along it, ``lo`` to ``hi`` in height."""
        zones = case.wall_zones.get(wall)
        if zones is None:
            return mean(case.walls[wall], lo, hi)
        return float(zones.mean(a * metres, b * metres, lo * metres, hi * metres))

    # Roof: half strips either side of each purlin line.
    last = len(stations) - 1
    for element_id, k in warehouse.purlin_station.items():
        here = stations[k]
        ya, yb = (local(n)[1] for n in elements[element_id].nodes)
        for other in (k - 1, k + 1):
            if not 0 <= other <= last:
                continue
            dx, dz = stations[other].x - here.x, stations[other].z - here.z
            run = math.hypot(dx, dz)
            outward = np.array([-dz, 0.0, dx]) / run * (1.0 if dx > 0.0 else -1.0)
            middle = here.x + dx / 2.0
            load = case.roof_load_at((here.x + middle) / 2.0 * metres)
            if load.zones is not None:
                value = float(
                    load.zones.mean(here.x * metres, middle * metres, ya * metres, yb * metres)
                )
            elif load.axis == "x":
                value = mean(load.profile, here.x, middle)
            else:
                value = mean(load.profile, ya, yb)
            add(element_id, value, run / 2.0, outward)

    # Overhangs: the roof's pressure at the eave on top, the wall's underneath.
    for strip in overhang_strips(warehouse):
        ya, yb = (local(n)[1] for n in elements[strip.element_id].nodes)
        x = strip.eave_x
        load = case.roof_load_at(x * metres)
        if load.zones is not None:
            top = float(load.zones.mean(x * metres, x * metres, ya * metres, yb * metres))
        elif load.axis == "x":
            top = mean(load.profile, x, x)
        else:
            top = mean(load.profile, ya, yb)
        eave = stations[0 if strip.wall == "x0" else last].z
        under = on_wall(strip.wall, ya, yb, eave, eave)
        add(strip.element_id, top - under, strip.slope_width, np.array(strip.normal))

    # Side walls.
    girt_zs = spec.girt_heights()
    for wall, station, outward in (
        ("x0", 0, np.array([-1.0, 0.0, 0.0])),
        ("x1", last, np.array([1.0, 0.0, 0.0])),
    ):
        levels = [0.0, *girt_zs, stations[station].z]
        if girt_zs:
            for element_id, (girt_wall, _bay, z) in warehouse.wall_girts.items():
                if girt_wall != wall:
                    continue
                k = levels.index(z)
                lo, hi = (levels[k - 1] + z) / 2.0, (z + levels[k + 1]) / 2.0
                ya, yb = (local(n)[1] for n in elements[element_id].nodes)
                add(element_id, on_wall(wall, ya, yb, lo, hi), hi - lo, outward)
            lo, hi = (levels[-2] + levels[-1]) / 2.0, levels[-1]
            for element_id, k in warehouse.purlin_station.items():
                if k == station:
                    ya, yb = (local(n)[1] for n in elements[element_id].nodes)
                    add(element_id, on_wall(wall, ya, yb, lo, hi), hi - lo, outward)
        else:
            for element_id, frame in warehouse.wall_columns[wall]:
                y = frame * spec.frame_spacing
                ya = max(0.0, y - spec.frame_spacing / 2.0)
                yb = min(spec.length, y + spec.frame_spacing / 2.0)
                za, zb = (local(n)[2] for n in elements[element_id].nodes)
                add(element_id, on_wall(wall, ya, yb, za, zb), yb - ya, outward)

    # End walls.
    end_wall = end_wall_layout(spec, stations)
    framed = any(end_wall.levels)
    for wall, frame, outward in (
        ("y0", 0, np.array([0.0, -1.0, 0.0])),
        ("y1", spec.n_frames - 1, np.array([0.0, 1.0, 0.0])),
    ):
        if not framed:
            for element_id, vertical in warehouse.wall_columns[wall]:
                x = end_wall.xs[vertical]
                left = (end_wall.xs[vertical - 1] + x) / 2.0 if vertical else x
                right = (
                    (x + end_wall.xs[vertical + 1]) / 2.0 if vertical < len(end_wall.xs) - 1 else x
                )
                # The wall up to the roof line, spread over the column's height.
                width = end_wall.roof_area(left, right, profile) / end_wall.tops[vertical]
                za, zb = (local(n)[2] for n in elements[element_id].nodes)
                add(element_id, on_wall(wall, left, right, za, zb), width, outward)
            continue
        top_girt: dict[int, float] = {}
        for vertical in range(len(end_wall.xs) - 1):
            a, b = end_wall.xs[vertical], end_wall.xs[vertical + 1]
            roof = end_wall.roof_area(a, b, profile) / (b - a)
            levels = [0.0, *end_wall.panel_levels(vertical), roof]
            top_girt[vertical] = levels[-2]
            for element_id, (girt_wall, panel, z) in warehouse.wall_girts.items():
                if girt_wall != wall or panel != vertical:
                    continue
                k = levels.index(z)
                lo, hi = (levels[k - 1] + z) / 2.0, (z + levels[k + 1]) / 2.0
                add(element_id, on_wall(wall, a, b, lo, hi), hi - lo, outward)
        # The strip under the roof line hangs from the rafter of the end frame.
        for k, element_id in enumerate(warehouse.rafter_elements[frame]):
            s0, s1 = stations[k], stations[k + 1]
            middle = (s0.x + s1.x) / 2.0
            vertical = max(v for v, x in enumerate(end_wall.xs[:-1]) if x <= middle)
            roof = (s0.z + s1.z) / 2.0
            height = (roof - top_girt[vertical]) / 2.0
            width = height * abs(s1.x - s0.x) / math.hypot(s1.x - s0.x, s1.z - s0.z)
            add(element_id, on_wall(wall, s0.x, s1.x, roof - height, roof), width, outward)

    loads: list[Any] = []
    for element_id in sorted(forces):
        element = elements[element_id]
        axes = frame_local_axes(
            3,
            nodes[element.nodes[0]].coords,
            nodes[element.nodes[1]].coords,
            element.local_axis_angle,
        )
        assert axes is not None  # a warehouse has no zero-length member
        if not forces[element_id].any():
            continue
        wx, wy, wz = _components(axis @ forces[element_id] for axis in axes)
        loads.append(UniformElementLoad(element_id=element_id, wx=wx, wy=wy, wz=wz))
    return loads


def roof_weights(warehouse: Warehouse, pressure: float, *, projected: bool) -> dict[int, float]:
    """Node id -> weight of a roof load per area, half of each purlin's strip per end."""
    if pressure == 0.0:
        return {}
    nodes = {n.id: np.asarray(n.coords, dtype=float) for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    out: dict[int, float] = {}
    for element_id, width in _purlin_widths(warehouse, projected=projected).items():
        i, j = elements[element_id].nodes
        half = 0.5 * pressure * width * float(np.linalg.norm(nodes[j] - nodes[i]))
        out[i] = out.get(i, 0.0) + half
        out[j] = out.get(j, 0.0) + half
    return out


def snow_loads(warehouse: Warehouse, case: SnowCase) -> list[Any]:
    """A snow or ash case as uniform loads on the purlins.

    Each purlin takes what falls on the half strip of plan to either
    neighbour: the case's mean pressure over it times its width, downwards.
    """
    from opensees_studio.core.loads import UniformElementLoad

    nodes = {n.id: n for n in warehouse.nodes}
    purlins = {e.id: e for e in warehouse.elements}
    stations = warehouse.stations
    last = len(stations) - 1
    loads_per_length: dict[int, float] = {}
    for element_id, k in warehouse.purlin_station.items():
        here = stations[k]
        per_length = 0.0
        for other in (k - 1, k + 1):
            if not 0 <= other <= last:
                continue
            middle = 0.5 * (here.x + stations[other].x)
            per_length += case.mean(here.x, middle) * abs(middle - here.x)
        loads_per_length[element_id] = per_length
    # An overhang takes the load at its eave.
    for strip in overhang_strips(warehouse):
        load = case.mean(strip.eave_x, strip.eave_x) * strip.plan_width
        loads_per_length[strip.element_id] = loads_per_length.get(strip.element_id, 0.0) + load
    loads: list[Any] = []
    for element_id, per_length in loads_per_length.items():
        if per_length == 0.0:
            continue
        _wx, wy, wz = _components(_gravity_components(nodes, purlins[element_id]) * per_length)
        loads.append(UniformElementLoad(element_id=element_id, wy=wy, wz=wz))
    return loads


__all__ = [
    "midspan_point_loads",
    "roof_pressure_loads",
    "roof_weights",
    "snow_loads",
    "wind_loads",
]
