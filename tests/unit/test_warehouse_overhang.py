"""The eave overhangs (aleros) of a generated warehouse: geometry, ids, loads."""

from __future__ import annotations

import math

import numpy as np
import pytest

from opensees_studio.core.frames import RoofType
from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    Warehouse,
    WarehouseError,
    WarehouseSpec,
    WarehouseWind,
    build_warehouse,
    member_design_overrides,
    roof_pressure_loads,
    roof_weights,
    warehouse_wind_cases,
    wind_loads,
)

SECTIONS = {"column": 1, "rafter": 2, "purlin": 3, "girt": 4, "brace": 5, "overhang": 6}
SI = UnitSystem.SI_M_N


def _spec(**fields):  # type: ignore[no-untyped-def]
    values = {"span": 20.0, "eave_height": 6.0, "frame_spacing": 6.0, "n_frames": 4, **fields}
    return WarehouseSpec(**values)


def _build(**fields) -> Warehouse:  # type: ignore[no-untyped-def]
    return build_warehouse(_spec(**fields), SECTIONS, first_node_id=1, first_element_id=1)


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


@pytest.mark.parametrize("fields", [{"overhang": -1.0}, {"overhang_sides": "y0"}])
def test_an_overhang_that_does_not_exist_is_refused(fields: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(WarehouseError):
        _spec(**fields)


def test_the_overhang_goes_on_from_the_eave_along_the_slope_of_the_roof() -> None:
    warehouse = _build(overhang=1.2, purlin_spacing=1.0, slope=0.10)
    nodes = {n.id: n for n in warehouse.nodes}
    by_id = {e.id: e for e in warehouse.elements}
    overhangs = warehouse.members["overhangs"]
    assert len(overhangs) == 2 * 4 * 2  # two sides, four frames, two pieces (1.2 m > 1 m)
    assert {by_id[i].section_id for i in overhangs} == {6}
    xs = sorted({nodes[n].coords[0] for i in overhangs for n in by_id[i].nodes})
    assert xs == pytest.approx([-1.2, -0.6, 0.0, 20.0, 20.6, 21.2])
    tip = next(n for n in warehouse.nodes if n.coords[0] == pytest.approx(-1.2))
    assert tip.coords[2] == pytest.approx(6.0 - 0.12)  # the slope goes on downwards
    # Purlins at each line of the overhang, frame to frame, in the purlins group.
    on_overhang = list(warehouse.overhang_purlins)
    assert len(on_overhang) == 2 * 2 * 3
    assert set(on_overhang) <= set(warehouse.members["purlins"])
    assert not any(by_id[i].auto_mesh for i in on_overhang)
    # The cantilever is held only at the eave: its whole length is unbraced.
    length = math.hypot(1.2, 0.12)
    assert {round(warehouse.unbraced[i], 9) for i in overhangs} == {round(length, 9)}
    overrides = {o.element_id: o for o in member_design_overrides(warehouse)}
    assert overrides[overhangs[0]].length_ltb == pytest.approx(length)


def test_a_mono_pitch_overhang_on_the_high_side_rises_and_one_side_can_be_chosen() -> None:
    warehouse = _build(roof=RoofType.MONO_PITCH, overhang=1.0, overhang_sides="x1")
    nodes = {n.id: n for n in warehouse.nodes}
    tips = [n for n in nodes.values() if n.coords[0] == pytest.approx(21.0)]
    assert tips and all(n.coords[2] == pytest.approx(6.0 + 0.10 * 21.0) for n in tips)
    assert not any(n.coords[0] < 0.0 for n in nodes.values())


def test_a_warehouse_without_overhangs_keeps_its_ids() -> None:
    plain = _build()
    with_overhangs = _build(overhang=1.0)
    n_nodes, n_elements = len(plain.nodes), len(plain.elements)
    assert [n.model_dump() for n in with_overhangs.nodes[:n_nodes]] == [
        n.model_dump() for n in plain.nodes
    ]
    assert [e.model_dump() for e in with_overhangs.elements[:n_elements]] == [
        e.model_dump() for e in plain.elements
    ]


def test_the_roof_loads_reach_the_tip_of_the_overhangs() -> None:
    spec_fields = {"overhang": 1.5, "purlin_spacing": 1.0}
    warehouse = _build(**spec_fields)
    length = 3 * 6.0
    live = _resultant(warehouse, roof_pressure_loads(warehouse, 500.0, projected=True))
    assert live[2] == pytest.approx(-500.0 * (20.0 + 2 * 1.5) * length)
    assert live[0] == pytest.approx(0.0, abs=1e-6)
    plain = _build(purlin_spacing=1.0)
    surface = 2 * math.hypot(1.5, 0.15) + 2 * math.hypot(10.0, 1.0)
    dead = _resultant(warehouse, roof_pressure_loads(warehouse, 100.0, projected=False))
    assert dead[2] == pytest.approx(-100.0 * surface * length)
    # The eave purlin takes half the first space of the overhang besides its roof.
    assert sum(roof_weights(warehouse, 100.0, projected=True).values()) == pytest.approx(
        100.0 * 23.0 * length
    )
    assert sum(roof_weights(plain, 100.0, projected=True).values()) == pytest.approx(
        100.0 * 20.0 * length
    )


def test_the_wind_lifts_the_windward_overhang_from_underneath() -> None:
    warehouse = _build(overhang=1.0, purlin_spacing=1.5, girt_spacing=1.5)
    plain = _build(purlin_spacing=1.5, girt_spacing=1.5)
    case = next(
        c for c in warehouse_wind_cases(warehouse.spec, WarehouseWind(), SI) if c.name == "WIND +X"
    )
    on_tip = [i for i, (wall, k) in warehouse.overhang_purlins.items() if (wall, k) == ("x0", 0)]
    loads = {load.element_id: load for load in wind_loads(warehouse, case, SI)}
    lift = _resultant(warehouse, [loads[i] for i in on_tip])
    # Windward: the wall's pressure under it adds to the roof's suction on top.
    roof_top = case.roof_load_at(0.0).profile.mean(0.0, 0.0)
    wall_below = case.walls["x0"].at(6.0)
    assert wall_below > 0.0
    # One purlin line at the tip, carrying half the overhang; a pressure pushes down.
    expected = -(roof_top - wall_below) * 0.5 * math.hypot(1.0, 0.1) * 3 * 6.0
    assert lift[2] == pytest.approx(expected * math.cos(math.atan(0.1)), rel=1e-6)
    assert lift[2] > 0.0
    # The loads of the roof between the walls do not change.
    before = {load.element_id: load for load in wind_loads(plain, case, SI)}
    for element_id, load in before.items():
        if element_id in plain.purlin_station and plain.purlin_station[element_id] not in (
            0,
            len(plain.stations) - 1,
        ):
            assert loads[element_id] == load
