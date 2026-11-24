"""Tension-only members, solved: an X-braced bay under a sideways push.

The bay is a mechanism without its bracing (the beam is pinned to the columns
and the columns to the ground), so the braces alone hold the push ``P``:

* linear braces share it, about ``P / (2 cos θ)`` each, one pulled and one pushed;
* tension-only braces leave it to the one the push stretches, ``P / cos θ``,
  and the other goes slack (next to nothing, its residual stiffness);
* the push the other way swaps them.

A tension-only brace runs as a truss, so its self weight reaches its joints.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("openseespy")

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    LinearTimeSeries,
    NodalLoad,
    Node,
    PlainLoadPattern,
    Project,
    StaticCase,
)
from opensees_studio.core.geometry.frame_options import EndRelease, FrameReleases
from opensees_studio.services.opensees_runner import OpenSeesRunner

L, H, P = 4.0, 3.0, 10_000.0
PINNED = FrameReleases(i=EndRelease(released=("M2", "M3")), j=EndRelease(released=("M2", "M3")))
#: In the X-Z plane: Y, and the rotations about X and Z, are held everywhere.
PLANE = (False, True, False, True, False, True)
BASE = (True, True, True, True, False, True)


def _bay(*, tension_only: bool, push: float = P, self_weight: float = 0.0) -> Project:
    nodes = [
        Node(id=1, coords=(0.0, 0.0, 0.0), restraint=BASE),
        Node(id=2, coords=(L, 0.0, 0.0), restraint=BASE),
        Node(id=3, coords=(0.0, 0.0, H), restraint=PLANE),
        Node(id=4, coords=(L, 0.0, H), restraint=PLANE),
    ]
    frame = ElasticSection(id=1, E=2e11, A=1e-2, Iz=1e-4, Iy=1e-4, G=8e10, J=1e-5)
    brace = ElasticSection(
        id=2, E=2e11, A=5e-4, Iz=1e-7, Iy=1e-7, G=8e10, J=1e-8, unit_weight=77_000.0
    )
    elements = [
        ElasticBeamColumn(id=1, nodes=(1, 3), section_id=1),
        ElasticBeamColumn(id=2, nodes=(2, 4), section_id=1),
        ElasticBeamColumn(id=3, nodes=(3, 4), section_id=1, releases=PINNED),
        ElasticBeamColumn(
            id=4, nodes=(1, 4), section_id=2, releases=PINNED, tension_only=tension_only
        ),
        ElasticBeamColumn(
            id=5, nodes=(2, 3), section_id=2, releases=PINNED, tension_only=tension_only
        ),
    ]
    project = Project(ndm=3, ndf=6, nodes=nodes, sections=[frame, brace], elements=elements)
    project.time_series.append(LinearTimeSeries(id=1))
    project.load_patterns.append(
        PlainLoadPattern(
            id=1,
            name="PUSH",
            time_series_id=1,
            self_weight=self_weight,
            nodal_loads=[NodalLoad(node_id=3, forces=(push, 0, 0, 0, 0, 0))],
        )
    )
    project.analyses.append(StaticCase(id=1, name="PUSH", pattern_ids=[1], system="UmfPack"))
    return project


def _axial(results, element_id: int) -> float:  # type: ignore[no-untyped-def]
    """Tension positive: ``localForce`` puts ``-N`` at end i."""
    return -float(results.element_forces[element_id][-1][0])


COS = L / math.hypot(L, H)


def test_linear_braces_share_the_push() -> None:
    project = _bay(tension_only=False)
    results = OpenSeesRunner(project).run(project.analyses[0])
    pulled, pushed = _axial(results, 4), _axial(results, 5)
    # About half each (the columns' shortening shifts a little to the pulled one).
    assert pulled == pytest.approx(P / (2 * COS), rel=0.02)
    assert pushed == pytest.approx(-P / (2 * COS), rel=0.02)
    assert (pulled - pushed) * COS == pytest.approx(P, rel=1e-9)


@pytest.mark.parametrize("push", [P, -P])
def test_the_stretched_brace_takes_the_whole_push_and_the_other_goes_slack(push: float) -> None:
    project = _bay(tension_only=True, push=push)
    results = OpenSeesRunner(project).run(project.analyses[0])
    pulled, slack = (4, 5) if push > 0 else (5, 4)
    assert _axial(results, pulled) == pytest.approx(P / COS, rel=1e-4)
    assert abs(_axial(results, slack)) < 1e-4 * P
    # A truss carries no shear or moment: the frame layout, zeros past the axial force.
    assert not any(results.element_forces[pulled][-1][1:6])


def test_a_tension_only_brace_weighs_on_its_joints() -> None:
    project = _bay(tension_only=True, push=0.0, self_weight=1.0)
    results = OpenSeesRunner(project).run(project.analyses[0])
    weight = 2 * 77_000.0 * 5e-4 * math.hypot(L, H)  # the frame's section weighs nothing
    vertical = sum(results.node_reaction[n][-1][2] for n in (1, 2))
    assert vertical == pytest.approx(weight, rel=1e-9)


def test_a_warehouse_with_tension_only_braces_holds_each_x_with_one_diagonal() -> None:
    """The warehouse wizard's braces, under a combination with the wind along Y.

    The wind along the building reaches the roof and wall bracing of the braced
    bays; in its combination case one diagonal of each X is pulled and the other
    is slack, and the combination reads that case.
    """
    from opensees_studio.core import ProjectMeta
    from opensees_studio.core.default_materials import default_materials
    from opensees_studio.core.defaults import ensure_dead_load_case
    from opensees_studio.core.warehouse import (
        CASE_SYSTEM,
        CODE_PRESETS,
        WarehouseLoads,
        WarehouseSpec,
        WarehouseWind,
        force_from_kn,
        plan_warehouse,
        pressure_from_kpa,
    )
    from opensees_studio.core.wind import rnc07_regional_speed

    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="tension-only warehouse"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)
    spec = WarehouseSpec(
        span=12.0, eave_height=5.0, frame_spacing=6.0, n_frames=3, tension_only_braces=True
    )
    preset = CODE_PRESETS["rnc07"]
    loads = WarehouseLoads(
        code="rnc07",
        roof_dead=pressure_from_kpa(0.10, units),
        roof_live=pressure_from_kpa(preset.roof_live_kpa, units),
        midspan_point=force_from_kn(preset.midspan_point_kn, units),
        wind=WarehouseWind(
            method="rnc07", speed=rnc07_regional_speed(2, "B"), exposure="R2", topography="T3"
        ),
    )
    plan = plan_warehouse(project, spec, loads=loads)
    plan.apply(project)
    combination = next(c for c in project.combinations if c.name == "0.9CM+1.6Pz:WIND +Y")
    (term,) = combination.terms
    case = next(c for c in project.analyses if c.id == term.ref_id)
    assert case.name == "Comb: 0.9CM+1.6Pz:WIND +Y" and case.system == CASE_SYSTEM

    results = OpenSeesRunner(project).run(case)

    for group in ("roof_bracing", "wall_bracing"):
        ids = plan.warehouse.members[group]
        assert ids and len(ids) % 2 == 0
        pairs = list(zip(ids[::2], ids[1::2], strict=True))  # the two diagonals of each X
        for a, b in pairs:
            pulled, slack = sorted((_axial(results, a), _axial(results, b)), reverse=True)
            assert pulled > 0.0
            assert abs(slack) < 1e-3 * pulled, (group, a, b, pulled, slack)
