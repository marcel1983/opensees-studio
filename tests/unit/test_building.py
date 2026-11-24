"""The parametric building: geometry, floor loads, mass source, diaphragms, earthquake, plan."""

from __future__ import annotations

import numpy as np
import pytest

from opensees_studio.core.building import (
    ACCIDENTAL_ECCENTRICITY,
    BUILDING_CODES,
    BUILDING_SEISMIC_METHODS,
    DEFAULT_STEEL_SHAPES,
    FLOOR_LIVE_CASE,
    GROUPS,
    OCCUPANCIES,
    OCCUPANCY_LIVE_KPA,
    ROOF_LIVE_CASE,
    SLAB_SPANS,
    BuildingError,
    BuildingLoads,
    BuildingSeismic,
    BuildingSpec,
    build_building,
    building_grid,
    default_section,
    elf_parameters,
    floor_loads,
    occupancy_loads,
    plan_building,
    rectangle_torsion_constant,
    seismic_case_names,
)
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.frames import SupportCondition
from opensees_studio.core.mass_source import (
    MassSource,
    effective_nodal_masses,
    pattern_weight_per_node,
)
from opensees_studio.core.project import Project
from opensees_studio.core.self_weight import weight_per_length
from opensees_studio.core.storeys import Storey
from opensees_studio.core.units import UnitSystem, gravity
from opensees_studio.core.warehouse import pressure_from_kpa
from opensees_studio.core.wind import KGF

SI = UnitSystem.SI_M_N
SECTIONS = {"column": 1, "beam_x": 2, "beam_y": 3}
#: 3 x 2 bays of 6 x 5 m, four storeys of 3.2 m: 18 x 10 m on plan.
AREA = 18.0 * 10.0


def _spec(**fields):  # type: ignore[no-untyped-def]
    values = {
        "bays_x": 3, "bay_x": 6.0, "bays_y": 2, "bay_y": 5.0,
        "storeys": 4, "storey_height": 3.2, **fields,
    }  # fmt: skip
    return BuildingSpec.regular(**values)


def _project(units: UnitSystem = SI) -> Project:
    project = Project(ndm=3, ndf=6)
    project.meta.units = units
    project.materials.extend(default_materials(project.next_material_id(), units))
    return project


def _loads(code: str = "rnc07", units: UnitSystem = SI, **fields):  # type: ignore[no-untyped-def]
    values = {
        "floor_dead": pressure_from_kpa(4.0, units),
        "roof_dead": pressure_from_kpa(3.0, units),
        **occupancy_loads(code, "office", units),
        **fields,
    }
    return BuildingLoads(code=code, **values)


def _frame_weight(project: Project) -> float:
    nodes = {n.id: np.asarray(n.coords) for n in project.nodes}
    return sum(
        weight_per_length(project, e) * float(np.linalg.norm(nodes[e.nodes[1]] - nodes[e.nodes[0]]))
        for e in project.elements
    )


def _nodal(plan):  # type: ignore[no-untyped-def]
    """Pattern id -> the nodal loads the plan gives it."""
    return {pid: loads for pid, field, loads in plan.pattern_loads if field == "nodal_loads"}


# ───────────────────────────── the geometry ─────────────────────────────
@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"spans_x": ()}, "at least one bay"),
        ({"spans_y": (5.0, 0.0)}, "Bay widths"),
        ({"storey_heights": ()}, "at least one storey"),
        ({"storey_heights": (3.0, -1.0)}, "Storey heights"),
        ({"frame": "timber"}, "frame material"),
        ({"slab": "diagonal"}, "slab span"),
    ],
)
def test_a_spec_that_is_not_a_building_is_refused(fields: dict, message: str) -> None:  # type: ignore[type-arg]
    values = {"spans_x": (6.0,), "spans_y": (5.0,), "storey_heights": (3.0,), **fields}
    with pytest.raises(BuildingError, match=message):
        BuildingSpec(**values)


def test_a_building_takes_the_codes_and_methods_it_has_numbers_for() -> None:
    """What the wizard offers: no code without live loads by use, no method without an ELF."""
    assert BUILDING_CODES == ("rnc07", "nscm", "asce7_lrfd", "asce7_asd")
    assert list(BUILDING_SEISMIC_METHODS) == ["rnc07", "nscm", "asce7"]
    assert set(BUILDING_SEISMIC_METHODS) == set(ACCIDENTAL_ECCENTRICITY)
    for code in BUILDING_CODES:
        assert occupancy_loads(code, "office", UnitSystem.SI_M_N)["floor_live"] > 0.0
    with pytest.raises(BuildingError, match="No table of live loads"):
        occupancy_loads("en1990", "office", UnitSystem.SI_M_N)
    with pytest.raises(BuildingError, match="no equivalent lateral force"):
        BuildingSeismic(method="en1998")


