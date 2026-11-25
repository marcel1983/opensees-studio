"""The warehouse's end walls and its wind: columns, girts, loads on the members, the plan."""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.frames import RoofType
from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.project import Project
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    POST_TOP_RELEASES,
    SECONDARY_RELEASES,
    Warehouse,
    WarehouseError,
    WarehouseLoads,
    WarehouseSeismic,
    WarehouseSnow,
    WarehouseSpec,
    WarehouseWind,
    build_warehouse,
    building_shape,
    end_wall_layout,
    member_design_overrides,
    plan_warehouse,
    portable,
    warehouse_wind_cases,
    wind_loads,
)
from opensees_studio.core.wind import (
    KGF,
    asce7_velocity_pressure,
    en1991_peak_pressure,
    en1991_wall_cp,
)

SECTIONS = {"column": 1, "rafter": 2, "purlin": 3, "girt": 4, "brace": 5, "end_column": 6}
SI = UnitSystem.SI_M_N
#: RNC-07, zone 2, Group B, R2, flat terrain: the pressure of Cp = 1 (97 kg/m²).
Q = 0.0479 * 45.0**2 * KGF


def _spec(**fields):  # type: ignore[no-untyped-def]
    values = {"span": 20.0, "eave_height": 6.0, "frame_spacing": 6.0, "n_frames": 6, **fields}
    return WarehouseSpec(**values)


def _build(**fields) -> Warehouse:  # type: ignore[no-untyped-def]
    return build_warehouse(_spec(**fields), SECTIONS, first_node_id=1, first_element_id=1)


def _project(units: UnitSystem = SI) -> Project:
    project = Project(ndm=3, ndf=6)
    project.meta.units = units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)
    return project


def _resultant(warehouse: Warehouse, loads: list) -> np.ndarray:  # type: ignore[type-arg]
    """Total force of uniform element loads, in global axes."""
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


def _case(warehouse: Warehouse, name: str, wind: WarehouseWind | None = None):  # type: ignore[no-untyped-def]
    cases = warehouse_wind_cases(warehouse.spec, wind or WarehouseWind(), SI)
    return next(c for c in cases if c.name == name)


# ─────────────────────────── the end walls ───────────────────────────
def test_end_wall_columns_stand_under_purlin_lines() -> None:
    spec = _spec(slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0)
    layout = end_wall_layout(spec)
    assert layout.xs == pytest.approx((0.0, 5.71428571, 10.0, 14.28571429, 20.0))
    assert sorted(layout.posts) == [1, 2, 3]  # the corners are the frame's own columns
    assert layout.tops == pytest.approx((6.0, 6.571428571, 7.0, 6.571428571, 6.0))
    # The corner columns carry the side wall's girt lines; the others what reaches them.
    assert layout.levels[0] == layout.levels[-1] == (1.5, 3.0, 4.5)
    assert layout.levels[1] == (1.5, 3.0, 4.5, 6.0)
    assert layout.levels[2] == (1.5, 3.0, 4.5, 6.0)
    assert layout.panel_levels(0) == [1.5, 3.0, 4.5] and layout.panel_levels(1) == [
        1.5, 3.0, 4.5, 6.0,
    ]  # fmt: skip
    # The wall up to the roof line, between any two abscissas.
    assert layout.roof_area(0.0, 20.0, spec.profile) == pytest.approx(20 * 6.0 + 20 * 1.0 / 2)
    assert layout.roof_area(8.0, 12.0, spec.profile) == pytest.approx(4 * 6.8 + 2 * 2 * 0.2 / 2)


def test_no_spacing_no_end_wall_columns_and_the_same_warehouse_as_before() -> None:
    plain = _build(girt_spacing=1.5)
    assert plain.members["end_columns"] == []
    assert not any(wall in ("y0", "y1") for wall, _p, _z in plain.wall_girts.values())
    framed = _build(girt_spacing=1.5, end_wall_column_spacing=5.0)
    # The end walls come last: everything else keeps its id and its nodes.
    count = len(plain.elements)
    assert [(e.id, e.nodes) for e in framed.elements[:count]] == [
        (e.id, e.nodes) for e in plain.elements
    ]
    assert [n.coords for n in framed.nodes[: len(plain.nodes)]] == [n.coords for n in plain.nodes]
    # Without the section a warehouse with end wall columns cannot be built.
    five = {k: v for k, v in SECTIONS.items() if k != "end_column"}
    build_warehouse(_spec(), five, first_node_id=1, first_element_id=1)
    with pytest.raises(WarehouseError, match="end_column"):
        build_warehouse(
            _spec(end_wall_column_spacing=5.0), five, first_node_id=1, first_element_id=1
        )
    with pytest.raises(WarehouseError):
        _spec(end_wall_column_spacing=-1.0)


