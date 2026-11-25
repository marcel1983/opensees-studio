"""The warehouse's combinations as the wizard shows and edits them."""

from __future__ import annotations

import dataclasses

import pytest

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.project import Project
from opensees_studio.core.warehouse import (
    PlannedCombination,
    WarehouseError,
    WarehouseLoads,
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


def _terms(project: Project, plan, name: str) -> dict[str, float]:  # type: ignore[no-untyped-def]
    cases = {c.id: c.name for c in [*project.analyses, *plan.cases]}
    combination = next(c for c in plan.combinations if c.name == name)
    return {cases[t.ref_id]: t.factor for t in combination.terms}


def test_the_plan_keeps_the_code_combinations_by_case_name() -> None:
    project = _project()
    loads = WarehouseLoads(code="rnc07", roof_dead=100.0, roof_live=400.0)
    plan = plan_warehouse(project, SPEC, loads=loads)
    code = plan.code_combinations
    assert [c.name for c in code] == ["1.4CM", "1.2CM+1.6CV"]
    assert code[1].factors == (("DEAD", 1.2), ("LIVE", 1.6))
    assert code[1].text() == "1.2 DEAD + 1.6 LIVE"
    assert code[1].factor("LIVE") == 1.6 and code[1].factor("WIND") == 0.0
    assert PlannedCombination("x", (("DEAD", 0.9), ("EQ X", -1.0))).text() == "0.9 DEAD - 1 EQ X"
    # Unedited, the plan makes them, and the envelope over them.
    assert [c.name for c in plan.combinations] == [
        *(c.name for c in code),
        "RNC-07 ultimate envelope",
    ]


def test_the_edited_combinations_replace_those_of_the_code() -> None:
    project = _project()
    loads = WarehouseLoads(code="rnc07", roof_dead=100.0, roof_live=400.0)
    code = plan_warehouse(project, SPEC, loads=loads).code_combinations
    edited = (
        dataclasses.replace(code[1], factors=(("DEAD", 1.25), ("LIVE", 1.5))),
        PlannedCombination("Service", (("DEAD", 1.0), ("LIVE", 1.0), ("DEAD", 0.0))),
    )
    plan = plan_warehouse(
        project, SPEC, loads=dataclasses.replace(loads, edited_combinations=edited)
    )
    assert plan.code_combinations == code  # still the code's, for the wizard
    names = [c.name for c in plan.combinations]
    assert names == ["1.2CM+1.6CV", "Service", "RNC-07 ultimate envelope"]
    assert _terms(project, plan, "1.2CM+1.6CV") == {"DEAD": 1.25, "LIVE": 1.5}
    assert _terms(project, plan, "Service") == {"DEAD": 1.0, "LIVE": 1.0}  # no zero term
    envelope = plan.combinations[-1]
    assert [t.ref_id for t in envelope.terms] == [c.id for c in plan.combinations[:2]]
    # None at all is a choice too.
    bare = plan_warehouse(project, SPEC, loads=dataclasses.replace(loads, edited_combinations=()))
    assert bare.combinations == []


def test_the_edits_are_kept_when_each_combination_is_its_own_case() -> None:
    project = _project()
    loads = WarehouseLoads(code="rnc07", roof_dead=100.0, wind=WarehouseWind(speed=30.0))
    spec = dataclasses.replace(SPEC, roof_tension_only=True)
    code = plan_warehouse(project, spec, loads=loads).code_combinations
    wind = next(c for c in code if "WIND" in c.text())
    edited = (dataclasses.replace(wind, name="Mine", factors=((wind.factors[0][0], 1.0),)),)
    plan = plan_warehouse(
        project, spec, loads=dataclasses.replace(loads, edited_combinations=edited)
    )
    assert [c.name for c in plan.combinations] == ["Mine"]
    assert [c.name for c in plan.cases if c.name.startswith("Comb:")] == ["Comb: Mine"]


@pytest.mark.parametrize(
    ("edited", "message"),
    [
        ((PlannedCombination(" ", (("DEAD", 1.0),)),), "needs a name"),
        ((PlannedCombination("A", (("DEAD", 1.0),)),) * 2, "Two combinations"),
        ((PlannedCombination("A", (("SNOW", 1.0),)),), "not a load case"),
        ((PlannedCombination("A", (("DEAD", 0.0),)),), "no load case"),
    ],
)
def test_combinations_that_cannot_be_made_are_refused(edited: tuple, message: str) -> None:  # type: ignore[type-arg]
    loads = WarehouseLoads(code="rnc07", roof_dead=100.0, edited_combinations=edited)
    with pytest.raises(WarehouseError, match=message):
        plan_warehouse(_project(), SPEC, loads=loads)