def test_regular_makes_equal_bays_with_a_taller_first_storey() -> None:
    spec = _spec(first_storey_height=4.5)
    assert spec.spans_x == (6.0, 6.0, 6.0)
    assert spec.spans_y == (5.0, 5.0)
    assert spec.storey_heights == (4.5, 3.2, 3.2, 3.2)
    assert spec.xs == [0.0, 6.0, 12.0, 18.0]
    assert spec.zs == pytest.approx([0.0, 4.5, 7.7, 10.9, 14.1])
    assert (spec.width, spec.depth, spec.floor_area) == (18.0, 10.0, AREA)
    assert spec.height == pytest.approx(14.1)
    with pytest.raises(BuildingError, match="at least one bay"):
        _spec(bays_x=0)
    with pytest.raises(BuildingError, match="at least one storey"):
        _spec(storeys=0)


def test_a_column_at_every_grid_point_and_beams_both_ways_at_every_floor() -> None:
    building = build_building(_spec(), SECTIONS, first_node_id=11, first_element_id=101)
    assert len(building.nodes) == 4 * 3 * 5
    assert [n.id for n in building.nodes] == list(range(11, 71))
    assert [e.id for e in building.elements] == list(range(101, 101 + 48 + 36 + 32))
    assert len(building.members["columns"]) == 4 * 3 * 4
    assert len(building.members["beams_x"]) == 3 * 3 * 4
    assert len(building.members["beams_y"]) == 4 * 2 * 4
    by_id = {e.id: e for e in building.elements}
    coords = {n.id: np.asarray(n.coords) for n in building.nodes}
    for key, axis, section in (("columns", 2, 1), ("beams_x", 0, 2), ("beams_y", 1, 3)):
        for element_id in building.members[key]:
            element = by_id[element_id]
            along = coords[element.nodes[1]] - coords[element.nodes[0]]
            assert along[axis] > 0.0 and np.count_nonzero(along) == 1
            assert element.section_id == section
    # Only the base is supported, and the ids read bottom to top.
    base = set(building.floor_nodes(0))
    assert base == set(range(11, 23))
    for node in building.nodes:
        assert all(node.restraint) == (node.id in base)
    assert building.joints[0, 0, 0] == 11 and building.joints[3, 2, 4] == 70
    assert "4 storey(s)" in building.summary()


def test_base_origin_and_column_angle() -> None:
    spec = _spec(base=SupportCondition.PINNED, origin=(100.0, 50.0, 2.0), column_angle=90.0)
    building = build_building(spec, SECTIONS)
    first = building.nodes[0]
    assert first.coords == (100.0, 50.0, 2.0)
    assert first.restraint == (True, True, True, False, False, False)
    assert building.nodes[-1].coords == pytest.approx((118.0, 60.0, 14.8))
    by_id = {e.id: e for e in building.elements}
    assert {by_id[i].local_axis_angle for i in building.members["columns"]} == {90.0}
    assert {by_id[i].local_axis_angle for i in building.members["beams_x"]} == {0.0}
    with pytest.raises(BuildingError, match="beam_y"):
        build_building(spec, {"column": 1, "beam_x": 2})


def test_every_bay_of_every_floor_is_a_panel_whose_first_edge_runs_along_x() -> None:
    building = build_building(_spec(), SECTIONS)
    coords = {n.id: np.asarray(n.coords) for n in building.nodes}
    assert sorted(building.panels) == [1, 2, 3, 4]
    for level, panels in building.panels.items():
        assert len(panels) == 6
        for a, b, c, d in panels:
            assert coords[b] - coords[a] == pytest.approx([6.0, 0.0, 0.0])
            assert coords[c] - coords[b] == pytest.approx([0.0, 5.0, 0.0])
            assert coords[d] - coords[a] == pytest.approx([0.0, 5.0, 0.0])
            assert coords[a][2] == pytest.approx(3.2 * level)


def test_the_grid_is_on_the_column_lines_and_the_floors() -> None:
    grid = building_grid(_spec(origin=(1.0, 2.0, 0.5)), name="Tower")
    assert grid.name == "Tower"
    assert grid.coord.origin == (1.0, 2.0, 0.5)
    assert [line.ordinate for line in grid.grid.x_grid_lines] == [0.0, 6.0, 12.0, 18.0]
    assert [line.ordinate for line in grid.grid.y_grid_lines] == [0.0, 5.0, 10.0]
    assert [line.ordinate for line in grid.grid.z_grid_lines] == pytest.approx(
        [0.0, 3.2, 6.4, 9.6, 12.8]
    )


