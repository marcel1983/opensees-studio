"""The warehouse on roof trusses, solved by OpenSees: equilibrium, truss action, the steel check."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from examples.warehouse_truss import build_warehouse_project

from opensees_studio.core.frames import RoofType
from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.project import Project
from opensees_studio.core.trusses import TrussType
from opensees_studio.core.warehouse import (
    CASE_SYSTEM,
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


def _end_forces(results: object, element_id: int) -> np.ndarray:
    """Local end forces of a frame element at the last step: i then j."""
    return np.asarray(results.element_forces[element_id]).reshape(-1)[-12:]  # type: ignore[attr-defined]


def _tension(results: object, element_id: int) -> float:
    """Axial force, positive in tension."""
    return float(_end_forces(results, element_id)[6])


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


def _group(project: Project, name: str) -> list[int]:
    return list(next(g for g in project.groups if g.name.startswith(f"{name} ")).element_ids)


@pytest.fixture(scope="module")
def solved() -> tuple[Project, dict[str, object]]:
    project = build_warehouse_project()
    assert {c.system for c in project.analyses} == {CASE_SYSTEM}  # type: ignore[attr-defined]
    return project, {c.name: OpenSeesRunner(project).run(c) for c in project.analyses}


def test_the_reactions_balance_the_wind_on_the_walls_and_the_roof(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    # 30 x 36 m, eave 8 m, ridge 10.25 m; girts every 1.6 m, so the lowest 0.8 m
    # of each wall goes straight into the ground. The wind does not know what
    # carries the roof: these are the numbers of a rafter warehouse of this shape.
    # The last quarter metre of roof is above 10 m, where the velocity grows with
    # the height (Art. 51), so the hand numbers are a little low.
    walls_x = (0.8 + 0.4) * Q * (8.0 - 0.8) * 36.0
    roof_x = (-0.8 + 0.7) * Q * 2.25 * 36.0  # windward and leeward suction, 8.5 degrees
    uplift_x = (0.8 + 0.7) * Q * 15.0 * 36.0
    assert -_reaction(results["WIND +X"]) == pytest.approx(
        [walls_x + roof_x, 0.0, uplift_x], rel=1e-3, abs=1e-4
    )
    end_wall = 30.0 * 8.0 + 30.0 * 2.25 / 2.0 - 30.0 * 0.8
    assert -_reaction(results["WIND +Y"]) == pytest.approx(
        [0.0, (0.8 + 0.4) * Q * end_wall, 0.8 * Q * 30.0 * 36.0], rel=1e-3, abs=1e-4
    )
    for name in ("WIND +X", "WIND -X", "WIND +Y", "WIND -Y"):
        assert -_reaction(results[name]) == pytest.approx(
            _applied(project, name), rel=1e-9, abs=1e-4
        )


def test_gravity_pulls_the_bottom_chord_and_presses_the_top_chord(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    dead = results["DEAD"]
    nodes = {n.id: n.coords for n in project.nodes}
    elements = {e.id: e for e in project.elements}

    def at_mid_span(group: str) -> list[int]:
        """The elements of an interior frame next to the ridge."""
        return [
            i
            for i in _group(project, group)
            if nodes[elements[i].nodes[0]][1] == 18.0
            and 13.0 < nodes[elements[i].nodes[0]][0] < 16.0
        ]

    bottom, top = at_mid_span("Truss bottom chords"), at_mid_span("Truss top chords")
    assert bottom and top
    assert all(_tension(dead, i) > 1e4 for i in bottom)
    assert all(_tension(dead, i) < -1e4 for i in top)
    # The couple of the two chords is the bending moment of the frame at mid-span:
    # about the same force in both, 3.2 m apart.
    assert _tension(dead, bottom[0]) == pytest.approx(-_tension(dead, top[0]), rel=0.15)
    # The wind lifts the roof: the bottom chord goes into compression.
    assert all(_tension(results["WIND +X"], i) < 0.0 for i in bottom)
    assert _reaction(dead)[2] > 0.0
    sag = _displacements(dead)[:, 2].min()
    assert -30.0 / 250.0 < sag < -0.002


def test_the_web_members_carry_axial_force_only(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    dead = results["DEAD"]
    nodes = {n.id: n.coords for n in project.nodes}
    elements = {e.id: e for e in project.elements}
    web = _group(project, "Truss web members")
    for element_id in web:
        forces = _end_forces(dead, element_id)
        assert forces[[4, 5, 10, 11]] == pytest.approx(0.0, abs=1e-3)  # pinned at both ends
    # Pratt: the diagonals next to the columns hang the roof from the top chord.
    first = [
        i
        for i in web
        if nodes[elements[i].nodes[0]][1] == 18.0
        and {round(nodes[n][0], 6) for n in elements[i].nodes} == {0.0, round(15.0 / 11, 6)}
    ]
    assert len(first) == 1
    assert _tension(dead, first[0]) > 1e4


def test_the_trussed_warehouse_is_stable_under_wind(solved) -> None:  # type: ignore[no-untyped-def]
    _project, results = solved
    for name in ("WIND +X", "WIND -X", "WIND +Y", "WIND -Y"):
        disp = _displacements(results[name])
        assert np.all(np.isfinite(disp))
        assert np.abs(disp[:, :3]).max() < 30.0 / 100.0  # a sway, not a mechanism
    plus, minus = _displacements(results["WIND +X"]), _displacements(results["WIND -X"])
    assert np.abs(plus[:, 0]).max() == pytest.approx(np.abs(minus[:, 0]).max(), rel=1e-6)
    along = _displacements(results["WIND +Y"])
    assert np.abs(along[:, 1]).max() < 0.06  # the bracing and the ties hold the building


def test_the_steel_check_takes_the_bottom_chord_between_its_ties(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    by_id = {c.id: results[c.name] for c in project.analyses}
    report = steel_frame_check(project, by_id, project.design)
    checked = {m.element_id: m for m in report.members}
    bottom = _group(project, "Truss bottom chords")
    top = _group(project, "Truss top chords")
    assert set(bottom) | set(top) <= set(checked)
    assert {checked[i].shape for i in bottom + top} == {"HSS6X6X1_4"}
    # 15 m of half span in 11 panels; a tie at the column, at every fourth panel
    # point and at the ridge: 4, 4 and 3 panels.
    panel = 15.0 / 11.0
    assert {round(checked[i].unbraced[1], 6) for i in bottom} == {
        round(4 * panel, 6),
        round(3 * panel, 6),
    }
    # A purlin holds the top chord at every panel point.
    assert max(checked[i].unbraced[1] for i in top) < 1.6
    assert all(checked[i].ratio > 0.0 for i in bottom + top)
    web = _group(project, "Truss web members")
    assert set(web) <= set(checked)


@pytest.mark.parametrize(
    "fields",
    [
        {"truss_bottom": "parallel", "truss_type": TrussType.HOWE},
        {"roof": RoofType.MONO_PITCH, "slope": 0.08, "truss_type": TrussType.WARREN_VERTICALS},
        {"n_naves": 2, "span": 10.0, "girt_spacing": 1.0, "truss_depth": 1.0},
        {"slope": 0.0, "end_wall_column_spacing": 0.0, "girt_spacing": 0.0},
    ],
)
def test_other_trusses_are_in_equilibrium(fields: dict) -> None:  # type: ignore[type-arg]
    project = Project(ndm=3, ndf=6)
    values = {
        "span": 16.0, "eave_height": 6.0, "frame_spacing": 5.0, "n_frames": 4,
        "purlin_spacing": 2.0, "girt_spacing": 1.25, "end_wall_column_spacing": 4.0,
        "roof_structure": "truss", "truss_depth": 0.8, "bottom_chord_tie_every": 2, **fields,
    }  # fmt: skip
    plan = plan_warehouse(
        project, WarehouseSpec(**values), loads=WarehouseLoads(wind=WarehouseWind())
    )
    plan.apply(project)
    cases = [c for c in project.analyses if c.name.startswith("WIND")]
    assert len(cases) == 4
    for case in cases:
        results = OpenSeesRunner(project).run(case)
        applied = _applied(project, case.name)
        assert np.linalg.norm(applied) > 1e3
        assert -_reaction(results) == pytest.approx(applied, rel=1e-8, abs=1e-4)
        assert np.abs(_displacements(results)[:, :3]).max() < 0.5
