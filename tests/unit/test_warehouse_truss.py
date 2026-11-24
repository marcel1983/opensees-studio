"""The warehouse with roof trusses: chords, web, ties, bracing lengths, sections."""

from __future__ import annotations

import numpy as np
import pytest

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.frames import RoofType
from opensees_studio.core.project import Project
from opensees_studio.core.trusses import TrussType
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    BRACE_RELEASES,
    CASE_SYSTEM,
    CODE_PRESETS,
    GROUPS,
    POST_TOP_RELEASES,
    SECONDARY_RELEASES,
    TRUSS_GROUPS,
    TRUSS_SECTION_KEYS,
    Warehouse,
    WarehouseError,
    WarehouseLoads,
    WarehouseSpec,
    WarehouseWind,
    bottom_chord_ties,
    build_warehouse,
    member_design_overrides,
    midspan_point_loads,
    plan_warehouse,
    warehouse_wind_cases,
    wind_loads,
)

SECTIONS = {
    "column": 1,
    "rafter": 2,
    "purlin": 3,
    "girt": 4,
    "brace": 5,
    "end_column": 6,
    "top_chord": 7,
    "bottom_chord": 8,
    "truss_web": 9,
    "chord_tie": 10,
}
SI = UnitSystem.SI_M_N


def _spec(**fields):  # type: ignore[no-untyped-def]
    values = {
        "span": 24.0,
        "eave_height": 8.0,
        "frame_spacing": 6.0,
        "n_frames": 4,
        "slope": 0.15,
        "purlin_spacing": 2.0,
        "roof_structure": "truss",
        "truss_depth": 1.0,
        **fields,
    }
    return WarehouseSpec(**values)


def _build(**fields) -> Warehouse:  # type: ignore[no-untyped-def]
    return build_warehouse(_spec(**fields), SECTIONS, first_node_id=1, first_element_id=1)


def _project() -> Project:
    project = Project(ndm=3, ndf=6)
    project.materials.extend(default_materials(project.next_material_id(), SI))
    ensure_dead_load_case(project)
    return project


def _coords(warehouse: Warehouse) -> dict[int, tuple[float, ...]]:
    return {n.id: n.coords for n in warehouse.nodes}


def _elements(warehouse: Warehouse, group: str):  # type: ignore[no-untyped-def]
    by_id = {e.id: e for e in warehouse.elements}
    return [by_id[i] for i in warehouse.members[group]]