def test_an_end_wall_column_is_pinned_and_spans_against_the_wind() -> None:
    warehouse = _build(slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0)
    nodes = {n.id: n for n in warehouse.nodes}
    by_id = {e.id: e for e in warehouse.elements}
    posts = [by_id[i] for i in warehouse.members["end_columns"]]
    assert len(posts) == 2 * 3 * 5  # two walls, three columns, split at four girt lines
    assert {e.section_id for e in posts} == {6}
    assert {e.local_axis_angle for e in posts} == {90.0}
    tops = [e for e in posts if e.releases == POST_TOP_RELEASES]
    assert len(tops) == 6
    assert all(nodes[e.nodes[1]].coords[2] > 6.0 for e in tops)  # the element under the rafter
    for element in posts:
        a, b = nodes[element.nodes[0]].coords, nodes[element.nodes[1]].coords
        assert a[0] == b[0] and a[1] == b[1] and a[1] in (0.0, 30.0)  # plumb, in an end wall
        axes = frame_local_axes(3, a, b, element.local_axis_angle)
        assert axes is not None and abs(axes[2][1]) == pytest.approx(1.0)  # the web along Y
    bases = [nodes[e.nodes[0]] for e in posts if nodes[e.nodes[0]].coords[2] == 0.0]
    assert len(bases) == 6
    assert {b.restraint for b in bases} == {(True, True, True, False, False, False)}
    assert {b.id for b in bases} <= set(warehouse.base_node_ids)
    # The top is a rafter node that a purlin line passes through.
    purlin_nodes = {n for i in warehouse.members["purlins"] for n in by_id[i].nodes}
    assert {e.nodes[1] for e in tops} <= purlin_nodes


def test_end_wall_girts_run_between_neighbouring_columns() -> None:
    warehouse = _build(slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0)
    nodes = {n.id: n for n in warehouse.nodes}
    by_id = {e.id: e for e in warehouse.elements}
    end = {i: v for i, v in warehouse.wall_girts.items() if v[0] in ("y0", "y1")}
    # Per wall: three lines in the two outer panels, four in the two inner ones.
    assert len(end) == 2 * (3 + 4 + 4 + 3)
    assert set(end) <= set(warehouse.members["girts"])
    for element_id, (wall, panel, z) in end.items():
        element = by_id[element_id]
        a, b = nodes[element.nodes[0]].coords, nodes[element.nodes[1]].coords
        assert a[2] == b[2] == z and a[1] == b[1] == (0.0 if wall == "y0" else 30.0)
        layout = end_wall_layout(warehouse.spec)
        assert (a[0], b[0]) == pytest.approx((layout.xs[panel], layout.xs[panel + 1]))
        assert element.releases == SECONDARY_RELEASES
        axes = frame_local_axes(3, a, b, element.local_axis_angle)
        assert axes is not None and abs(axes[2][1]) == pytest.approx(1.0)  # the web flat
    # No girts without a spacing: the end wall columns then stand alone.
    bare = _build(slope=0.10, end_wall_column_spacing=5.0)
    assert bare.members["girts"] == [] and len(bare.members["end_columns"]) == 6


def test_the_interior_columns_of_a_wide_end_wall_carry_its_girts() -> None:
    warehouse = _build(
        n_naves=2, span=12.0, roof=RoofType.MONO_PITCH, slope=0.15,
        girt_spacing=1.5, end_wall_column_spacing=6.0,
    )  # fmt: skip
    layout = end_wall_layout(warehouse.spec)
    assert len(layout.xs) == 5 and sorted(layout.posts) == [1, 3]
    assert layout.tops[-1] == pytest.approx(6.0 + 0.15 * 24.0)
    nodes = {n.id: n for n in warehouse.nodes}
    by_id = {e.id: e for e in warehouse.elements}
    middle = [
        by_id[i] for i in warehouse.members["columns"] if nodes[by_id[i].nodes[0]].coords[0] == 12.0
    ]
    per_frame: dict[float, int] = {}
    for element in middle:
        y = nodes[element.nodes[0]].coords[1]
        per_frame[y] = per_frame.get(y, 0) + 1
    # Split at the girt lines in the two end frames only.
    assert per_frame[0.0] == per_frame[30.0] == len(layout.levels[2]) + 1 > 1
    assert {per_frame[y] for y in (6.0, 12.0, 18.0, 24.0)} == {1}
    # The high wall has no girt above the last line that reaches both of its columns.
    assert max(layout.panel_levels(3)) <= layout.tops[3]


