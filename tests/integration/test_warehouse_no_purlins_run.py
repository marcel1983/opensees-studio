"""A warehouse without modelled purlins and girts, solved by OpenSees."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.project import Project, ProjectMeta
from opensees_studio.core.warehouse import (
    WarehouseLoads,
    WarehouseSpec,
    WarehouseWind,
    plan_warehouse,
    pressure_from_kpa,
)
from opensees_studio.services.opensees_runner import OpenSeesRunner


@pytest.mark.parametrize("roof_structure", ["rafter", "truss"])
def test_the_rafters_carry_the_roof_and_the_struts_hold_the_frames(roof_structure: str) -> None:
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="no purlins"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)
    truss = {"roof_structure": "truss", "truss_depth": 1.0} if roof_structure == "truss" else {}
    spec = WarehouseSpec(
        span=12.0,
        eave_height=5.0,
        frame_spacing=6.0,
        n_frames=4,
        slope=0.10,
        girt_spacing=1.5,
        model_purlins=False,
        model_girts=False,
        overhang=1.0,
        **truss,
    )
    loads = WarehouseLoads(
        code="rnc07",
        roof_dead=0.0,
        roof_live=pressure_from_kpa(0.5, units),
        midspan_point=0.0,
        wind=WarehouseWind(),
    )
    plan = plan_warehouse(project, spec, loads=loads)
    plan.apply(project)
    assert not plan.warehouse.members["purlins"] and not plan.warehouse.members["girts"]
    runner = OpenSeesRunner(project)

    live = next(c for c in project.analyses if c.name == "LIVE")
    results = runner.run(live)
    reaction = sum(np.asarray(r).reshape(-1, 6)[-1][2] for r in results.node_reaction.values())
    assert float(reaction) == pytest.approx(0.5e3 * (12.0 + 2.0) * 18.0, rel=1e-9)
    for case in project.analyses:
        if not case.name.startswith("WIND"):
            continue
        disp = np.array(
            [np.asarray(d).reshape(-1, 6)[-1] for d in runner.run(case).node_disp.values()]
        )
        assert np.all(np.isfinite(disp))
        assert np.abs(disp[:, :3]).max() < 0.5, case.name  # a building, not a mechanism