# ──────────────────────────────── sections ────────────────────────────────
def test_a_steel_frame_takes_aisc_shapes_and_a_concrete_one_rectangles() -> None:
    project = _project()
    column = default_section("column", "steel", project, 7)
    assert (column.id, column.name) == (7, DEFAULT_STEEL_SHAPES["column"])
    assert column.Iy > column.Iz  # strong axis about local y
    beam = default_section("beam_x", "concrete", project, 8)
    assert beam.name == "BEAM 300x600"
    area, modulus = beam.A, beam.E
    assert area == pytest.approx(0.3 * 0.6)
    assert beam.Iy == pytest.approx(0.3 * 0.6**3 / 12.0)
    assert beam.Iz == pytest.approx(0.6 * 0.3**3 / 12.0)
    assert modulus == pytest.approx(24.87e9, rel=0.2)
    assert weight_per_length_of(beam) == pytest.approx(0.18 * 24_000.0, rel=0.05)
    # In millimetres the same section, not a thousand times it.
    mm = default_section("beam_x", "concrete", _project(UnitSystem.SI_MM_N), 8)
    area = mm.A
    assert area == pytest.approx(300.0 * 600.0)


def weight_per_length_of(section) -> float:  # type: ignore[no-untyped-def]
    return float(section.unit_weight) * float(section.A)


def test_the_torsion_constant_of_a_rectangle() -> None:
    assert rectangle_torsion_constant(1.0, 1.0) == pytest.approx(0.1406, rel=2e-3)
    assert rectangle_torsion_constant(2.0, 1.0) == pytest.approx(0.229 * 2.0, rel=5e-3)
    assert rectangle_torsion_constant(1.0, 2.0) == rectangle_torsion_constant(2.0, 1.0)
    assert rectangle_torsion_constant(100.0, 1.0) == pytest.approx(100.0 / 3.0, rel=1e-2)


# ───────────────────────────────── the plan ─────────────────────────────────
def test_only_a_3d_frame_model_takes_a_building() -> None:
    with pytest.raises(BuildingError, match="3D frame model"):
        plan_building(Project(ndm=2, ndf=3), _spec())
    with pytest.raises(BuildingError, match="Section 9"):
        plan_building(_project(), _spec(), sections={"column": 9})


def test_the_plan_changes_nothing_until_it_is_applied() -> None:
    project = _project()
    before = project.model_dump()
    plan = plan_building(project, _spec(), loads=_loads(seismic=BuildingSeismic()))
    assert project.model_dump() == before
    plan.apply(project)
    project.validate_references()
    assert len(project.nodes) == 60 + 4
    assert len(project.elements) == 116
    assert [g.name for g in project.groups] == list(GROUPS.values())
    assert {len(g.element_ids) for g in project.groups} == {48, 36, 32}
    assert [c.name for c in project.coord_systems][-1] == "Building"
    # Each panel is on its pattern once (not once from the plan and once from its pattern).
    panels = {p.name: len(p.floor_loads) for p in project.load_patterns}
    assert panels == {
        "DEAD": 24, "LIVE": 18, "ROOF LIVE": 6,
        "EQ X +e": 0, "EQ X -e": 0, "EQ Y +e": 0, "EQ Y -e": 0,
    }  # fmt: skip


def test_missing_sections_are_created_once_and_chosen_ones_are_kept() -> None:
    project = _project()
    plan = plan_building(project, _spec())
    assert [s.name for s in plan.sections] == ["W14X90", "W18X50"]
    sections = {e.section_id for e in plan.building.elements}
    assert sections == {s.id for s in plan.sections}
    plan.apply(project)
    column, beam = (s.id for s in plan.sections)
    again = plan_building(
        project,
        _spec(origin=(40.0, 0.0, 0.0), frame="concrete"),
        sections={"column": column, "beam_x": beam, "beam_y": None},
    )
    assert [s.name for s in again.sections] == ["BEAM 300x600"]
    by_id = {e.id: e for e in again.building.elements}
    assert {by_id[i].section_id for i in again.building.members["columns"]} == {column}
    assert {by_id[i].section_id for i in again.building.members["beams_y"]} == {
        again.sections[0].id
    }


def test_one_storey_per_floor_and_a_level_that_has_one_keeps_it() -> None:
    project = _project()
    project.storeys.append(Storey(id=5, name="Mezzanine", elevation=6.4))
    plan = plan_building(project, _spec())
    assert [(s.name, s.elevation) for s in plan.storeys] == [
        ("Storey 1", pytest.approx(3.2)),
        ("Storey 3", pytest.approx(9.6)),
        ("Roof", pytest.approx(12.8)),
    ]
    assert {s.id for s in plan.storeys}.isdisjoint({5})
    # The diaphragm of the second floor is the existing storey's.
    assert [d.storey_id for d in plan.diaphragms][1] == 5


