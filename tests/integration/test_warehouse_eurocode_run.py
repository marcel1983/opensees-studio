"""The Eurocode warehouse, solved by OpenSees: the zoned wind pressures reach the bases."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from examples.warehouse_eurocode import build_warehouse_project

from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.project import Project
from opensees_studio.core.warehouse import WarehouseSpec, WarehouseWind, warehouse_wind_cases
from opensees_studio.core.wind import en1991_peak_pressure, en1991_wall_cp
from opensees_studio.services.opensees_runner import OpenSeesRunner


def _reaction(results: object) -> np.ndarray:
    return np.sum(
        [np.asarray(r).reshape(-1, 6)[-1][:3] for r in results.node_reaction.values()],  # type: ignore[attr-defined]
        axis=0,
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


def test_the_eurocode_wind_of_the_example_reaches_the_bases() -> None:
    project = build_warehouse_project()
    names = [c.name for c in project.analyses]
    assert names == [
        "DEAD", "ROOF LIVE",
        *(f"WIND {d} {label}" for d in ("+X", "-X") for label in "ABCD"),
        *(f"WIND {d} {label}" for d in ("+Y", "-Y") for label in "AB"),
        "SNOW", "SNOW +X", "SNOW -X",
    ]  # fmt: skip
    cases = {c.name: c for c in project.analyses}
    reactions = {
        name: -_reaction(OpenSeesRunner(project).run(cases[name]))
        for name in ("WIND +X A", "WIND +X C", "WIND -X C", "WIND +Y A", "WIND +Y B")
    }
    for name, reaction in reactions.items():
        assert reaction == pytest.approx(_applied(project, name), rel=1e-9, abs=1e-4)

    # 20 x 30 m, eave 6 m, ridge 8 m; vb = 26 m/s in terrain II.
    spec = WarehouseSpec(span=20.0, eave_height=6.0, frame_spacing=6.0, n_frames=6, slope=0.2)
    wind = WarehouseWind(method="en1991", speed=26.0, exposure="II")
    pressures = {c.name: c for c in warehouse_wind_cases(spec, wind, project.meta.units)}
    qp = en1991_peak_pressure(8.0, 26.0)
    # Along the ridge the end walls push (the girts send the lowest 0.75 m into
    # the ground) and the whole roof lifts; the internal pressure only changes the lift.
    windward, leeward = en1991_wall_cp(8.0 / 30.0)
    end_wall = 20.0 * 6.0 + 20.0 * 2.0 / 2.0 - 20.0 * 0.75
    for name in ("WIND +Y A", "WIND +Y B"):
        zones = pressures[name].roof[0].zones
        assert zones is not None
        assert reactions[name] == pytest.approx(
            [0.0, qp * (windward - leeward) * end_wall, -zones.mean(0.0, 20.0, 0.0, 30.0) * 600.0],
            rel=1e-9,
            abs=1e-4,
        )
    assert reactions["WIND +Y A"][2] - reactions["WIND +Y B"][2] == pytest.approx(0.5 * qp * 600.0)
    # Across the ridge, case C pushes the windward slope down and pulls the other up.
    zones = pressures["WIND +X C"].roof[0].zones
    assert zones is not None
    on_windward = zones.mean(0.0, 10.0, 0.0, 30.0)
    on_leeward = zones.mean(10.0, 20.0, 0.0, 30.0)
    windward, leeward = en1991_wall_cp(8.0 / 20.0)
    assert reactions["WIND +X C"] == pytest.approx(
        [
            qp * (windward - leeward) * (6.0 - 0.75) * 30.0
            + (on_windward - on_leeward) * 2.0 * 30.0,
            0.0,
            -(on_windward + on_leeward) * 10.0 * 30.0,
        ],
        rel=1e-9,
        abs=1e-4,
    )
    assert reactions["WIND -X C"] == pytest.approx(
        reactions["WIND +X C"] * [-1.0, 1.0, 1.0], rel=1e-9, abs=1e-4
    )