def test_a_girt_braces_an_end_wall_column_only_with_a_stabilising_angle() -> None:
    none = _build(slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0)
    every = _build(
        slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0, column_fly_brace_every=2
    )
    ridge_post = lambda w: [  # noqa: E731
        w.unbraced[i] for i, v in w.wall_columns["y0"] if v == 2
    ]
    assert ridge_post(none) == pytest.approx([7.0] * 5)  # unbraced over its whole height
    assert ridge_post(every) == pytest.approx([3.0, 3.0, 3.0, 3.0, 1.0])
    overrides = {m.element_id: m for m in member_design_overrides(every)}
    for element_id, _vertical in every.wall_columns["y0"]:
        assert overrides[element_id].length_ltb == pytest.approx(every.unbraced[element_id])


# ─────────────────────────── wind on the members ───────────────────────────
def test_wind_across_a_bare_warehouse_goes_to_the_purlins_and_the_columns() -> None:
    warehouse = _build(slope=0.10)
    loads = wind_loads(warehouse, _case(warehouse, "WIND +X"), SI)
    slope_area = math.hypot(10.0, 1.0) * 30.0
    sine, cosine = 1.0 / math.hypot(10.0, 1.0), 10.0 / math.hypot(10.0, 1.0)
    walls = (0.8 + 0.4) * Q * 6.0 * 30.0
    roof_x = (-0.8 + 0.7) * Q * slope_area * sine  # the suctions pull against each other
    roof_z = (0.8 + 0.7) * Q * slope_area * cosine
    assert _resultant(warehouse, loads) == pytest.approx([walls + roof_x, 0.0, roof_z], abs=1e-6)
    # Every purlin and every side column is loaded; nothing else.
    loaded = {load.element_id for load in loads}
    side_columns = {i for wall in ("x0", "x1") for i, _f in warehouse.wall_columns[wall]}
    assert loaded == set(warehouse.purlin_station) | side_columns
    by_id = {load.element_id: load for load in loads}
    # An interior frame's column takes a whole bay, an end frame's half of one.
    first, second = (i for i, f in warehouse.wall_columns["x0"] if f in (0, 1))
    assert abs(by_id[second].wz) == pytest.approx(0.8 * Q * 6.0)
    assert abs(by_id[first].wz) == pytest.approx(0.8 * Q * 3.0)
    assert by_id[second].wy == pytest.approx(0.0, abs=1e-9)  # along the web, across the wall


def test_a_purlin_is_loaded_normal_to_its_roof() -> None:
    warehouse = _build(slope=0.10)
    case = _case(warehouse, "WIND +Y")  # -0.8 on both slopes
    loads = {load.element_id: load for load in wind_loads(warehouse, case, SI)}
    stations = warehouse.stations
    ridge = next(k for k, s in enumerate(stations) if s.x == 10.0)
    for element_id, k in warehouse.purlin_station.items():
        load = loads[element_id]
        assert load.wx == pytest.approx(0.0, abs=1e-9)
        if k == ridge:
            # The web is plumb: the two slopes' horizontal pulls cancel.
            assert load.wy == pytest.approx(0.0, abs=1e-9)
            half = stations[k].tributary_slope / 2.0
            assert abs(load.wz) == pytest.approx(2 * 0.8 * Q * half * 10.0 / math.hypot(10.0, 1.0))
        elif 0 < k < len(stations) - 1:
            # The web is normal to the roof: all of the suction goes along it.
            assert load.wy == pytest.approx(0.0, abs=1e-9)
            assert abs(load.wz) == pytest.approx(0.8 * Q * stations[k].tributary_slope)
    assert _resultant(warehouse, list(loads.values()))[2] == pytest.approx(0.8 * Q * 600.0)


