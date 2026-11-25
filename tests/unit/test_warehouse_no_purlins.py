"""A warehouse whose purlins or girts are not modelled: the roof on the rafters, the walls on the columns."""

from __future__ import annotations

import math

import numpy as np
import pytest

from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    Warehouse,
    WarehouseSnow,
    WarehouseSpec,
    WarehouseWind,
    build_warehouse,
    roof_pressure_loads,
    roof_weights,
    snow_loads,
    warehouse_snow_cases,
    warehouse_wind_cases,
    wind_loads,
)

SECTIONS = {
    "column": 1,
    "rafter": 2,
    "purlin": 3,
    "girt": 4,
    "brace": 5,
    "overhang": 6,
    "end_column": 7,
}
SI = UnitSystem.SI_M_N
LENGTH = 3 * 6.0


def _build(**fields) -> Warehouse:  # type: ignore[no-untyped-def]
    values = {"span": 20.0, "eave_height": 6.0, "frame_spacing": 6.0, "n_frames": 4, **fields}
    return build_warehouse(WarehouseSpec(**values), SECTIONS, first_node_id=1, first_element_id=1)


def _resultant(warehouse: Warehouse, loads: list) -> np.ndarray:  # type: ignore[type-arg]
    nodes = {n.id: np.asarray(n.coords) for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    total = np.zeros(3)
    for load in loads:
        element = elements[load.element_id]
        a, b = nodes[element.nodes[0]], nodes[element.nodes[1]]
        axes = frame_local_axes(3, a, b, element.local_axis_angle)
        assert axes is not None
        vector = load.wx * axes[0] + load.wy * axes[1] + load.wz * axes[2]
        total += vector * float(np.linalg.norm(b - a))
    return total


def test_without_purlins_only_struts_tie_the_frames() -> None:
    warehouse = _build(model_purlins=False, purlin_spacing=1.0)
    assert warehouse.members["purlins"] == [] and not warehouse.purlin_station
    struts = warehouse.members["roof_struts"]
    lines = set(warehouse.strut_station.values())
    xs = sorted(warehouse.stations[k].x for k in lines)
    # The eaves and the ridge, and where the X of the roof bracing end.
    assert xs[0] == 0.0 and xs[-1] == 20.0 and 10.0 in xs
    assert len(lines) < len(warehouse.stations)
    assert len(struts) == len(lines) * 3  # every bay
    by_id = {e.id: e for e in warehouse.elements}
    assert {by_id[i].section_id for i in struts} == {3}
    assert not any(by_id[i].auto_mesh for i in struts)
    braced = {n for i in warehouse.members["roof_bracing"] for n in by_id[i].nodes}
    tied = {n for i in struts for n in by_id[i].nodes}
    assert braced <= tied  # every node of a roof X is on a strut


def test_without_purlins_the_rafters_carry_the_roof_loads() -> None:
    plain = _build(purlin_spacing=1.0, overhang=1.5)
    bare = _build(purlin_spacing=1.0, overhang=1.5, model_purlins=False)
    assert not bare.overhang_purlins
    rafters = {i for frame in bare.rafter_elements for i in frame} | set(bare.members["overhangs"])
    for projected in (True, False):
        loads = roof_pressure_loads(bare, 500.0, projected=projected)
        assert {load.element_id for load in loads} == rafters
        assert _resultant(bare, loads) == pytest.approx(
            _resultant(plain, roof_pressure_loads(plain, 500.0, projected=projected))
        )
    live = _resultant(bare, roof_pressure_loads(bare, 500.0, projected=True))
    assert live[2] == pytest.approx(-500.0 * 23.0 * LENGTH)
    weights = roof_weights(bare, 100.0, projected=True)
    assert sum(weights.values()) == pytest.approx(100.0 * 23.0 * LENGTH)
    # An end frame carries half a bay, a middle one a whole bay.
    end = bare.rafter_elements[0][0]
    middle = bare.rafter_elements[1][0]
    by_load = {load.element_id: load for load in roof_pressure_loads(bare, 1.0, projected=False)}
    assert math.hypot(by_load[middle].wx, by_load[middle].wy, by_load[middle].wz) == pytest.approx(
        6.0
    )
    assert math.hypot(by_load[end].wx, by_load[end].wy, by_load[end].wz) == pytest.approx(3.0)


def test_without_purlins_snow_and_wind_add_up_to_the_same_loads() -> None:
    plain = _build(purlin_spacing=1.0, girt_spacing=1.5)
    bare = _build(purlin_spacing=1.0, girt_spacing=1.5, model_purlins=False)
    for case in warehouse_snow_cases(plain.spec, WarehouseSnow(method="ash", ground=1000.0), SI):
        assert _resultant(bare, snow_loads(bare, case)) == pytest.approx(
            _resultant(plain, snow_loads(plain, case))
        )
    for case in warehouse_wind_cases(plain.spec, WarehouseWind(), SI):
        mine = _resultant(bare, wind_loads(bare, case, SI))
        theirs = _resultant(plain, wind_loads(plain, case, SI))
        assert mine == pytest.approx(theirs, rel=1e-9, abs=1e-6), case.name


def test_without_girts_the_walls_are_bare_and_the_wind_goes_to_the_columns() -> None:
    bare = _build(girt_spacing=1.5, model_girts=False, end_wall_column_spacing=5.0)
    none = _build(girt_spacing=0.0, end_wall_column_spacing=5.0)
    assert bare.members["girts"] == []
    assert len(bare.nodes) == len(none.nodes) and len(bare.elements) == len(none.elements)
    case = next(c for c in warehouse_wind_cases(bare.spec, WarehouseWind(), SI))
    columns = {i for ids in bare.wall_columns.values() for i, _ in ids}
    loaded = {load.element_id for load in wind_loads(bare, case, SI)}
    assert columns & loaded