def test_without_loads_the_plan_is_the_frame_its_storeys_and_its_diaphragms() -> None:
    plan = plan_building(_project(), _spec(), with_grid=False)
    assert plan.grid is None
    assert not plan.cases and not plan.pattern_loads and not plan.combinations
    assert plan.mass_source is None
    assert len(plan.diaphragms) == 4
    # No mass yet: the retained node goes to the centroid of the floor.
    assert [n.coords for n in plan.retained_nodes] == [
        pytest.approx((9.0, 5.0, z)) for z in (3.2, 6.4, 9.6, 12.8)
    ]
    assert not plan_building(_project(), _spec(diaphragms=False)).diaphragms


# ───────────────────────────────── gravity ─────────────────────────────────
@pytest.mark.parametrize("slab", SLAB_SPANS)
def test_the_floors_weigh_their_load_times_their_area(slab: str) -> None:
    project = _project()
    loads = _loads()
    plan = plan_building(project, _spec(slab=slab), loads=loads)
    plan.apply(project)
    patterns = {p.name: p for p in project.load_patterns}

    def weight(name: str) -> float:
        return sum(pattern_weight_per_node(project, patterns[name]).values())

    assert weight("DEAD") == pytest.approx(
        _frame_weight(project) + (3 * 4000.0 + 3000.0) * AREA, rel=1e-9
    )
    assert weight(FLOOR_LIVE_CASE) == pytest.approx(3 * 250.0 * KGF * AREA, rel=1e-9)
    assert weight(ROOF_LIVE_CASE) == pytest.approx(100.0 * KGF * AREA, rel=1e-9)
    distributions = {load.distribution for load in patterns["DEAD"].floor_loads}
    assert distributions == {
        {"two_way": "two_way", "one_way_x": "one_way_12", "one_way_y": "one_way_23"}[slab]
    }


def test_a_one_way_slab_loads_only_the_beams_it_spans_between() -> None:
    from opensees_studio.core.area_loads import pattern_distributed_loads

    for slab, loaded in (("one_way_x", "beams_y"), ("one_way_y", "beams_x")):
        project = _project()
        plan = plan_building(project, _spec(slab=slab), loads=_loads())
        plan.apply(project)
        dead = next(p for p in project.load_patterns if p.name == "DEAD")
        carrying = {load.element_id for load in pattern_distributed_loads(project, dead)}
        assert carrying == set(plan.building.members[loaded]), slab


def test_no_load_no_panel_and_no_live_case() -> None:
    plan = plan_building(_project(), _spec(), loads=BuildingLoads(floor_dead=4000.0))
    assert [c.name for c in plan.cases] == ["DEAD"]
    assert [(field, len(loads)) for _id, field, loads in plan.pattern_loads] == [
        ("floor_loads", 18)
    ]
    building = build_building(_spec(), SECTIONS)
    assert len(floor_loads(building, 1.0, 2.0)) == 24
    assert {load.value for load in floor_loads(building, 0.0, 2.0)} == {2.0}


def test_an_existing_dead_case_takes_the_slab() -> None:
    project = _project()
    ensure_dead_load_case(project)
    dead = project.load_patterns[0]
    plan = plan_building(project, _spec(), loads=_loads())
    assert [c.name for c in plan.cases] == [FLOOR_LIVE_CASE, ROOF_LIVE_CASE]
    assert plan.pattern_loads[0][0] == dead.id
    assert not dead.floor_loads  # the project is not touched
    assert plan.mass_source.patterns[0].pattern_id == dead.id


@pytest.mark.parametrize(
    ("code", "floor", "roof"),
    [("rnc07", 100.0 / 250.0, 40.0 / 100.0), ("nscm", 0.15, 0.15), ("asce7_lrfd", None, None)],
)
def test_the_mass_is_the_dead_case_and_the_live_load_the_code_counts(
    code: str, floor: float | None, roof: float | None
) -> None:
    project = _project()
    plan = plan_building(project, _spec(), loads=_loads(code))
    source = plan.mass_source
    assert source.element_self_mass is False
    patterns = {p.id: p.name for p in plan.patterns}
    factors = {patterns[e.pattern_id]: e.factor for e in source.patterns}
    expected = {"DEAD": 1.0}
    if floor is not None and roof is not None:
        expected |= {FLOOR_LIVE_CASE: pytest.approx(floor), ROOF_LIVE_CASE: pytest.approx(roof)}
    assert factors == expected
    plan.apply(project)
    table = OCCUPANCY_LIVE_KPA["asce7" if code == "asce7_lrfd" else code]
    weight = (
        _frame_weight(project) - _base_half_columns(project, plan)
        + (3 * 4000.0 + 3000.0) * AREA
        + (3 * table["office"][1] + table["roof"][1]) * 1e3 * AREA
    )  # fmt: skip
    # The half of the first storey's columns that hangs from the supports is no mass.
    masses = effective_nodal_masses(project)
    assert gravity(SI) * sum(m[0] for m in masses.values()) == pytest.approx(weight, rel=1e-9)
    # All of it above the base sits on the four retained nodes.
    retained = [n.id for n in plan.retained_nodes]
    assert gravity(SI) * sum(masses[n][0] for n in retained) == pytest.approx(weight, rel=1e-9)
    assert all(masses[n][5] > 0.0 for n in retained)