def test_girts_take_the_wall_and_the_bottom_half_strip_goes_to_the_ground() -> None:
    warehouse = _build(slope=0.10, girt_spacing=1.5)
    loads = wind_loads(warehouse, _case(warehouse, "WIND +X"), SI)
    by_id = {load.element_id: load for load in loads}
    bare = _resultant(
        _build(slope=0.10), wind_loads(_build(slope=0.10), _case(warehouse, "WIND +X"), SI)
    )
    lost = (0.8 + 0.4) * Q * 0.75 * 30.0  # the lower half of the lowest strip, both walls
    assert _resultant(warehouse, loads) == pytest.approx(bare - [lost, 0.0, 0.0], abs=1e-6)
    for element_id, (wall, _bay, _z) in warehouse.wall_girts.items():
        pressure = {"x0": 0.8, "x1": 0.4}[wall] * Q
        assert abs(by_id[element_id].wz) == pytest.approx(pressure * 1.5)  # along its flat web
        assert by_id[element_id].wy == pytest.approx(0.0, abs=1e-9)
    # No column is loaded by the side walls: only the corner ones, by the end
    # walls, which have no girts here. The eave purlin takes the top half strip.
    side = {i for wall in ("x0", "x1") for i, _f in warehouse.wall_columns[wall]}
    ends = {i for wall in ("y0", "y1") for i, _v in warehouse.wall_columns[wall]}
    assert side & set(by_id) == side & ends != set()
    assert all(by_id[i].wz == pytest.approx(0.0, abs=1e-9) for i in side & ends)  # along Y only
    plain = _build(slope=0.10)
    roof_only = {
        load.element_id: load for load in wind_loads(plain, _case(warehouse, "WIND +X"), SI)
    }
    eave = next(i for i, k in warehouse.purlin_station.items() if k == 0)
    same = next(i for i, k in plain.purlin_station.items() if k == 0)
    extra = np.hypot(by_id[eave].wy - roof_only[same].wy, by_id[eave].wz - roof_only[same].wz)
    assert extra == pytest.approx(0.8 * Q * 0.75)


@pytest.mark.parametrize(
    ("fields", "lost_height"),
    [
        ({}, 0.0),  # no girts, no end wall columns: the frame's columns take it all
        ({"end_wall_column_spacing": 5.0}, 0.0),
        ({"girt_spacing": 1.5, "end_wall_column_spacing": 5.0}, 0.75),
    ],
)
def test_wind_along_the_ridge_loads_the_whole_end_wall(fields, lost_height) -> None:  # type: ignore[no-untyped-def]
    warehouse = _build(slope=0.10, **fields)
    loads = wind_loads(warehouse, _case(warehouse, "WIND +Y"), SI)
    gable_wall = 20.0 * 6.0 + 20.0 * 1.0 / 2.0
    expected_y = (0.8 + 0.4) * Q * (gable_wall - lost_height * 20.0)
    total = _resultant(warehouse, loads)
    assert total[1] == pytest.approx(expected_y)
    assert total[0] == pytest.approx(0.0, abs=1e-6)


def test_a_framed_end_wall_loads_its_girts_its_rafter_and_nothing_else() -> None:
    warehouse = _build(slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0)
    loads = {
        load.element_id: load for load in wind_loads(warehouse, _case(warehouse, "WIND +Y"), SI)
    }
    end_girts = {i: v for i, v in warehouse.wall_girts.items() if v[0] == "y0"}
    for element_id, (_wall, panel, z) in end_girts.items():
        if z < 4.5:  # a line with a line above and below: a full girt spacing
            assert abs(loads[element_id].wz) == pytest.approx(0.8 * Q * 1.5)
        assert (panel, loads[element_id].wy) == (panel, pytest.approx(0.0, abs=1e-9))
    # The columns of the end wall are loaded by their girts, not directly.
    assert not {i for i, _v in warehouse.wall_columns["y0"]} & set(loads)
    # The strip under the roof line hangs from the end rafter, across its web.
    rafters = warehouse.rafter_elements[0]
    assert set(rafters) <= set(loads)
    assert all(loads[i].wz == pytest.approx(0.0, abs=1e-9) for i in rafters)
    assert not set(warehouse.rafter_elements[2]) & set(loads)


def test_the_loads_follow_the_project_units() -> None:
    spec_m = _spec(slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0)
    spec_mm = _spec(
        span=20e3, eave_height=6e3, frame_spacing=6e3, slope=0.10,
        girt_spacing=1.5e3, end_wall_column_spacing=5e3, purlin_spacing=1.5e3,
    )  # fmt: skip
    assert building_shape(spec_mm, UnitSystem.SI_MM_N) == building_shape(spec_m, SI)
    in_m = build_warehouse(spec_m, SECTIONS, first_node_id=1, first_element_id=1)
    in_mm = build_warehouse(spec_mm, SECTIONS, first_node_id=1, first_element_id=1)
    wind = WarehouseWind(method="asce7", speed=50.0, exposure="C")
    for name in ("WIND +X A", "WIND -Y B"):
        case_m = next(c for c in warehouse_wind_cases(spec_m, wind, SI) if c.name == name)
        case_mm = next(
            c for c in warehouse_wind_cases(spec_mm, wind, UnitSystem.SI_MM_N) if c.name == name
        )
        a = wind_loads(in_m, case_m, SI)
        b = wind_loads(in_mm, case_mm, UnitSystem.SI_MM_N)
        assert [load.element_id for load in a] == [load.element_id for load in b]
        for one, other in zip(a, b, strict=True):  # N/m against N/mm
            assert (other.wy * 1e3, other.wz * 1e3) == pytest.approx((one.wy, one.wz), abs=1e-6)
        assert _resultant(in_mm, b) == pytest.approx(_resultant(in_m, a), abs=1e-3)


