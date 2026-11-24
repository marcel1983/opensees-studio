"""The parametric building, solved by OpenSees: gravity, storey shears, torsion, diaphragms."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from examples.building_office import plan_building_project

from opensees_studio.core.building import (
    BuildingLoads,
    BuildingPlan,
    BuildingSeismic,
    BuildingSpec,
    occupancy_loads,
    plan_building,
)
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.project import Project
from opensees_studio.core.self_weight import weight_per_length
from opensees_studio.core.warehouse import CASE_SYSTEM
from opensees_studio.core.wind import KGF
from opensees_studio.services.opensees_runner import OpenSeesRunner

AREA = 18.0 * 15.0


def _last(values: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
    return {key: np.asarray(v).reshape(-1, 6)[-1] for key, v in values.items()}


def _reaction(results: object) -> np.ndarray:
    return np.sum(list(_last(results.node_reaction).values()), axis=0)[:3]  # type: ignore[attr-defined]


def _frame_weight(project: Project) -> float:
    nodes = {n.id: np.asarray(n.coords) for n in project.nodes}
    return sum(
        weight_per_length(project, e) * float(np.linalg.norm(nodes[e.nodes[1]] - nodes[e.nodes[0]]))
        for e in project.elements
    )


@pytest.fixture(scope="module")
def solved() -> tuple[Project, BuildingPlan, dict[str, object]]:
    project, plan = plan_building_project()
    project.validate_references()
    assert {c.system for c in project.analyses} == {CASE_SYSTEM}  # type: ignore[attr-defined]
    assert [c.name for c in project.analyses] == [
        "DEAD", "LIVE", "ROOF LIVE", "EQ X +e", "EQ X -e", "EQ Y +e", "EQ Y -e"
    ]  # fmt: skip
    return project, plan, {c.name: OpenSeesRunner(project).run(c) for c in project.analyses}


def test_the_supports_carry_the_frame_and_the_floors(solved) -> None:  # type: ignore[no-untyped-def]
    project, _plan, results = solved
    dead = _frame_weight(project) + (2 * 4500.0 + 3500.0) * AREA
    assert _reaction(results["DEAD"]) == pytest.approx([0.0, 0.0, dead], rel=1e-9, abs=1e-3)
    # NSCM Tabla 7.1.1: offices 250 kg/m², a roof slab 100 kg/m².
    assert _reaction(results["LIVE"])[2] == pytest.approx(2 * 250.0 * KGF * AREA, rel=1e-9)
    assert _reaction(results["ROOF LIVE"])[2] == pytest.approx(100.0 * KGF * AREA, rel=1e-9)
    # A symmetric building under gravity does not sway.
    drift = np.array(list(_last(results["DEAD"].node_disp).values()))[:, :2]
    assert np.abs(drift).max() < 1e-9


def test_the_base_shear_and_the_storey_shears_are_the_code_s(solved) -> None:  # type: ignore[no-untyped-def]
    project, plan, results = solved
    # Seismic weight: the dead case above the base and 0.15 of the live load (NSCM 9.6 a).
    by_id = {e.id: e for e in project.elements}
    hanging = sum(
        0.5 * weight_per_length(project, by_id[i]) * 3.5
        for i in plan.building.members["columns"][:16]
    )
    weight = (
        _frame_weight(project) - hanging
        + (2 * 4500.0 + 3500.0) * AREA
        + 0.15 * (2 * 250.0 + 100.0) * KGF * AREA
    )  # fmt: skip
    for direction, axis in (("X", 0), ("Y", 1)):
        lateral = plan.lateral[direction]
        assert lateral.total_weight == pytest.approx(weight, rel=1e-9)
        # The plateau of NSCM 8.2.1 with Ro = 8: Cs = 0.143.
        assert lateral.coefficient == pytest.approx(0.143, rel=2e-3)
        shear = lateral.coefficient * weight
        expected = np.zeros(3)
        expected[axis] = shear
        forces = [lv.force for lv in lateral.levels]
        storeys = [s.id for s in sorted(project.storeys, key=lambda s: s.elevation)]
        for sign in ("+e", "-e"):
            result = results[f"EQ {direction} {sign}"]
            assert -_reaction(result) == pytest.approx(expected, rel=1e-8, abs=1e-3)
            for k, storey in enumerate(storeys):
                cut = np.asarray(result.storey_shear[storey])[-1]  # type: ignore[attr-defined]
                assert cut[axis] == pytest.approx(sum(forces[k:]), rel=1e-6)


def test_the_accidental_eccentricity_twists_the_floors_either_way(solved) -> None:  # type: ignore[no-untyped-def]
    _project, plan, results = solved
    roof = plan.retained_nodes[-1].id

    def at_roof(name: str) -> np.ndarray:
        return _last(results[name].node_disp)[roof]  # type: ignore[attr-defined]

    for direction, axis, twist in (("X", 0, -1.0), ("Y", 1, 1.0)):
        plus, minus = at_roof(f"EQ {direction} +e"), at_roof(f"EQ {direction} -e")
        # The same sway, opposite twists: +e moves the force along the other axis.
        assert plus[axis] == pytest.approx(minus[axis], rel=1e-9)
        assert plus[5] == pytest.approx(-minus[5], rel=1e-6)
        assert np.sign(plus[5]) == twist and abs(plus[5]) > 1e-6
        # A visible sway, far from a mechanism: under 1 % of the height elastic.
        assert 1e-4 < plus[axis] < 9.5 / 100.0
        assert abs(plus[1 - axis]) < 1e-6 * plus[axis] + 1e-9


def test_every_floor_moves_as_a_rigid_body_in_its_plane(solved) -> None:  # type: ignore[no-untyped-def]
    project, plan, results = solved
    coords = {n.id: np.asarray(n.coords) for n in project.nodes}
    disp = _last(results["EQ Y +e"].node_disp)  # type: ignore[attr-defined]
    for level, retained in enumerate(plan.retained_nodes, start=1):
        centre = disp[retained.id]
        for node in plan.building.floor_nodes(level):
            dx, dy = (coords[node] - coords[retained.id])[:2]
            assert disp[node][0] == pytest.approx(centre[0] - centre[5] * dy, abs=1e-10)
            assert disp[node][1] == pytest.approx(centre[1] + centre[5] * dx, abs=1e-10)
            assert disp[node][5] == pytest.approx(centre[5], abs=1e-12)
    # The frame furthest along +X moves more than the centre under +e, the other less.
    roof = plan.building.spec.n_storeys
    far, near = plan.building.joints[3, 0, roof], plan.building.joints[0, 0, roof]
    assert disp[far][1] > disp[plan.retained_nodes[-1].id][1] > disp[near][1] > 0.0


@pytest.mark.parametrize(
    ("spec", "code", "seismic"),
    [
        (
            {"slab": "one_way_x", "column_angle": 90.0},
            "rnc07",
            BuildingSeismic(method="rnc07", a0=0.31, soil="II", reduction=4.0),
        ),
        (
            {"diaphragms": False, "slab": "one_way_y"},
            "asce7_lrfd",
            BuildingSeismic(method="asce7", sds=1.0, sd1=0.6, reduction=8.0),
        ),
    ],
)
def test_other_buildings_solve_too(spec: dict, code: str, seismic: BuildingSeismic) -> None:  # type: ignore[type-arg]
    project = Project(ndm=3, ndf=6)
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))
    plan = plan_building(
        project,
        BuildingSpec(spans_x=(4.0, 7.0), spans_y=(5.0,), storey_heights=(4.0, 3.0), **spec),
        loads=BuildingLoads(
            code=code,
            floor_dead=4000.0,
            roof_dead=3000.0,
            **occupancy_loads(code, "residential", units),
            seismic=seismic,
        ),
    )
    plan.apply(project)
    project.validate_references()
    for case in project.analyses:
        result = OpenSeesRunner(project).run(case)
        reaction = _reaction(result)
        assert np.all(np.isfinite(reaction))
        if case.name.startswith("EQ"):
            axis = 0 if " X" in case.name else 1
            assert -reaction[axis] == pytest.approx(plan.lateral["XY"[axis]].base_shear, rel=1e-8)
        elif case.name == "DEAD":
            assert reaction[2] == pytest.approx(
                _frame_weight(project) + (4000.0 + 3000.0) * 11.0 * 5.0, rel=1e-9
            )