# ─────────────────────────────── the spec ───────────────────────────────
@pytest.mark.parametrize(
    "fields",
    [
        {"roof_structure": "arch"},
        {"truss_depth": 0.0},
        {"truss_depth": 8.0},  # the bottom chord would lie on the ground
        {"truss_type": TrussType.WARREN},  # no vertical under the purlins
        {"truss_bottom": "curved"},
        {"bottom_chord_tie_every": -1},
    ],
)
def test_a_truss_that_cannot_be_built_is_refused(fields: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(WarehouseError):
        _spec(**fields)


def test_the_truss_fields_are_ignored_with_rafters() -> None:
    spec = WarehouseSpec(span=20.0, eave_height=6.0, frame_spacing=6.0, truss_depth=0.0)
    assert not spec.has_truss
    assert "rafter" in spec.section_keys()
    assert not set(TRUSS_SECTION_KEYS) & set(spec.section_keys())


def test_a_truss_needs_its_sections_and_no_rafter() -> None:
    spec = _spec()
    assert spec.section_keys() == [
        "column", "purlin", "girt", "brace", "top_chord", "bottom_chord", "truss_web", "chord_tie",
    ]  # fmt: skip
    with pytest.raises(WarehouseError, match="top_chord"):
        build_warehouse(
            spec,
            {"column": 1, "purlin": 3, "girt": 4, "brace": 5},
            first_node_id=1,
            first_element_id=1,
        )


# ─────────────────────────────── geometry ───────────────────────────────
def test_the_chords_follow_the_roof_and_the_level_under_it() -> None:
    warehouse = _build()
    coords = _coords(warehouse)
    n_stations = len(warehouse.stations)
    assert n_stations == 15  # 12.13 m of slope in 7 parts, twice
    assert warehouse.members["rafters"] == []
    assert len(warehouse.members["top_chords"]) == (n_stations - 1) * 4
    assert len(warehouse.members["bottom_chords"]) == (n_stations - 1) * 4
    assert warehouse.rafter_elements[0] == warehouse.members["top_chords"][: n_stations - 1]
    for frame, (top, bottom) in enumerate(
        zip(warehouse.rafter_elements, warehouse.bottom_chord_elements, strict=True)
    ):
        by_id = {e.id: e for e in warehouse.elements}
        for k, (t, b) in enumerate(zip(top, bottom, strict=True)):
            s0, s1 = warehouse.stations[k], warehouse.stations[k + 1]
            assert coords[by_id[t].nodes[0]] == pytest.approx((s0.x, frame * 6.0, s0.z))
            assert coords[by_id[t].nodes[1]] == pytest.approx((s1.x, frame * 6.0, s1.z))
            assert coords[by_id[b].nodes[0]] == pytest.approx((s0.x, frame * 6.0, 7.0))
            assert coords[by_id[b].nodes[1]] == pytest.approx((s1.x, frame * 6.0, 7.0))
            # Chords are continuous: no release.
            assert by_id[t].releases == by_id[b].releases
            assert by_id[t].releases != BRACE_RELEASES


def test_a_parallel_bottom_chord_keeps_the_depth() -> None:
    warehouse = _build(truss_bottom="parallel", truss_depth=1.2)
    coords = _coords(warehouse)
    for element in _elements(warehouse, "bottom_chords"):
        for node in element.nodes:
            x, _y, z = coords[node]
            assert z == pytest.approx(warehouse.spec.profile.roof_height(x) - 1.2)
    assert warehouse.spec.bottom_chord_height(12.0) == pytest.approx(8.0 + 1.8 - 1.2)


def test_the_web_has_a_vertical_under_every_purlin_and_a_diagonal_per_panel() -> None:
    warehouse = _build()
    coords = _coords(warehouse)
    n_stations = len(warehouse.stations)
    web = _elements(warehouse, "truss_webs")
    verticals = [e for e in web if coords[e.nodes[0]][0] == coords[e.nodes[1]][0]]
    diagonals = [e for e in web if e not in verticals]
    # The two columns are the end verticals of each truss.
    assert len(verticals) == (n_stations - 2) * 4
    assert len(diagonals) == (n_stations - 1) * 4
    assert all(e.releases == BRACE_RELEASES for e in web)


def _rising(warehouse: Warehouse) -> list[bool]:
    """Per panel of the first frame: the diagonal rises to the right."""
    coords = _coords(warehouse)
    out: dict[float, bool] = {}
    for element in _elements(warehouse, "truss_webs"):
        (xa, ya, za), (xb, _yb, zb) = (coords[n] for n in element.nodes)
        if ya != 0.0 or xa == xb:
            continue
        (x0, z0), (x1, z1) = sorted([(xa, za), (xb, zb)])
        out[x0] = z1 > z0
        assert x1 > x0
    return [out[x] for x in sorted(out)]


def test_pratt_diagonals_run_down_to_mid_span_and_howe_up() -> None:
    pratt = _rising(_build(truss_type=TrussType.PRATT))
    howe = _rising(_build(truss_type=TrussType.HOWE))
    half = len(pratt) // 2
    assert pratt == [False] * half + [True] * half
    assert howe == [True] * half + [False] * half


def test_warren_diagonals_alternate_and_are_symmetric() -> None:
    warren = _rising(_build(truss_type=TrussType.WARREN_VERTICALS))
    assert warren[:4] == [False, True, False, True]
    assert warren == [not r for r in reversed(warren)]


def test_each_nave_has_its_own_truss() -> None:
    pratt = _rising(_build(n_naves=2, span=12.0, roof=RoofType.MONO_PITCH, slope=0.05))
    per_nave = len(pratt) // 2
    assert per_nave == 7  # the middle panel goes with the left half
    assert pratt[:per_nave] == [False] * 4 + [True] * 3
    assert pratt[per_nave:] == pratt[:per_nave]


# ───────────────────────────── columns ─────────────────────────────
def test_a_column_goes_through_the_bottom_chord_up_to_the_top_chord() -> None:
    warehouse = _build()
    coords = _coords(warehouse)
    columns = _elements(warehouse, "columns")
    assert len(columns) == 2 * 2 * 4  # base to chord, chord to top
    first = [e for e in columns if coords[e.nodes[0]][:2] == (0.0, 0.0)]
    assert [coords[e.nodes[0]][2] for e in first] == [0.0, 7.0]
    assert coords[first[-1].nodes[1]][2] == 8.0
    chord = _elements(warehouse, "bottom_chords")[0]
    assert chord.nodes[0] == first[0].nodes[1]


def test_a_girt_at_the_level_of_the_bottom_chord_shares_its_node() -> None:
    warehouse = _build(girt_spacing=1.0)  # girts at 1, 2, ... 7 m; the chord at 7 m
    coords = _coords(warehouse)
    assert len(set(coords.values())) == len(coords)
    columns = [e for e in _elements(warehouse, "columns") if coords[e.nodes[0]][:2] == (0.0, 0.0)]
    assert len(columns) == 8
    top_girt = next(
        e for e in _elements(warehouse, "girts") if coords[e.nodes[0]] == (0.0, 0.0, 7.0)
    )
    assert top_girt.nodes[0] == _elements(warehouse, "bottom_chords")[0].nodes[0]
    # That girt line is the tie of the wall: only the ridge has a tie of its own.
    assert {coords[e.nodes[0]][0] for e in _elements(warehouse, "chord_ties")} == {12.0}


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"girt_spacing": 1.5, "end_wall_column_spacing": 6.0},
        {"girt_spacing": 1.0, "end_wall_column_spacing": 5.0, "truss_bottom": "parallel"},
        {"n_naves": 2, "span": 15.0, "truss_type": TrussType.HOWE, "end_wall_column_spacing": 5.0},
        {"roof": RoofType.MONO_PITCH, "slope": 0.08, "truss_type": TrussType.WARREN_VERTICALS},
        {"slope": 0.0, "girt_spacing": 2.0, "bottom_chord_tie_every": 2},
    ],
)
def test_no_node_and_no_member_is_repeated(fields: dict) -> None:  # type: ignore[type-arg]
    warehouse = _build(**fields)
    coords = [tuple(round(c, 6) for c in n.coords) for n in warehouse.nodes]
    assert len(set(coords)) == len(coords)
    pairs = [tuple(sorted(e.nodes)) for e in warehouse.elements]
    assert len(set(pairs)) == len(pairs)
    assert all(a != b for a, b in pairs)
    listed = [eid for ids in warehouse.members.values() for eid in ids]
    assert sorted(listed) == [e.id for e in warehouse.elements]
    assert set(warehouse.members) == set(GROUPS)