def test_asce7_uplift_on_a_low_roof_follows_the_zones() -> None:
    warehouse = _build(slope=0.10)
    wind = WarehouseWind(method="asce7", speed=45.0, exposure="C")
    qh = asce7_velocity_pressure(6.5, 45.0, "C")
    loads = wind_loads(warehouse, _case(warehouse, "WIND +X A", wind), SI)
    # Plan zones of 6.5 m, 6.5 m and the rest; the vertical part of a normal
    # pressure on a slope is the pressure on its plan.
    external = qh * 0.85 * (0.9 * 6.5 + 0.5 * 6.5 + 0.3 * 7.0) * 30.0
    internal = 0.18 * qh * 600.0
    assert _resultant(warehouse, loads)[2] == pytest.approx(external + internal, rel=1e-9)
    mirrored = wind_loads(warehouse, _case(warehouse, "WIND -X A", wind), SI)
    assert _resultant(warehouse, mirrored) == pytest.approx(
        _resultant(warehouse, loads) * [-1.0, 1.0, 1.0], abs=1e-6
    )
    # Case B pushes the roof down a little: -0.18 outside against -0.18 inside.
    down = wind_loads(warehouse, _case(warehouse, "WIND +X B", wind), SI)
    assert _resultant(warehouse, down)[2] == pytest.approx(
        qh * 600.0 * (0.85 * 0.18 - 0.18), rel=1e-9
    )


# ─────────────────────────────── the plan ───────────────────────────────
def test_wind_settings_are_checked() -> None:
    for fields in (
        {"method": "eurocode"},
        {"speed": 0.0},
        {"topographic_factor": 0.0},
        {"openings": "roof"},
        {"directions": ()},
        {"directions": ("+Z",)},
    ):
        with pytest.raises(WarehouseError):
            WarehouseWind(**fields)  # type: ignore[arg-type]
    with pytest.raises(WarehouseError, match="roughness"):
        warehouse_wind_cases(_spec(), WarehouseWind(exposure="C"), SI)  # ASCE's, not RNC-07's
    assert {p.wind_method for p in CODE_PRESETS.values()} == {"rnc07", "asce7", "en1991"}
    assert CODE_PRESETS["nscm"].wind_method == "rnc07"  # NSCM 7.2


def test_the_plan_adds_one_case_per_wind_and_combines_each_with_one_sign() -> None:
    project = _project()
    before = project.model_dump()
    spec = _spec(slope=0.10, girt_spacing=1.5, end_wall_column_spacing=5.0)
    loads = WarehouseLoads(code="rnc07", roof_dead=100.0, roof_live=98.0, wind=WarehouseWind())
    plan = plan_warehouse(project, spec, loads=loads)
    assert project.model_dump() == before
    plan.apply(project)
    assert [c.name for c in project.analyses] == [
        "DEAD", "LIVE", "WIND +X", "WIND -X", "WIND +Y", "WIND -Y",
    ]  # fmt: skip
    assert "W8X31" in [s.name for s in plan.sections]
    assert project.groups[-1].name == "End wall columns W8X31"
    patterns = {p.name: p for p in project.load_patterns}
    for name in ("WIND +X", "WIND -X", "WIND +Y", "WIND -Y"):
        pattern = patterns[name]
        assert pattern.self_weight == 0.0 and pattern.element_loads
        assert not pattern.nodal_loads
    names = [c.name for c in project.combinations]
    assert names == [
        "1.4CM",
        "1.2CM+1.6CV",
        "1.2CM+1.6Pz:WIND +X+CV",
        "1.2CM+1.6Pz:WIND -X+CV",
        "1.2CM+1.6Pz:WIND +Y+CV",
        "1.2CM+1.6Pz:WIND -Y+CV",
        "0.9CM+1.6Pz:WIND +X",
        "0.9CM+1.6Pz:WIND -X",
        "0.9CM+1.6Pz:WIND +Y",
        "0.9CM+1.6Pz:WIND -Y",
        "RNC-07 ultimate envelope",
    ]
    wind_ids = {c.id for c in project.analyses if c.name.startswith("WIND")}
    for combination in project.combinations[:-1]:
        assert all(t.factor > 0.0 for t in combination.terms if t.ref_id in wind_ids)
    assert any("4 wind case(s) by RNC-07" in note for note in plan.notes)
    Project.model_validate(project.model_dump())

    # A second warehouse beside the first gets its own wind cases.
    again = plan_warehouse(
        project, WarehouseSpec(span=10.0, eave_height=4.0, frame_spacing=5.0, origin=(40.0, 0, 0)),
        loads=WarehouseLoads(wind=WarehouseWind(directions=("+X",))),
    )  # fmt: skip
    assert [c.name for c in again.cases] == ["WIND +X (2)"]


