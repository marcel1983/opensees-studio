"""Roof stiffeners and each kind of wall bracing, solved by OpenSees under the wind."""

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


@pytest.mark.parametrize(
    "fields",
    [
        {"roof_stiffeners": "beam", "stiffener_lines": 1},
        {"roof_stiffeners": "truss", "stiffener_depth": 0.8, "wall_bracing_type": "double_x"},
        {"wall_bracing_type": "double_x", "girt_spacing": 1.5},
        {"wall_bracing_type": "moment_frame"},
    ],
    ids=["beam", "truss-double-x", "double-x-on-girt", "moment-frame"],
)
def test_the_building_stands_along_and_across(fields: dict) -> None:  # type: ignore[type-arg]
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="stiffened"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)
    spec = WarehouseSpec(
        span=12.0, eave_height=5.0, frame_spacing=6.0, n_frames=4, slope=0.10, **fields
    )
    loads = WarehouseLoads(
        code="rnc07",
        roof_dead=0.0,
        roof_live=pressure_from_kpa(0.5, units),
        midspan_point=0.0,
        wind=WarehouseWind(),
    )
    plan_warehouse(project, spec, loads=loads).apply(project)
    runner = OpenSeesRunner(project)
    for case in project.analyses:
        if case.name not in ("LIVE", "WIND +X", "WIND +Y"):
            continue
        results = runner.run(case)
        disp = np.array([np.asarray(d).reshape(-1, 6)[-1] for d in results.node_disp.values()])
        assert np.all(np.isfinite(disp)), case.name
        assert np.abs(disp[:, :3]).max() < 0.2, case.name  # a building, not a mechanism
        if case.name == "LIVE":
            reaction = sum(
                np.asarray(r).reshape(-1, 6)[-1][2] for r in results.node_reaction.values()
            )
            assert float(reaction) == pytest.approx(0.5e3 * 12.0 * 18.0, rel=1e-9)
