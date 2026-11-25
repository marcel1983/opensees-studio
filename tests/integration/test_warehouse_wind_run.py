"""The warehouse under wind, solved by OpenSees: equilibrium, load paths, the steel check."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from examples.warehouse_wind import build_warehouse_project

from opensees_studio.core.frames import RoofType, SupportCondition
from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.project import Project
from opensees_studio.core.warehouse import (
    WarehouseLoads,
    WarehouseSpec,
    WarehouseWind,
    plan_warehouse,
)
from opensees_studio.core.wind import KGF
from opensees_studio.services.opensees_runner import OpenSeesRunner
from opensees_studio.services.steel_design import steel_frame_check

#: RNC-07 zone 2, Group B, R2, flat terrain: the pressure of Cp = 1.
Q = 0.0479 * 45.0**2 * KGF


def _reaction(results: object) -> np.ndarray:
    return np.sum(
        [np.asarray(r).reshape(-1, 6)[-1][:3] for r in results.node_reaction.values()],  # type: ignore[attr-defined]
        axis=0,
    )


def _displacements(results: object) -> np.ndarray:
    return np.array(
        [np.asarray(d).reshape(-1, 6)[-1] for d in results.node_disp.values()]  # type: ignore[attr-defined]
    )


def _applied(project: Project, case_name: str) -> np.ndarray:
    case = next(c for c in project.analyses if c.name == case_name)
    pattern = next(p for p in project.load_patterns if p.id == case.pattern_ids[0])  # type: ignore[attr-defined]
    nodes = {n.id: np.asarray(n.coords) for n in project.nodes}
    elements = {e.id: e for e in project.elements}
    total = np.zeros(3)
    for load in pattern.element_loads:  # type: ignore[attr-defined]
        element = elements[load.element_id]
        a, b = nodes[element.nodes[0]], nodes[element.nodes[1]]
        axes = frame_local_axes(3, a, b, element.local_axis_angle)  # type: ignore[attr-defined]
        assert axes is not None
        vector = load.wx * axes[0] + load.wy * axes[1] + load.wz * axes[2]
        total += vector * float(np.linalg.norm(b - a))
    return total


@pytest.fixture(scope="module")
def solved() -> tuple[Project, dict[str, object]]:
    project = build_warehouse_project()
    runner_results = {c.name: OpenSeesRunner(project).run(c) for c in project.analyses}
    return project, runner_results


def test_the_reactions_balance_the_wind_on_the_walls_and_the_roof(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    # 24 x 36 m, eave 7 m, ridge 8.8 m; girts every 1.4 m, so the lowest 0.7 m of
    # each wall goes straight into the ground.
    walls_x = (0.8 + 0.4) * Q * (7.0 - 0.7) * 36.0
    roof_x = (-0.8 + 0.7) * Q * 1.8 * 36.0  # windward and leeward suction, 8.5 degrees
    uplift_x = (0.8 + 0.7) * Q * 12.0 * 36.0
    assert -_reaction(results["WIND +X"]) == pytest.approx(
        [walls_x + roof_x, 0.0, uplift_x], rel=1e-9, abs=1e-5
    )
    assert -_reaction(results["WIND -X"]) == pytest.approx(
        [-(walls_x + roof_x), 0.0, uplift_x], rel=1e-9, abs=1e-5
    )
    end_wall = 24.0 * 7.0 + 24.0 * 1.8 / 2.0 - 24.0 * 0.7
    walls_y = (0.8 + 0.4) * Q * end_wall
    uplift_y = 0.8 * Q * 24.0 * 36.0
    assert -_reaction(results["WIND +Y"]) == pytest.approx(
        [0.0, walls_y, uplift_y], rel=1e-9, abs=1e-5
    )
    for name in ("WIND +X", "WIND -X", "WIND +Y", "WIND -Y"):
        assert -_reaction(results[name]) == pytest.approx(
            _applied(project, name), rel=1e-9, abs=1e-5
        )


def test_the_wind_cases_are_stable_and_mirror_each_other(solved) -> None:  # type: ignore[no-untyped-def]
    _project, results = solved
    for name in ("WIND +X", "WIND -X", "WIND +Y", "WIND -Y"):
        disp = _displacements(results[name])
        assert np.all(np.isfinite(disp))
        assert np.abs(disp[:, :3]).max() < 24.0 / 100.0  # a sway, not a mechanism
    plus, minus = _displacements(results["WIND +X"]), _displacements(results["WIND -X"])
    assert np.abs(plus[:, 0]).max() == pytest.approx(np.abs(minus[:, 0]).max(), rel=1e-6)
    # Across the ridge the frames sway in their planes; along Y only the end
    # wall columns move, bowing outwards under the suction on the end walls.
    assert np.abs(plus[:, 0]).max() > 2 * np.abs(plus[:, 1]).max()
    along = _displacements(results["WIND +Y"])
    assert np.abs(along[:, 1]).max() < 0.05  # the bracing holds the building


def test_an_end_wall_column_spans_from_its_base_to_the_roof(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    posts = set(
        next(g for g in project.groups if g.name.startswith("End wall columns ")).element_ids
    )
    elements = {e.id: e for e in project.elements}
    nodes = {n.id: n for n in project.nodes}
    bases = {
        elements[i].nodes[0]
        for i in posts
        if nodes[elements[i].nodes[0]].coords[2] == 0.0
        and nodes[elements[i].nodes[0]].coords[1] == 0.0
    }
    assert len(bases) == 3
    reactions = results["WIND +Y"].node_reaction  # type: ignore[attr-defined]
    for node_id in bases:
        reaction = np.asarray(reactions[node_id]).reshape(-1, 6)[-1]
        assert reaction[1] < -1e3  # the windward wall pushes on it; its base pushes back
        assert reaction[3:] == pytest.approx(0.0, abs=1e-3)  # a pinned base
    # The bases of the wall take part of the wall only: the rest goes up into the
    # roof and comes down through the bracing of the side walls.
    at_wall = sum(
        np.asarray(r).reshape(-1, 6)[-1][1]
        for n, r in reactions.items()
        if nodes[n].coords[1] == 0.0 and nodes[n].coords[2] == 0.0
    )
    total = _reaction(results["WIND +Y"])[1]
    assert abs(at_wall) < abs(total)


def test_the_steel_check_reads_the_end_wall_columns_bracing(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    by_id = {c.id: results[c.name] for c in project.analyses}
    report = steel_frame_check(project, by_id, project.design)
    posts = set(
        next(g for g in project.groups if g.name.startswith("End wall columns ")).element_ids
    )
    checked = [m for m in report.members if m.element_id in posts]
    assert len(checked) == len(posts)
    assert {m.shape for m in checked} == {"W8X31"}
    # Girts 1.4 m apart, a stabilising angle on every second one; the last
    # stretch of the ridge column runs from the girt at 5.6 m to the rafter at 8.8 m.
    lbs = {round(m.unbraced[2], 6) for m in checked}
    assert 2.8 in lbs and max(lbs) == pytest.approx(3.2)
    assert all(m.ratio > 0.0 for m in checked)


@pytest.mark.parametrize(
    ("fields", "wind"),
    [
        ({"roof": RoofType.MONO_PITCH, "span": 12.0, "n_naves": 2, "slope": 0.15}, {}),
        ({"slope": 0.0, "support": SupportCondition.FIXED}, {"openings": "x0"}),
        ({"slope": 0.5, "girt_spacing": 0.0}, {"method": "asce7", "exposure": "B", "speed": 50.0}),
        (
            {"slope": 0.1, "end_wall_column_spacing": 0.0},
            {"method": "asce7", "exposure": "C", "speed": 57.0, "openings": "y1"},
        ),
    ],
)
def test_other_shapes_and_procedures_are_in_equilibrium(fields: dict, wind: dict) -> None:  # type: ignore[type-arg]
    project = Project(ndm=3, ndf=6)
    values = {
        "span": 16.0, "eave_height": 5.0, "frame_spacing": 5.0, "n_frames": 4,
        "girt_spacing": 1.25, "end_wall_column_spacing": 4.0, **fields,
    }  # fmt: skip
    plan = plan_warehouse(
        project, WarehouseSpec(**values), loads=WarehouseLoads(wind=WarehouseWind(**wind))
    )
    plan.apply(project)
    cases = [c for c in project.analyses if c.name.startswith("WIND")]
    assert len(cases) == (8 if wind.get("method") == "asce7" else 4)
    for case in cases:
        results = OpenSeesRunner(project).run(case)
        applied = _applied(project, case.name)
        assert np.linalg.norm(applied) > 1e3
        assert -_reaction(results) == pytest.approx(applied, rel=1e-8, abs=1e-4)
        assert np.abs(_displacements(results)[:, :3]).max() < 0.5