def test_an_end_wall_column_is_the_vertical_of_the_end_truss() -> None:
    warehouse = _build(girt_spacing=1.5, end_wall_column_spacing=6.0)
    coords = _coords(warehouse)
    by_id = {e.id: e for e in warehouse.elements}
    posts = [e for e in _elements(warehouse, "end_columns") if coords[e.nodes[0]][1] == 0.0]
    xs = sorted({coords[e.nodes[0]][0] for e in posts})
    assert len(xs) == 3 and xs[1] == 12.0
    ridge = [e for e in posts if coords[e.nodes[0]][0] == 12.0]
    levels = [coords[e.nodes[0]][2] for e in ridge]
    assert 7.0 in levels  # it meets the bottom chord
    assert coords[ridge[-1].nodes[1]][2] == pytest.approx(9.8)
    assert ridge[-1].releases == POST_TOP_RELEASES
    chord_node = next(e.nodes[0] for e in ridge if coords[e.nodes[0]][2] == 7.0)
    assert any(chord_node in by_id[i].nodes for i in warehouse.bottom_chord_elements[0])
    # The truss web has no vertical there in the end frames, and has one inside.
    web_verticals = [
        e
        for e in _elements(warehouse, "truss_webs")
        if coords[e.nodes[0]][0] == coords[e.nodes[1]][0] == 12.0
    ]
    assert sorted(coords[e.nodes[0]][1] for e in web_verticals) == [6.0, 12.0]


