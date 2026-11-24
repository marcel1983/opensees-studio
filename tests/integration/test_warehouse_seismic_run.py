"""The warehouse's static earthquake, solved by OpenSees: base shear, sway, bracing."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from examples.warehouse_seismic import build_warehouse_project

from opensees_studio.core.frames import RoofType
from opensees_studio.core.project import Project
from opensees_studio.core.self_weight import weight_per_length
from opensees_studio.core.warehouse import (
    CASE_SYSTEM,
    WarehouseLoads,
    WarehouseSeismic,
    WarehouseSpec,
    plan_warehouse,
    seismic_coefficient,
)
from opensees_studio.core.wind import KGF
from opensees_studio.services.opensees_runner import OpenSeesRunner


def _reaction(results: object) -> np.ndarray:
    return np.sum(
        [np.asarray(r).reshape(-1, 6)[-1][:3] for r in results.node_reaction.values()],  # type: ignore[attr-defined]
        axis=0,
    )


def _displacements(results: object) -> np.ndarray:
    return np.array(
        [np.asarray(d).reshape(-1, 6)[-1] for d in results.node_disp.values()]  # type: ignore[attr-defined]
    )


def _steel_weight(project: Project) -> float:
    nodes = {n.id: np.asarray(n.coords) for n in project.nodes}
    return sum(
        weight_per_length(project, e) * float(np.linalg.norm(nodes[e.nodes[1]] - nodes[e.nodes[0]]))
        for e in project.elements
    )


@pytest.fixture(scope="module")
def solved() -> tuple[Project, dict[str, object]]:
    project = build_warehouse_project()
    assert {c.system for c in project.analyses} == {CASE_SYSTEM}  # type: ignore[attr-defined]
    cases = [c for c in project.analyses if c.name.startswith("EQ")]
    assert [c.name for c in cases] == ["EQ X", "EQ Y"]
    return project, {c.name: OpenSeesRunner(project).run(c) for c in cases}


def test_the_base_shear_is_the_coefficient_times_the_weight(solved) -> None:  # type: ignore[no-untyped-def]
    project, results = solved
    # 18 x 30 m, 15 %: steel, 0.10 kPa of roof on the slope, and on plan 0.3 of the
    # 10 kg/m² of roof live load (NSCM 9.6 b).
    slope_area = 2 * float(np.hypot(9.0, 0.15 * 9.0)) * 30.0
    weight = _steel_weight(project) + 100.0 * slope_area + 3.0 * KGF * 18.0 * 30.0
    seismic = WarehouseSeismic(method="nscm", a0=0.36667, soil="C", importance_class="II")
    shear = seismic_coefficient(seismic)[0] * weight
    assert shear == pytest.approx(0.572 * weight, rel=1e-3)
    assert -_reaction(results["EQ X"]) == pytest.approx([shear, 0.0, 0.0], rel=1e-8, abs=1e-3)
    assert -_reaction(results["EQ Y"]) == pytest.approx([0.0, shear, 0.0], rel=1e-8, abs=1e-3)


def test_the_frames_sway_and_the_bracing_holds_the_long_direction(solved) -> None:  # type: ignore[no-untyped-def]
    _project, results = solved
    across = _displacements(results["EQ X"])
    along = _displacements(results["EQ Y"])
    assert np.all(np.isfinite(across)) and np.all(np.isfinite(along))
    # Pinned-base portal frames across: a visible sway, not a mechanism.
    assert 0.005 < across[:, 0].max() < 6.0 / 20.0
    assert np.abs(across[:, 1]).max() < 0.1 * across[:, 0].max()
    # X bracing along: much stiffer than the frames.
    assert 0.0 < along[:, 1].max() < 0.5 * across[:, 0].max()


@pytest.mark.parametrize(
    ("fields", "seismic"),
    [
        ({"roof": RoofType.MONO_PITCH, "slope": 0.08}, WarehouseSeismic(roof_live=10.0 * KGF)),
        (
            {"roof_structure": "truss", "truss_depth": 0.8, "bottom_chord_tie_every": 2},
            WarehouseSeismic(method="asce7", sds=0.9, reduction=3.25, importance=1.25),
        ),
        (
            {"n_naves": 2, "span": 10.0, "end_wall_column_spacing": 0.0, "girt_spacing": 0.0},
            WarehouseSeismic(
                method="nscm", a0=0.3, soil="B", importance_class="III", directions=("Y",)
            ),
        ),
    ],
)
def test_other_warehouses_are_in_equilibrium(fields: dict, seismic: WarehouseSeismic) -> None:  # type: ignore[type-arg]
    project = Project(ndm=3, ndf=6)
    values = {
        "span": 16.0, "eave_height": 6.0, "frame_spacing": 5.0, "n_frames": 4,
        "purlin_spacing": 2.0, "girt_spacing": 1.25, "end_wall_column_spacing": 4.0, **fields,
    }  # fmt: skip
    plan = plan_warehouse(
        project,
        WarehouseSpec(**values),
        loads=WarehouseLoads(roof_dead=120.0, seismic=seismic),
    )
    plan.apply(project)
    cases = [c for c in project.analyses if c.name.startswith("EQ")]
    assert len(cases) == len(seismic.directions)
    for case in cases:
        results = OpenSeesRunner(project).run(case)
        pattern = next(p for p in project.load_patterns if p.id == case.pattern_ids[0])  # type: ignore[attr-defined]
        applied = np.sum([load.forces[:3] for load in pattern.nodal_loads], axis=0)  # type: ignore[attr-defined]
        assert np.linalg.norm(applied) > 1e3
        assert -_reaction(results) == pytest.approx(applied, rel=1e-8, abs=1e-4)
        assert np.abs(_displacements(results)[:, :3]).max() < 0.5
