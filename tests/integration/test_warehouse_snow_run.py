"""Ash and snow on the warehouse, solved by OpenSees: what falls on the roof reaches the bases."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from examples.warehouse_ash import build_warehouse_project

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.project import Project
from opensees_studio.core.warehouse import (
    WarehouseLoads,
    WarehouseSnow,
    WarehouseSpec,
    plan_warehouse,
    warehouse_snow_cases,
)
from opensees_studio.core.wind import KGF
from opensees_studio.services.opensees_runner import OpenSeesRunner


def _reactions(results: object) -> dict[int, np.ndarray]:
    return {
        node: np.asarray(r).reshape(-1, 6)[-1][:3]
        for node, r in results.node_reaction.items()  # type: ignore[attr-defined]
    }


def test_the_ash_of_the_example_reaches_the_bases() -> None:
    project = build_warehouse_project()
    cases = {c.name: c for c in project.analyses}
    assert list(cases) == ["DEAD", "ROOF LIVE", "ASH"]
    ash = np.sum(list(_reactions(OpenSeesRunner(project).run(cases["ASH"])).values()), axis=0)
    # 20 kg/m² on the 20 x 30 m of plan.
    assert ash == pytest.approx([0.0, 0.0, 20.0 * KGF * 20.0 * 30.0], rel=1e-9, abs=1e-3)


@pytest.mark.parametrize("method", ["asce7", "en1991"])
def test_the_drift_loads_the_side_it_is_named_after(method: str) -> None:
    project = Project(ndm=3, ndf=6)
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))
    spec = WarehouseSpec(
        span=18.0, eave_height=6.0, frame_spacing=6.0, n_frames=4, slope=0.25,
        purlin_spacing=1.5,
    )  # fmt: skip
    snow = WarehouseSnow(method, 1500.0)
    code = "asce7_lrfd"
    plan = plan_warehouse(project, spec, loads=WarehouseLoads(code=code, snow=snow))
    plan.apply(project)
    project.validate_references()
    loads = {c.name: c for c in warehouse_snow_cases(spec, snow, units)}
    assert list(loads) == ["SNOW", "SNOW +X", "SNOW -X"]
    coords = {n.id: n.coords for n in project.nodes}
    totals = {}
    for case in project.analyses:
        if case.name not in loads:
            continue
        reactions = _reactions(OpenSeesRunner(project).run(case))
        total = np.sum(list(reactions.values()), axis=0)
        assert total == pytest.approx(
            [0.0, 0.0, loads[case.name].resultant() * spec.length], rel=1e-8, abs=1e-3
        )
        left = sum(r[2] for node, r in reactions.items() if coords[node][0] < 1.0)
        totals[case.name] = (left, total[2] - left)
    assert totals["SNOW"][0] == pytest.approx(totals["SNOW"][1], rel=1e-6)
    assert totals["SNOW +X"][1] > 1.2 * totals["SNOW +X"][0]
    assert totals["SNOW -X"] == pytest.approx(totals["SNOW +X"][::-1], rel=1e-6)