@pytest.mark.parametrize(
    ("code", "expected", "per_wind"),
    [
        ("nscm", ["1.2CM+1.6CVT+0.5V:WIND +X", "1.2CM+V:WIND +Y+0.5CVT", "0.9CM+V:WIND +X"], 3),
        ("asce7_lrfd", [], 3),  # named by case id: 1.2D+1.6Lr+0.5W, 1.2D+W+0.5Lr, 0.9D+W
        ("asce7_asd", ["D+0.6W:WIND +X A", "0.6D+0.6W:WIND +Y B"], 3),
    ],
)
def test_each_code_combines_the_wind_its_own_way(
    code: str, expected: list[str], per_wind: int
) -> None:
    project = _project()
    preset = CODE_PRESETS[code]
    wind = WarehouseWind(
        method=preset.wind_method,
        speed=preset.wind_speed,
        exposure="C" if preset.wind_method == "asce7" else "R2",
        directions=("+X", "+Y"),
    )
    plan = plan_warehouse(
        project, _spec(), loads=WarehouseLoads(code=code, roof_live=500.0, wind=wind)
    )
    names = [c.name for c in plan.combinations]
    for name in expected:
        assert name in names, names
    wind_ids = [c.id for c in plan.cases if c.name.startswith("WIND")]
    assert len(wind_ids) == (4 if preset.wind_method == "asce7" else 2)
    with_wind = [
        c
        for c in plan.combinations
        if c.combination_type != "Envelope" and any(t.ref_id in wind_ids for t in c.terms)
    ]
    # One wind at a time, and never reversed.
    assert len(with_wind) == per_wind * len(wind_ids)
    for combination in with_wind:
        factors = [t.factor for t in combination.terms if t.ref_id in wind_ids]
        assert len(factors) == 1 and factors[0] > 0.0


# ─────────────────────── the same bytes on every machine ───────────────────────
def _planned(roof_structure: str) -> str:
    project = _project()
    spec = _spec(
        slope=0.15,
        purlin_spacing=1.5,
        girt_spacing=1.5,
        rafter_fly_brace_every=2,
        end_wall_column_spacing=5.0,
        roof_structure=roof_structure,
        truss_depth=1.0 if roof_structure == "truss" else 0.0,
    )
    preset = CODE_PRESETS["rnc07"]
    loads = WarehouseLoads(
        code="rnc07",
        roof_dead=100.0,
        roof_live=preset.roof_live_kpa * 1000.0,
        midspan_point=preset.midspan_point_kn * 1000.0,
        wind=WarehouseWind(),
        seismic=WarehouseSeismic(),
        snow=WarehouseSnow(ground=700.0),
    )
    plan_warehouse(project, spec, loads=loads).apply(project)
    return project.model_dump_json(by_alias=True)


@pytest.mark.parametrize("roof_structure", ["rafter", "truss"])
@pytest.mark.parametrize("towards", [math.inf, -math.inf])
def test_the_plan_does_not_keep_the_last_digit_of_the_maths(
    monkeypatch: pytest.MonkeyPatch, roof_structure: str, towards: float
) -> None:
    """Square roots, sines and dot products differ in the last digit between
    processors and C libraries: what a plan writes is rounded, so the same
    warehouse is the same file everywhere."""
    from opensees_studio.core import warehouse as module

    expected = _planned(roof_structure)

    def nudged(function):  # type: ignore[no-untyped-def]
        def call(*args):  # type: ignore[no-untyped-def]
            value = function(*args)
            return math.nextafter(value, towards) if value else value

        return call

    for name in ("hypot", "atan2", "atan", "degrees", "radians", "sin", "cos", "tan"):
        monkeypatch.setattr(math, name, nudged(getattr(math, name)))

    def axes(*args):  # type: ignore[no-untyped-def]
        return tuple(np.nextafter(axis, towards) for axis in frame_local_axes(*args))

    monkeypatch.setattr(module, "frame_local_axes", axes)
    norm = np.linalg.norm
    monkeypatch.setattr(
        np.linalg, "norm", lambda *args, **kw: np.nextafter(norm(*args, **kw), towards)
    )

    assert _planned(roof_structure) == expected