# ─────────────────────── ties and sway bracing ───────────────────────
def test_the_bottom_chord_is_tied_at_the_columns_and_the_ridge() -> None:
    warehouse = _build()
    assert [k for k, tied in enumerate(bottom_chord_ties(warehouse.spec, warehouse.stations)) if tied] == [
        0, 7, 14,
    ]  # fmt: skip
    ties = _elements(warehouse, "chord_ties")
    assert len(ties) == 3 * 3  # three lines, three bays
    coords = _coords(warehouse)
    assert {coords[e.nodes[0]][2] for e in ties} == {7.0}
    assert all(coords[e.nodes[0]][0] == coords[e.nodes[1]][0] for e in ties)
    assert all(e.releases == SECONDARY_RELEASES for e in ties)
    # A vertical X at the ridge line of each braced bay; the side walls have their own.
    sway = _elements(warehouse, "sway_bracing")
    assert len(sway) == 2 * 2
    assert {coords[n][0] for e in sway for n in e.nodes} == {12.0}
    assert all(e.releases == BRACE_RELEASES for e in sway)


def test_more_tie_lines_on_request_and_no_sway_bracing_without_roof_bracing() -> None:
    warehouse = _build(bottom_chord_tie_every=2, roof_bracing=False)
    tied = bottom_chord_ties(warehouse.spec, warehouse.stations)
    assert [k for k, flag in enumerate(tied) if flag] == [0, 2, 4, 6, 7, 9, 11, 13, 14]
    assert len(warehouse.members["chord_ties"]) == 9 * 3
    assert warehouse.members["sway_bracing"] == []


# ───────────────────────── bracing lengths ─────────────────────────
def test_the_bottom_chord_is_braced_only_at_its_ties() -> None:
    warehouse = _build()
    lengths = [warehouse.unbraced[e] for e in warehouse.bottom_chord_elements[1]]
    assert lengths == pytest.approx([12.0] * 14)
    closer = _build(bottom_chord_tie_every=2)
    panel = 12.0 / 7.0
    assert sorted({round(closer.unbraced[e], 9) for e in closer.bottom_chord_elements[1]}) == [
        pytest.approx(panel),
        pytest.approx(2 * panel),
    ]
    # A purlin is fixed to the top chord itself: no override, the panel as modelled.
    assert not set(warehouse.rafter_elements[0]) & set(warehouse.unbraced)
    overrides = {o.element_id: o for o in member_design_overrides(warehouse)}
    one = overrides[warehouse.bottom_chord_elements[0][0]]
    assert one.length_minor == one.length_ltb == pytest.approx(12.0)


def test_the_bottom_chord_braces_the_column() -> None:
    warehouse = _build(girt_spacing=2.0)  # girts at 2, 4, 6 m without stabilising angles
    coords = _coords(warehouse)
    column = [e for e in _elements(warehouse, "columns") if coords[e.nodes[0]][:2] == (0.0, 0.0)]
    assert [warehouse.unbraced[e.id] for e in column] == pytest.approx([7.0, 7.0, 7.0, 7.0, 1.0])


# ───────────────────────────── loads ─────────────────────────────
@pytest.mark.parametrize(
    "fields",
    [
        {"girt_spacing": 1.6, "end_wall_column_spacing": 6.0},
        {"girt_spacing": 1.0, "end_wall_column_spacing": 6.0},  # a girt line on the chord
        {"girt_spacing": 1.0, "end_wall_column_spacing": 4.0, "truss_bottom": "parallel"},
        {"end_wall_column_spacing": 6.0, "n_naves": 2, "span": 12.0},
    ],
)
def test_the_wind_on_a_trussed_warehouse_is_the_wind_on_the_same_building(
    fields: dict,  # type: ignore[type-arg]
) -> None:
    truss = _build(**fields)
    rafter = _build(**fields, roof_structure="rafter")
    nodes_of = {id(w): {n.id: np.asarray(n.coords) for n in w.nodes} for w in (truss, rafter)}

    def resultant(warehouse: Warehouse, loads: list) -> np.ndarray:  # type: ignore[type-arg]
        from opensees_studio.core.geometry.local_axes import frame_local_axes

        nodes = nodes_of[id(warehouse)]
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

    for a, b in zip(
        warehouse_wind_cases(truss.spec, WarehouseWind(), SI),
        warehouse_wind_cases(rafter.spec, WarehouseWind(), SI),
        strict=True,
    ):
        assert resultant(truss, wind_loads(truss, a, SI)) == pytest.approx(
            resultant(rafter, wind_loads(rafter, b, SI)), rel=1e-9, abs=1e-6
        )
    # Without girts the wall hangs from the columns, over their whole height.
    bare = _build()
    case = warehouse_wind_cases(bare.spec, WarehouseWind(), SI)[0]
    loaded = {load.element_id for load in wind_loads(bare, case, SI)}
    assert set(bare.members["columns"]) <= loaded