def _base_half_columns(project: Project, plan) -> float:  # type: ignore[no-untyped-def]
    """The half of the first storey's columns that hangs from the base."""
    by_id = {e.id: e for e in project.elements}
    first = plan.building.members["columns"][:12]
    return sum(0.5 * weight_per_length(project, by_id[i]) * 3.2 for i in first)


def test_a_project_that_has_a_mass_source_gets_the_building_added_to_it() -> None:
    project = _project()
    project.mass_source = MassSource(include_vertical=True)
    plan = plan_building(project, _spec(), loads=_loads())
    source = plan.mass_source
    assert source.include_vertical is True
    # The dead case brings the self weight: the elements' own would double it.
    assert source.element_self_mass is False
    assert len(source.patterns) == 3
    assert any("already had a mass source" in note for note in plan.notes)
    plan.apply(project)
    assert plan_building(project, _spec(origin=(50.0, 0.0, 0.0)), loads=None).mass_source is None


# ──────────────────────────────── diaphragms ────────────────────────────────
def test_every_floor_is_tied_to_a_node_at_its_centre_of_mass() -> None:
    project = _project()
    # Bays of 4 and 8 m along X: the centroid of the joints (5.33 m) is not the
    # centre of the floor's mass (6 m, the slab is uniform).
    spec = BuildingSpec(spans_x=(4.0, 8.0), spans_y=(5.0,), storey_heights=(3.0, 3.0))
    plan = plan_building(project, spec, loads=_loads())
    assert [(d.storey_id, d.constrained_nodes) for d in plan.diaphragms] == [
        (s.id, ()) for s in plan.storeys
    ]
    assert [d.retained_node for d in plan.diaphragms] == [n.id for n in plan.retained_nodes]
    assert {n.id for n in plan.retained_nodes}.isdisjoint({n.id for n in plan.building.nodes})
    for node, z in zip(plan.retained_nodes, (3.0, 6.0), strict=True):
        assert node.coords[2] == z  # exactly in the floor
        assert node.coords[1] == pytest.approx(2.5)
        assert 5.6 < node.coords[0] < 6.0
        assert node.restraint == (False,) * 6


def test_a_floor_whose_storey_is_already_tied_joins_that_diaphragm() -> None:
    project = _project()
    plan_building(project, _spec(storeys=2), loads=_loads()).apply(project)
    wing = plan_building(project, _spec(storeys=3, origin=(18.0, 0.0, 0.0)), loads=_loads())
    assert len(wing.diaphragms) == 1 and len(wing.retained_nodes) == 1
    assert sum("already has a rigid diaphragm" in note for note in wing.notes) == 2
    wing.apply(project)
    project.validate_references()
    assert len({n.id for n in project.nodes}) == len(project.nodes)
    assert len({e.id for e in project.elements}) == len(project.elements)
    assert len({c.name for c in project.analyses}) == len(project.analyses)