def test_a_number_half_way_between_two_rounded_ones_falls_to_one_side() -> None:
    half_way = 294.4254031875  # 13 digits: a product of round inputs
    values = {
        portable(v)
        for v in (half_way, math.nextafter(half_way, math.inf), math.nextafter(half_way, 0.0))
    }
    assert len(values) == 1
    assert portable(-0.0) == 0.0 and math.copysign(1.0, portable(-0.0)) == 1.0
    assert portable(1.0 / 3.0) == 0.333333333333


def test_a_load_has_no_component_that_is_round_off() -> None:
    project = _project()
    plan = plan_warehouse(
        project,
        _spec(slope=0.15, end_wall_column_spacing=5.0),
        loads=WarehouseLoads(code="rnc07", roof_dead=100.0, wind=WarehouseWind()),
    )
    for _pattern, list_name, loads in plan.pattern_loads:
        if list_name != "element_loads":
            continue
        for load in loads:
            components = [abs(c) for c in (load.wx, load.wy, load.wz) if c]
            assert min(components) > 1e-6 * max(components)
            assert "-0.0" not in repr((load.wx, load.wy, load.wz))


# ───────────────────────────── EN 1991-1-4 ─────────────────────────────
EN_WIND = WarehouseWind(method="en1991", speed=26.0, exposure="II")


