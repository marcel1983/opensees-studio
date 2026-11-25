"""A warehouse with eave overhangs, solved by OpenSees: the overhangs carry their roof."""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.project import Project, ProjectMeta
from opensees_studio.core.warehouse import (
    WarehouseLoads,
    WarehouseSpec,
    plan_warehouse,
    pressure_from_kpa,
)
from opensees_studio.services.opensees_runner import OpenSeesRunner


def test_the_overhangs_carry_their_roof_to_the_frames() -> None:
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="overhangs"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)
    spec = WarehouseSpec(
        span=12.0, eave_height=5.0, frame_spacing=6.0, n_frames=3, slope=0.10, overhang=1.5
    )
    live_kpa = 0.5
    loads = WarehouseLoads(
        code="rnc07", roof_dead=0.0, roof_live=pressure_from_kpa(live_kpa, units), midspan_point=0.0
    )
    plan = plan_warehouse(project, spec, loads=loads)
    plan.apply(project)
    live = next(c for c in project.analyses if c.name == "LIVE")
    results = OpenSeesRunner(project).run(live)

    reaction = sum(np.asarray(r).reshape(-1, 6)[-1][2] for r in results.node_reaction.values())
    plan_area = (12.0 + 2 * 1.5) * 12.0
    assert float(reaction) == pytest.approx(live_kpa * 1e3 * plan_area, rel=1e-9)
    # The cantilever at the middle frame takes the purlins of the two half bays
    # beside it, two lines at 0.75 and 1.5 m: the half space next to the wall
    # goes to the eave purlin, so its shear at the eave is the roof from 0.375 m
    # to the tip over one bay.
    nodes = {n.id: n for n in project.nodes}
    overhangs = next(g for g in project.groups if g.name.startswith("Overhangs ")).element_ids
    roots = [
        e
        for e in project.elements
        if e.id in overhangs
        and nodes[e.nodes[0]].coords[0] == 0.0
        and nodes[e.nodes[0]].coords[1] == 6.0
    ]
    assert len(roots) == 1
    force = np.asarray(results.element_forces[roots[0].id]).reshape(-1, 12)[-1]
    assert math.hypot(*force[0:3]) == pytest.approx(live_kpa * 1e3 * 1.125 * 6.0, rel=1e-6)
    # Its moment at the eave: 375 N/m at 0.75 m and 187.5 N/m at 1.5 m, over 6 m.
    moment = math.hypot(*force[3:6])
    assert moment == pytest.approx(6.0 * (375.0 * 0.75 + 187.5 * 1.5), rel=1e-6)
