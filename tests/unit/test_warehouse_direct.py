"""The direct analysis method of AISC 360 on a generated warehouse, and its AISC 341 systems."""

from __future__ import annotations

import pytest

from opensees_studio.core.analysis import StaticCase
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.project import Project
from opensees_studio.core.warehouse import (
    CASE_SYSTEM,
    WarehouseError,
    WarehouseLoads,
    WarehouseSeismic,
    WarehouseSpec,
    WarehouseWind,
    plan_warehouse,
)

SPEC = WarehouseSpec(span=12.0, eave_height=5.0, frame_spacing=5.0, n_frames=3)


def _project() -> Project:
    project = Project(ndm=3, ndf=6)
    project.materials.extend(default_materials(project.next_material_id(), project.meta.units))
    ensure_dead_load_case(project)
    return project


def _plan(**fields):  # type: ignore[no-untyped-def]
    project = _project()
    values = {"code": "rnc07", "roof_dead": 100.0, "roof_live": 400.0, **fields}
    return project, plan_warehouse(project, SPEC, loads=WarehouseLoads(**values))


def test_a_gravity_combination_becomes_four_cases_with_notional_loads() -> None:
    project, plan = _plan(direct_analysis=True)
    by_id = {c.id: c for c in [*project.analyses, *plan.cases]}
    combination = next(c for c in plan.combinations if c.name == "1.2CM+1.6CV")
    assert combination.combination_type == "Envelope"
    cases = [by_id[t.ref_id] for t in combination.terms]
    assert [c.name for c in cases] == [f"DAM 1.2CM+1.6CV N{d}" for d in ("+X", "-X", "+Y", "-Y")]
    for case, direction in zip(cases, ("+X", "-X", "+Y", "-Y"), strict=True):
        assert isinstance(case, StaticCase)
        assert case.p_delta and case.stiffness_factor == 0.8 and case.algorithm == "Newton"
        assert case.notional_ratio == pytest.approx(0.003)  # 0.002 + 0.001 for τb = 1
        assert case.notional_direction == direction
        assert case.direct_analysis is not None and case.direct_analysis.order == "second"
        assert case.system == CASE_SYSTEM and case.n_steps == 10
        assert sorted(case.pattern_factors) == [1.2, 1.6]
    envelope = plan.combinations[-1]
    assert envelope.name == "RNC-07 ultimate envelope"
    assert plan.design is not None and plan.design.stability_method == "direct"
    assert any("Chapter C" in note for note in plan.notes)


def test_a_wind_combination_is_one_case_with_its_notional_load_along_the_wind() -> None:
    project, plan = _plan(direct_analysis=True, wind=WarehouseWind(speed=30.0))
    by_id = {c.id: c for c in [*project.analyses, *plan.cases]}
    for combination in plan.combinations:
        if "WIND" not in combination.name or combination.combination_type != "LinearAdd":
            continue
        (term,) = combination.terms
        case = by_id[term.ref_id]
        assert case.name == f"DAM {combination.name}"
        assert case.direct_analysis.lateral and case.notional_ratio == pytest.approx(0.001)
        wind = next(w for w in ("+X", "-X", "+Y", "-Y") if f"WIND {w}" in combination.name)
        assert case.notional_direction == wind


def test_an_earthquake_combination_follows_the_sign_of_its_main_direction() -> None:
    seismic = WarehouseSeismic(method="nscm", a0=0.36667, soil="C")
    project, plan = _plan(code="nscm", direct_analysis=True, seismic=seismic)
    by_id = {c.id: c for c in [*project.analyses, *plan.cases]}
    seen = set()
    for combination in plan.combinations:
        if "EQ" not in combination.name or combination.combination_type != "LinearAdd":
            continue
        case = by_id[combination.terms[0].ref_id]
        main = "X" if combination.name.index("EQ X") < combination.name.index("EQ Y") else "Y"
        assert case.notional_direction[-1] == main
        seen.add(case.notional_direction)
    assert seen == {"+X", "-X", "+Y", "-Y"}


def test_the_braces_in_tension_only_take_the_direct_analysis_cases() -> None:
    project = _project()
    spec = WarehouseSpec(
        span=12.0, eave_height=5.0, frame_spacing=5.0, n_frames=3, roof_tension_only=True
    )
    loads = WarehouseLoads(code="rnc07", roof_dead=100.0, direct_analysis=True)
    plan = plan_warehouse(project, spec, loads=loads)
    assert not any(c.name.startswith("Comb: ") for c in plan.cases)
    assert any(c.name.startswith("DAM ") for c in plan.cases)


def test_the_aisc_341_systems_go_to_the_design_settings() -> None:
    plan = _plan(seismic_system_x="OMF", seismic_system_y="OCBF")[1]
    assert plan.design is not None
    assert (plan.design.seismic_system, plan.design.seismic_system_y) == ("OMF", "OCBF")
    same = _plan(seismic_system_x="IMF")[1]
    assert (same.design.seismic_system, same.design.seismic_system_y) == ("IMF", None)
    none = _plan(design_lengths=False)[1]
    assert none.design is None


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"code": "asce7_asd", "direct_analysis": True}, "LRFD"),
        ({"seismic_system_x": "XBF"}, "AISC 341"),
        ({"seismic_system_y": "moment"}, "AISC 341"),
    ],
)
def test_what_cannot_be_designed_is_refused(fields: dict, message: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(WarehouseError, match=message):
        WarehouseLoads(**fields)