def test_the_mid_span_load_goes_on_the_ridge_node_of_the_top_chord() -> None:
    warehouse = _build()
    nodal, inside = midspan_point_loads(warehouse, 2000.0)
    assert inside == [] and len(nodal) == 4
    coords = _coords(warehouse)
    for load in nodal:
        assert coords[load.node_id][0::2] == pytest.approx((12.0, 9.8))


# ───────────────────────────── the plan ─────────────────────────────
def test_the_plan_creates_the_truss_sections_and_groups() -> None:
    project = _project()
    before = project.model_dump()
    preset = CODE_PRESETS["rnc07"]
    loads = WarehouseLoads(code="rnc07", roof_dead=100.0, roof_live=preset.roof_live_kpa * 1e3)
    plan = plan_warehouse(project, _spec(girt_spacing=1.5), loads=loads)
    assert project.model_dump() == before
    assert [s.name for s in plan.sections] == [
        "W14X48", "C150X50X15X2.38", "L3X3X1_4", "HSS6X6X1_4", "HSS3X3X3_16", "HSS4X4X3_16",
    ]  # fmt: skip
    plan.apply(project)
    project.validate_references()
    names = [g.name for g in project.groups]
    assert "Rafters" not in names
    assert [GROUPS[key] for key in TRUSS_GROUPS] == names[-5:]
    section_of = {s.id: s.name for s in project.sections}
    by_id = {e.id: e for e in project.elements}
    used = {
        key: {section_of[by_id[i].section_id] for i in plan.warehouse.members[key]}
        for key in TRUSS_GROUPS
    }
    assert used == {
        "top_chords": {"HSS6X6X1_4"},
        "bottom_chords": {"HSS6X6X1_4"},
        "truss_webs": {"HSS3X3X3_16"},
        "chord_ties": {"HSS4X4X3_16"},
        "sway_bracing": {"L3X3X1_4"},
    }
    lengths = {m.element_id: m for m in project.design.members}  # type: ignore[union-attr]
    assert set(plan.warehouse.bottom_chord_elements[0]) <= set(lengths)


def test_the_cases_the_wizard_creates_use_a_sparse_solver() -> None:
    project = _project()
    existing = {c.id: c.system for c in project.analyses}  # type: ignore[attr-defined]
    loads = WarehouseLoads(code="rnc07", roof_live=400.0, wind=WarehouseWind())
    plan = plan_warehouse(project, _spec(n_frames=6), loads=loads)
    assert {c.system for c in plan.cases} == {CASE_SYSTEM}
    assert len(plan.cases) == 5  # the roof live load and four winds
    plan.apply(project)
    # A case of the project is not the wizard's to change: the note says so.
    assert {c.id: c.system for c in project.analyses if c.id in existing} == existing  # type: ignore[attr-defined]
    assert any("DEAD" in note and CASE_SYSTEM in note for note in plan.notes)


def test_the_summary_names_the_truss() -> None:
    text = _build().summary()
    assert "4 trussed frames" in text and "truss depth 1" in text
    assert "112 chord" in text  # 14 panels, two chords, four frames


def test_a_level_bottom_chord_on_an_end_wall_girt_line_takes_its_place() -> None:
    warehouse = _build(girt_spacing=1.0, end_wall_column_spacing=6.0)
    coords = _coords(warehouse)
    end_girts_at_chord = [
        e
        for e in _elements(warehouse, "girts")
        if coords[e.nodes[0]][2] == coords[e.nodes[1]][2] == 7.0
        and coords[e.nodes[0]][1] == coords[e.nodes[1]][1]
    ]
    assert end_girts_at_chord == []
    for frame, wall in ((0, "y0"), (3, "y1")):
        chord = warehouse.bottom_chord_elements[frame]
        assert {warehouse.wall_girts[e][0] for e in chord} == {wall}
        assert {warehouse.wall_girts[e][2] for e in chord} == {7.0}
    assert not set(warehouse.bottom_chord_elements[1]) & set(warehouse.wall_girts)
    # So the wind on that strip of the end wall is not lost.
    case = next(
        c for c in warehouse_wind_cases(warehouse.spec, WarehouseWind(), SI) if c.name == "WIND +Y"
    )
    loaded = {load.element_id for load in wind_loads(warehouse, case, SI)}
    assert set(warehouse.bottom_chord_elements[0]) <= loaded