# ──────────────────────────────── earthquake ────────────────────────────────
@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"method": "ubc"}, "seismic method"),
        ({"reduction": 0.0}, "reduction factor"),
        ({"period_x": -1.0}, "period"),
        ({"eccentricity": 0.6}, "eccentricity"),
        ({"directions": ()}, "at least one"),
        ({"directions": ("Z",)}, "direction"),
    ],
)
def test_seismic_settings_are_checked(fields: dict, message: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(BuildingError, match=message):
        BuildingSeismic(**fields)


def test_the_accidental_eccentricity_is_the_code_s_unless_given() -> None:
    assert ACCIDENTAL_ECCENTRICITY == {"rnc07": 0.1, "nscm": 0.05, "asce7": 0.05}
    assert BuildingSeismic(method="rnc07").eccentricity_ratio == 0.1
    assert BuildingSeismic(method="nscm").eccentricity_ratio == 0.05
    assert BuildingSeismic(method="asce7", eccentricity=0.0).eccentricity_ratio == 0.0
    assert seismic_case_names("X", True) == [("EQ X +e", 1), ("EQ X -e", -1)]
    assert seismic_case_names("Y", False) == [("EQ Y", 0)]


def test_where_the_period_comes_from() -> None:
    spec = _spec()
    # RNC-07 has no empirical period: none given, the plateau.
    plateau, source = elf_parameters(BuildingSeismic(method="rnc07"), spec, SI, "X")
    assert plateau.use_period is False and "plateau" in source
    given, source = elf_parameters(BuildingSeismic(method="rnc07", period_y=0.8), spec, SI, "Y")
    assert (given.use_period, given.period) == (True, 0.8) and "0.8" in source
    # ASCE 7 Eq. 12.8-7 for a steel moment frame: 0.0724 hn^0.8.
    asce, source = elf_parameters(BuildingSeismic(method="asce7"), spec, SI, "X")
    assert asce.period == pytest.approx(0.0724 * 12.8**0.8, rel=1e-6) and "empirical" in source
    assert asce.code == "asce7_16"
    concrete, _ = elf_parameters(BuildingSeismic(method="asce7"), _spec(frame="concrete"), SI, "X")
    assert concrete.period == pytest.approx(0.0466 * 12.8**0.9, rel=1e-6)
    # NSCM caps a given period at Cu Ta, so it carries Ta as well.
    nscm, _ = elf_parameters(BuildingSeismic(method="nscm", soil="C", period_x=2.0), spec, SI, "X")
    assert nscm.code == "nscm2021" and nscm.period == 2.0 and nscm.approximate_period > 0.0
    # In feet the height is still 12.8 m.
    feet = BuildingSpec.regular(
        bays_x=1, bay_x=20.0, bays_y=1, bay_y=20.0, storeys=4, storey_height=3.2 / 0.3048
    )
    us, _ = elf_parameters(BuildingSeismic(method="asce7"), feet, UnitSystem.US_FT_KIP, "X")
    assert us.period == pytest.approx(asce.period, rel=1e-6)
    with pytest.raises(BuildingError, match="structural system"):
        elf_parameters(BuildingSeismic(method="asce7", system="igloo"), spec, SI, "X")


@pytest.mark.parametrize(
    ("code", "seismic", "coefficient"),
    [
        # RNC-07 Art. 24: zone C, soil II, S = 1.5; 2.7 S a0 / (Q' Omega) = 0.314 < S a0.
        ("rnc07", BuildingSeismic(method="rnc07", a0=0.31, soil="II"), 1.5 * 0.31),
        ("asce7_lrfd", BuildingSeismic(method="asce7", sds=1.0, sd1=0.6, reduction=8.0), 0.125),
        (
            "asce7_lrfd",
            BuildingSeismic(method="asce7", sds=1.0, sd1=0.6, reduction=8.0, importance=1.5),
            0.1875,
        ),
    ],
)
def test_the_base_shear_is_the_coefficient_times_the_seismic_weight(
    code: str, seismic: BuildingSeismic, coefficient: float
) -> None:
    project = _project()
    plan = plan_building(project, _spec(), loads=_loads(code, seismic=seismic))
    assert sorted(plan.lateral) == ["X", "Y"]
    plan.apply(project)
    masses = effective_nodal_masses(project)
    weight = gravity(SI) * sum(masses[n.id][0] for n in plan.retained_nodes)
    for direction, axis in (("X", 0), ("Y", 1)):
        result = plan.lateral[direction]
        assert result.total_weight == pytest.approx(weight, rel=1e-9)
        assert result.coefficient == pytest.approx(coefficient, rel=1e-9)
        assert result.base_shear == pytest.approx(coefficient * weight, rel=1e-9)
        assert [lv.name for lv in result.levels] == ["Storey 1", "Storey 2", "Storey 3", "Roof"]
        cases = [c for c in plan.cases if c.name.startswith(f"EQ {direction}")]
        assert [c.name for c in cases] == [f"EQ {direction} +e", f"EQ {direction} -e"]
        for case in cases:
            loads = _nodal(plan)[case.pattern_ids[0]]
            assert [load.node_id for load in loads] == [n.id for n in plan.retained_nodes]
            assert sum(load.forces[axis] for load in loads) == pytest.approx(result.base_shear)
            assert all(load.forces[1 - axis] == 0.0 for load in loads)
    assert any("Earthquake along X" in note for note in plan.notes)


def test_the_accidental_torque_is_the_storey_force_times_the_eccentricity() -> None:
    project = _project()
    seismic = BuildingSeismic(method="rnc07", a0=0.31, soil="II")
    plan = plan_building(project, _spec(), loads=_loads(seismic=seismic))
    by_name = {c.name: _nodal(plan)[c.pattern_ids[0]] for c in plan.cases if "EQ" in c.name}
    for level, force in enumerate(lv.force for lv in plan.lateral["X"].levels):
        # RNC-07 Art. 32 d: 0.1 b, b across the earthquake: 10 m for X, 18 m for Y.
        plus, minus = by_name["EQ X +e"][level].forces, by_name["EQ X -e"][level].forces
        assert plus[0] == minus[0] == pytest.approx(force)
        assert plus[5] == pytest.approx(-force * 1.0) and minus[5] == pytest.approx(force * 1.0)
        plus, minus = by_name["EQ Y +e"][level].forces, by_name["EQ Y -e"][level].forces
        assert plus[5] == pytest.approx(force * 1.8) and minus[5] == pytest.approx(-force * 1.8)


def test_no_eccentricity_or_no_diaphragm_one_case_per_direction() -> None:
    seismic = BuildingSeismic(method="asce7", eccentricity=0.0, directions=("Y",))
    plan = plan_building(_project(), _spec(), loads=_loads("asce7_lrfd", seismic=seismic))
    assert [c.name for c in plan.cases if "EQ" in c.name] == ["EQ Y"]
    assert all(load.forces[5] == 0.0 for loads in _nodal(plan).values() for load in loads)
    loose = plan_building(
        _project(), _spec(diaphragms=False), loads=_loads(seismic=BuildingSeismic(soil="II"))
    )
    assert [c.name for c in loose.cases if "EQ" in c.name] == ["EQ X", "EQ Y"]
    assert any("Without rigid diaphragms" in note for note in loose.notes)
    # The storey force is shared between the joints of the floor by their mass.
    shear = loose.lateral["X"].base_shear
    x_case = next(c for c in loose.cases if c.name == "EQ X")
    loads = _nodal(loose)[x_case.pattern_ids[0]]
    assert len(loads) == 48
    assert sum(load.forces[0] for load in loads) == pytest.approx(shear)


def test_what_the_code_refuses_is_a_building_error() -> None:
    with pytest.raises(BuildingError, match="soil"):
        plan_building(
            _project(), _spec(), loads=_loads(seismic=BuildingSeismic(method="rnc07", soil=""))
        )


def test_the_static_method_s_height_limit_is_a_note() -> None:
    seismic = BuildingSeismic(method="nscm", a0=0.36667, soil="C")
    tall = plan_building(_project(), _spec(), loads=_loads("nscm", seismic=seismic))
    assert sum("exceeds the 12 m" in note for note in tall.notes) == 2
    low = plan_building(_project(), _spec(storeys=3), loads=_loads("nscm", seismic=seismic))
    assert not any("exceeds" in note for note in low.notes)


# ─────────────────────────────── combinations ───────────────────────────────
def _earthquake_terms(plan, combination) -> dict[str, float]:  # type: ignore[no-untyped-def]
    names = {c.id: c.name for c in plan.cases}
    return {
        names[t.ref_id]: t.factor
        for t in combination.terms
        if t.source == "case" and names.get(t.ref_id, "").startswith("EQ")
    }


@pytest.mark.parametrize(
    ("code", "method"), [("rnc07", "rnc07"), ("nscm", "nscm"), ("rnc07", "nscm")]
)
def test_nicaragua_combines_100_percent_with_30_percent_of_the_other_direction(
    code: str, method: str
) -> None:
    seismic = BuildingSeismic(method=method, a0=0.31, soil="II" if method == "rnc07" else "C")
    plan = plan_building(_project(), _spec(storeys=3), loads=_loads(code, seismic=seismic))
    seen = set()
    for combination in plan.combinations:
        terms = _earthquake_terms(plan, combination)
        if not terms:
            continue
        # One case of each direction, never the two eccentricities of one.
        assert sorted(name[:4] for name in terms) == ["EQ X", "EQ Y"], combination.name
        assert sorted(abs(f) for f in terms.values()) == pytest.approx([0.3, 1.0])
        seen.add(tuple(sorted(terms.items())))
    # 2 x 2 cases, either one at 100 %, 4 signs: 32, in two gravity combinations.
    assert len(seen) == 32
    names = [c.name for c in plan.combinations]
    assert len(names) == len(set(names))
    assert plan.combinations[-1].combination_type == "Envelope"


def test_nscm_takes_the_vertical_earthquake_of_the_site() -> None:
    from opensees_studio.core.warehouse import WarehouseSeismic, nscm_a0_fas

    seismic = BuildingSeismic(method="nscm", a0=0.36667, soil="C", importance_class="II")
    plan = plan_building(_project(), _spec(storeys=3), loads=_loads("nscm", seismic=seismic))
    site = nscm_a0_fas(WarehouseSeismic(method="nscm", a0=0.36667, soil="C", importance_class="II"))
    dead = next(c.id for c in plan.cases if c.name == "DEAD")
    factors = {
        round(t.factor, 4)
        for c in plan.combinations
        if _earthquake_terms(plan, c)
        for t in c.terms
        if t.ref_id == dead
    }
    assert factors == {round(1.2 + 0.2 * site, 4), round(0.9 - 0.2 * site, 4)}


def test_asce7_takes_one_earthquake_case_at_a_time() -> None:
    seismic = BuildingSeismic(method="asce7", sds=1.0, sd1=0.6, reduction=8.0)
    plan = plan_building(_project(), _spec(), loads=_loads("asce7_lrfd", seismic=seismic))
    with_e = [t for c in plan.combinations if (t := _earthquake_terms(plan, c))]
    assert all(len(terms) == 1 for terms in with_e)
    assert {name for terms in with_e for name in terms} == {
        "EQ X +e", "EQ X -e", "EQ Y +e", "EQ Y -e"
    }  # fmt: skip
    assert {f for terms in with_e for f in terms.values()} == {1.0, -1.0}


def test_gravity_only_and_no_combinations() -> None:
    plan = plan_building(_project(), _spec(), loads=_loads("asce7_lrfd"))
    assert [c.name for c in plan.combinations] == [
        "1.4D", "1.2D+1.6L+0.5Lr", "1.2D+1.6Lr+L", "LRFD envelope"
    ]  # fmt: skip
    none = plan_building(_project(), _spec(), loads=_loads(combinations=False))
    assert not none.combinations and len(none.cases) == 3


# ───────────────────────────── uses and units ─────────────────────────────
def test_the_live_loads_of_a_use() -> None:
    assert set(OCCUPANCIES) | {"roof"} == set(OCCUPANCY_LIVE_KPA["rnc07"])
    for table in OCCUPANCY_LIVE_KPA.values():
        assert set(table) == set(OCCUPANCIES) | {"roof"}
        assert all(0.0 <= seismic <= live for live, seismic in table.values())
    office = occupancy_loads("rnc07", "office", SI)
    assert office == {
        "floor_live": pytest.approx(250.0 * KGF),
        "floor_live_seismic": pytest.approx(100.0 * KGF),
        "roof_live": pytest.approx(100.0 * KGF),
        "roof_live_seismic": pytest.approx(40.0 * KGF),
    }
    assert occupancy_loads("nscm", "assembly", UnitSystem.SI_M_KN)["floor_live_seismic"] == (
        pytest.approx(0.15 * 400.0 * KGF / 1e3)
    )
    asce = occupancy_loads("asce7_asd", "office", UnitSystem.US_FT_KIP)
    assert asce["floor_live"] == pytest.approx(0.050, rel=1e-3)  # 50 psf
    assert asce["roof_live"] == pytest.approx(0.020, rel=1e-3)
    assert asce["floor_live_seismic"] == 0.0
    with pytest.raises(BuildingError, match="use"):
        occupancy_loads("rnc07", "roof", SI)
    with pytest.raises(BuildingError, match="design code"):
        occupancy_loads("ubc97", "office", SI)


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"code": "ubc97"}, "design code"),
        ({"floor_dead": -1.0}, "positive"),
        ({"floor_live": 1.0, "floor_live_seismic": 2.0}, "floor live load"),
        ({"roof_live_seismic": 2.0}, "roof live load"),
    ],
)
def test_loads_are_checked(fields: dict, message: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(BuildingError, match=message):
        BuildingLoads(**fields)


def test_the_forces_follow_the_project_units() -> None:
    seismic = BuildingSeismic(method="rnc07", a0=0.31, soil="II")
    si = plan_building(_project(), _spec(), loads=_loads(seismic=seismic))
    kn_project = _project(UnitSystem.SI_M_KN)
    kn = plan_building(kn_project, _spec(), loads=_loads(units=UnitSystem.SI_M_KN, seismic=seismic))
    assert kn.lateral["X"].base_shear == pytest.approx(si.lateral["X"].base_shear / 1e3, rel=1e-9)
    assert [n.coords for n in kn.retained_nodes] == [
        pytest.approx(n.coords) for n in si.retained_nodes
    ]


# ─────────────────────── the same bytes on every machine ───────────────────────
@pytest.mark.parametrize("towards", [np.inf, -np.inf])
def test_the_plan_does_not_keep_the_last_digit_of_the_sums(
    monkeypatch: pytest.MonkeyPatch, towards: float
) -> None:
    """The centre of mass and the storey forces are sums of products, whose last
    digit depends on the processor: what the plan writes of them is rounded."""
    from opensees_studio.core import equivalent_lateral, mass_source

    def planned() -> str:
        project = _project()
        plan_building(project, _spec(), loads=_loads(seismic=BuildingSeismic())).apply(project)
        return project.model_dump_json(by_alias=True)

    expected = planned()

    def nudge(value: float) -> float:
        return float(np.nextafter(value, towards)) if value else value

    centre = mass_source.diaphragm_centre_of_mass
    forces = equivalent_lateral.nodal_forces
    monkeypatch.setattr(
        mass_source,
        "diaphragm_centre_of_mass",
        lambda *args, **kw: tuple(nudge(v) for v in centre(*args, **kw)),
    )
    monkeypatch.setattr(
        equivalent_lateral,
        "nodal_forces",
        lambda *args, **kw: {
            node: tuple(nudge(v) for v in force) for node, force in forces(*args, **kw).items()
        },
    )

    assert planned() == expected
