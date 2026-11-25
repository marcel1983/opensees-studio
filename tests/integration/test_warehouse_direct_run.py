"""The warehouse's direct analysis cases, solved by OpenSees: second order, notional loads."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from opensees_studio.core.analysis import StaticCase
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.project import Project
from opensees_studio.core.warehouse import (
    WarehouseLoads,
    WarehouseSpec,
    WarehouseWind,
    plan_warehouse,
)
from opensees_studio.services.opensees_runner import OpenSeesRunner


def _reaction(results: object) -> np.ndarray:
    return np.sum(
        [np.asarray(r).reshape(-1, 6)[-1][:3] for r in results.node_reaction.values()],  # type: ignore[attr-defined]
        axis=0,
    )


def _sway(project: Project, results: object) -> float:
    """The mean sway along X of the eaves: the tops of the side columns."""
    eaves = [
        n.id for n in project.nodes if abs(n.coords[2] - 6.0) < 1e-9 and n.coords[0] in (0.0, 14.0)
    ]
    disp = results.node_disp  # type: ignore[attr-defined]
    return float(np.mean([np.asarray(disp[i]).reshape(-1, 6)[-1][0] for i in eaves]))


@pytest.fixture(scope="module")
def warehouse() -> Project:
    project = Project(ndm=3, ndf=6)
    project.materials.extend(default_materials(project.next_material_id(), project.meta.units))
    ensure_dead_load_case(project)
    spec = WarehouseSpec(
        span=14.0, eave_height=6.0, frame_spacing=5.0, n_frames=3, girt_spacing=1.5,
        roof_tension_only=True, wall_tension_only=True,
    )  # fmt: skip
    loads = WarehouseLoads(
        code="rnc07", roof_dead=150.0, roof_live=400.0, wind=WarehouseWind(speed=30.0),
        direct_analysis=True,
    )  # fmt: skip
    plan_warehouse(project, spec, loads=loads).apply(project)
    return project


def test_a_gravity_case_holds_with_its_notional_load_sideways(warehouse: Project) -> None:
    case = next(c for c in warehouse.analyses if c.name == "DAM 1.2CM+1.6CV N+X")
    assert isinstance(case, StaticCase)
    results = OpenSeesRunner(warehouse).run(case)
    reaction = -_reaction(results)
    # The notional load 0.003 Yi along +X, Yi the factored gravity above the bases.
    note = next(n for n in results.warnings if n.startswith("Notional loads along +X"))  # type: ignore[attr-defined]
    assert "Ni = 0.003 Yi" in note
    total = float(note.rsplit(", ", 1)[1].split(" ")[0])
    assert reaction[0] == pytest.approx(total, rel=1e-6)
    assert 0.0025 * abs(reaction[2]) < reaction[0] < 0.003 * abs(reaction[2])
    assert reaction[1] == pytest.approx(0.0, abs=1e-6 * abs(reaction[2]))


def test_the_second_order_wind_case_sways_more_than_the_first_order_sum(warehouse: Project) -> None:
    combination = next(
        c for c in warehouse.combinations if "WIND +X" in c.name and c.name.startswith("0.9")
    )
    second = next(c for c in warehouse.analyses if c.id == combination.terms[0].ref_id)
    assert isinstance(second, StaticCase) and second.p_delta
    results = OpenSeesRunner(warehouse).run(second)
    reaction = -_reaction(results)
    assert reaction[0] > 0.0  # the wind and its notional load push towards +X
    linear = second.model_copy(
        update={
            "p_delta": False, "stiffness_factor": 1.0, "notional_ratio": 0.0,
            "algorithm": "Newton", "name": "first order",
        }
    )  # fmt: skip
    first = OpenSeesRunner(warehouse).run(linear)
    # Reduced stiffness and P-Delta: more sway than the first-order elastic one.
    sway, linear_sway = _sway(warehouse, results), _sway(warehouse, first)
    assert linear_sway > 0.0
    assert sway > 1.2 * linear_sway  # 1 / 0.8, and P-Delta on top
    assert sway < 0.1