def test_en1991_roof_and_wall_zones_reach_the_members() -> None:
    warehouse = _build(slope=0.2)  # 20 x 30 m, eave 6 m, ridge 8 m
    qp = en1991_peak_pressure(8.0, 26.0)
    # Along the ridge: the end walls push, the side walls cancel, the roof lifts.
    case = _case(warehouse, "WIND +Y A", EN_WIND)
    loads = wind_loads(warehouse, case, SI)
    zones = case.roof[0].zones
    assert zones is not None
    windward, leeward = en1991_wall_cp(8.0 / 30.0)
    gable_wall = 20.0 * 6.0 + 20.0 * 2.0 / 2.0
    uplift = -zones.mean(0.0, 20.0, 0.0, 30.0) * 600.0
    assert uplift > 0.6 * qp * 600.0  # no zone under -0.5, plus 0.2 inside
    assert _resultant(warehouse, loads) == pytest.approx(
        [0.0, qp * (windward - leeward) * gable_wall, uplift], abs=1e-6
    )
    # The side walls pull harder near the windward corner: zone A reaches
    # e/5 = 3.2 m, past the half bay of the first frame; the last frame is in C.
    by_id = {load.element_id: load for load in loads}
    columns = dict((frame, i) for i, frame in warehouse.wall_columns["x0"])
    assert abs(by_id[columns[0]].wz) == pytest.approx(qp * (1.2 + 0.2) * 3.0)
    assert abs(by_id[columns[5]].wz) == pytest.approx(qp * (0.5 + 0.2) * 3.0)
    # The second frame's bay, 3 to 9 m: 0.2 m of A, the rest B.
    assert abs(by_id[columns[1]].wz) == pytest.approx(qp * (1.2 * 0.2 + 0.8 * 5.8 + 0.2 * 6.0))
    # The purlins of the first bay carry the corner and edge zones, the last bay zone I.
    nodes = {n.id: n for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    station = next(k for k, s in enumerate(warehouse.stations) if 0.0 < s.x < 4.0)
    along = {
        min(nodes[n].coords[1] for n in elements[i].nodes): i
        for i, k in warehouse.purlin_station.items()
        if k == station
    }
    stations = warehouse.stations
    xa = (stations[station - 1].x + stations[station].x) / 2.0
    xb = (stations[station].x + stations[station + 1].x) / 2.0
    tributary = stations[station].tributary_slope
    for y0 in (0.0, 24.0):
        assert by_id[along[y0]].wz == pytest.approx(
            -zones.mean(xa, xb, y0, y0 + 6.0) * tributary, rel=1e-9
        )
    assert abs(by_id[along[0.0]].wz) > 1.3 * abs(by_id[along[24.0]].wz)

    # Across the ridge, case C: the windward slope pushed, the leeward one pulled.
    case = _case(warehouse, "WIND +X C", EN_WIND)
    zones = case.roof[0].zones
    assert zones is not None
    on_windward = zones.mean(0.0, 10.0, 0.0, 30.0)
    on_leeward = zones.mean(10.0, 20.0, 0.0, 30.0)
    assert on_windward > 0.0 > on_leeward
    windward, leeward = en1991_wall_cp(8.0 / 20.0)
    assert _resultant(warehouse, wind_loads(warehouse, case, SI)) == pytest.approx(
        [
            qp * (windward - leeward) * 6.0 * 30.0 + (on_windward - on_leeward) * 2.0 * 30.0,
            0.0,
            -(on_windward + on_leeward) * 10.0 * 30.0,
        ],
        abs=1e-6,
    )


def test_en1991_girts_follow_the_zones_along_the_wall() -> None:
    warehouse = _build(slope=0.2, girt_spacing=1.5, end_wall_column_spacing=5.0)
    qp = en1991_peak_pressure(8.0, 26.0)
    case = _case(warehouse, "WIND +X A", EN_WIND)
    by_id = {load.element_id: load for load in wind_loads(warehouse, case, SI)}
    # The end wall is parallel to the wind: e = min(30, 16) = 16, so zone A
    # reaches 3.2 m from the windward corner, B 16 m, and C the rest.
    xs = end_wall_layout(warehouse.spec).xs

    def suction(a: float, b: float) -> float:
        cuts = [a, *(c for c in (3.2, 16.0) if a < c < b), b]
        parts = itertools.pairwise(cuts)
        cp = lambda x: 1.2 if x < 3.2 else 0.8 if x < 16.0 else 0.5  # noqa: E731
        return sum(cp((lo + hi) / 2.0) * (hi - lo) for lo, hi in parts) / (b - a)

    assert suction(xs[0], xs[1]) > suction(xs[1], xs[2]) == 0.8 > suction(xs[3], xs[4])
    seen = set()
    for element_id, (wall, panel, z) in warehouse.wall_girts.items():
        if wall == "y0" and z == 3.0:
            seen.add(panel)
            assert abs(by_id[element_id].wz) == pytest.approx(
                qp * (suction(xs[panel], xs[panel + 1]) + 0.2) * 1.5
            )
    assert seen == {0, 1, 2, 3}


def test_the_eurocode_preset_plans_its_wind_snow_and_combinations() -> None:
    preset = CODE_PRESETS["en1990"]
    # EN 1991-1-1 Table 6.10, category H: 0.4 kN/m², and no point load with it.
    assert (preset.roof_live_kpa, preset.midspan_point_kn) == (0.4, 0.0)
    assert (preset.wind_method, preset.snow_method, preset.seismic_method) == (
        "en1991", "en1991", "en1998",
    )  # fmt: skip
    project = _project()
    loads = WarehouseLoads(
        code="en1990",
        roof_dead=100.0,
        roof_live=400.0,
        wind=WarehouseWind(method="en1991", speed=26.0, exposure="II", directions=("+X", "+Y")),
    )
    plan = plan_warehouse(project, _spec(slope=0.2), loads=loads)
    plan.apply(project)
    assert [c.name for c in project.analyses] == [
        "DEAD", "ROOF LIVE",
        "WIND +X A", "WIND +X B", "WIND +X C", "WIND +X D", "WIND +Y A", "WIND +Y B",
    ]  # fmt: skip
    names = [c.name for c in project.combinations]
    wind = [n for n in names if "W:WIND +X A" in n]
    # The wind leads with and without a favourable permanent action; the roof
    # imposed load never goes with it (EN 1991-1-1 3.3.2 (1)).
    assert "ULS 1.35G+1.5W:WIND +X A" in names and "ULS G+1.5W:WIND +X A" in names
    assert "ULS 1.35G+1.5Qr" in names
    assert not [n for n in names if "Qr" in n and "W:" in n]
    assert wind == [
        "ULS 1.35G+1.5W:WIND +X A",
        "ULS G+1.5W:WIND +X A",
        "SLS char G+W:WIND +X A",
        "SLS freq G+0.2W:WIND +X A",
    ]
    wind_ids = {c.id for c in project.analyses if c.name.startswith("WIND")}
    for combination in project.combinations:
        assert all(t.factor > 0.0 for t in combination.terms if t.ref_id in wind_ids)
    assert any("6 wind case(s) by EN 1991-1-4" in note for note in plan.notes)
    Project.model_validate(project.model_dump())
