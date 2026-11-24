"""Ash and snow on the warehouse: the cases, the loads on the purlins, the combinations."""

from __future__ import annotations

import numpy as np
import pytest

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import make_load_cases
from opensees_studio.core.frames import RoofType
from opensees_studio.core.project import Project
from opensees_studio.core.snow import ASH_LOAD_KPA
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    SNOW_METHODS,
    WarehouseError,
    WarehouseLoads,
    WarehouseSnow,
    WarehouseSpec,
    build_warehouse,
    plan_warehouse,
    pressure_from_kpa,
    roof_pressure_loads,
    snow_loads,
    warehouse_snow_cases,
)
from opensees_studio.core.wind import KGF

SECTIONS = {"column": 1, "rafter": 2, "purlin": 3, "girt": 4, "brace": 5, "end_column": 6}
SI = UnitSystem.SI_M_N
ASH = 20.0 * KGF  # N/m²


def _spec(**fields):  # type: ignore[no-untyped-def]
    values = {
        "span": 20.0, "eave_height": 6.0, "frame_spacing": 6.0, "n_frames": 4, "slope": 0.2,
        "purlin_spacing": 1.5, **fields,
    }  # fmt: skip
    return WarehouseSpec(**values)


def _project(units: UnitSystem = SI) -> Project:
    project = Project(ndm=3, ndf=6)
    project.meta.units = units
    project.materials.extend(default_materials(project.next_material_id(), units))
    return project


def _vertical(warehouse, loads) -> float:  # type: ignore[no-untyped-def]
    """Total load of uniform purlin loads (they are vertical: the norm is the load)."""
    nodes = {n.id: np.asarray(n.coords) for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    return sum(
        float(np.hypot(load.wy, load.wz))
        * float(np.linalg.norm(np.subtract(*(nodes[n] for n in elements[load.element_id].nodes))))
        for load in loads
    )


def _snow_ids(plan) -> set[int]:  # type: ignore[no-untyped-def]
    return {c.id for c in plan.cases if c.name.startswith(("SNOW", "ASH"))}


def test_the_methods_and_what_each_code_starts_with() -> None:
    assert list(SNOW_METHODS) == ["ash", "asce7", "en1991"]
    assert {key: preset.snow_method for key, preset in CODE_PRESETS.items()} == {
        "rnc07": "ash", "nscm": "ash", "asce7_lrfd": "asce7", "asce7_asd": "asce7"
    }  # fmt: skip
    assert pytest.approx(ASH / 1e3) == ASH_LOAD_KPA


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"method": "hail"}, "snow method"),
        ({"ground": -1.0}, "positive"),
        ({"exposure": 0.0}, "Ce, Ct and Is"),
        ({"importance": -1.0}, "Ce, Ct and Is"),
    ],
)
def test_snow_settings_are_checked(fields: dict, message: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(WarehouseError, match=message):
        WarehouseSnow(**fields)


@pytest.mark.parametrize(
    ("fields", "method", "names"),
    [
        ({}, "ash", ["ASH"]),
        ({}, "asce7", ["SNOW", "SNOW +X", "SNOW -X"]),
        ({}, "en1991", ["SNOW", "SNOW +X", "SNOW -X"]),
        # Naves share one roof: two of them are still one gable, without a valley.
        ({"n_naves": 2}, "asce7", ["SNOW", "SNOW +X", "SNOW -X"]),
        ({"n_naves": 2}, "en1991", ["SNOW", "SNOW +X", "SNOW -X"]),
        ({"roof": RoofType.MONO_PITCH}, "en1991", ["SNOW"]),
        ({"n_naves": 2, "roof": RoofType.MONO_PITCH}, "asce7", ["SNOW"]),
    ],
)
def test_the_cases_follow_the_roof_and_load_the_purlins_with_all_of_it(
    fields: dict,
    method: str,
    names: list[str],  # type: ignore[type-arg]
) -> None:
    spec = _spec(**fields)
    warehouse = build_warehouse(spec, SECTIONS, first_node_id=1, first_element_id=1)
    cases = warehouse_snow_cases(spec, WarehouseSnow(method, 1500.0), SI)
    assert [c.name for c in cases] == names
    # The first case is uniform: the same loads as a live load of that value.
    uniform = cases[0].points[0][1]
    mine = snow_loads(warehouse, cases[0])
    theirs = roof_pressure_loads(warehouse, uniform, projected=True)
    assert [(a.element_id, a.wy, a.wz) for a in mine] == [
        (b.element_id, pytest.approx(b.wy), pytest.approx(b.wz)) for b in theirs
    ]
    # Every case puts on the purlins what falls on the plan of the roof.
    for case in cases:
        assert _vertical(warehouse, snow_loads(warehouse, case)) == pytest.approx(
            case.resultant() * spec.length, rel=1e-9
        )
    if method == "en1991" and names[-1] == "SNOW -X":
        # Half the snow on the +X slope, all of it on the other.
        assert cases[2].resultant() == pytest.approx(0.75 * cases[0].resultant())


def test_no_load_no_case() -> None:
    spec = _spec()
    assert warehouse_snow_cases(spec, WarehouseSnow("asce7", 0.0), SI) == []
    plan = plan_warehouse(_project(), spec, loads=WarehouseLoads(snow=WarehouseSnow("ash", 0.0)))
    assert [c.name for c in plan.cases] == ["DEAD"]
    plain = plan_warehouse(_project(), spec, loads=WarehouseLoads(roof_live=100.0))
    assert not _snow_ids(plain)


def test_nscm_has_a_load_of_its_own_for_the_ash() -> None:
    project = _project()
    loads = WarehouseLoads(
        code="nscm", roof_dead=100.0, roof_live=98.0, snow=WarehouseSnow("ash", ASH)
    )
    plan = plan_warehouse(project, _spec(), loads=loads)
    assert [c.name for c in plan.cases] == ["DEAD", "ROOF LIVE", "ASH"]
    ash = next(c for c in plan.cases if c.name == "ASH")
    field, items = next(
        (field, items) for pid, field, items in plan.pattern_loads if pid == ash.pattern_ids[0]
    )
    assert field == "element_loads"
    assert _vertical(plan.warehouse, items) == pytest.approx(ASH * 20.0 * 18.0)
    # NSCM 7.5.1: 1.2CM + 1.6(CVT or CCV): the ash leads one combination.
    names = [c.name for c in plan.combinations]
    assert "1.2CM+1.6CCV" in names and "1.2CM+1.6CVT" in names
    assert any("1 case(s) by Volcanic ash" in note for note in plan.notes)
    plan.apply(project)
    project.validate_references()


def test_rnc07_takes_the_ash_with_the_live_load() -> None:
    loads = WarehouseLoads(
        code="rnc07", roof_dead=100.0, roof_live=98.0, snow=WarehouseSnow("ash", ASH)
    )
    plan = plan_warehouse(_project(), _spec(), loads=loads)
    live, ash = (next(c.id for c in plan.cases if c.name == name) for name in ("LIVE", "ASH"))
    # Art. 14: "adicional a la carga viva". Art. 15 has no ash: it goes as CV.
    gravity = next(c for c in plan.combinations if c.name == "1.2CM+1.6CV")
    assert {t.ref_id: t.factor for t in gravity.terms}[live] == 1.6
    assert {t.ref_id: t.factor for t in gravity.terms}[ash] == 1.6
    # A snow with drifts under a code that has no snow load: the balanced case only.
    snowy = plan_warehouse(
        _project(), _spec(), loads=WarehouseLoads(code="rnc07", snow=WarehouseSnow("en1991", 1e3))
    )
    assert [c.name for c in snowy.cases] == ["DEAD", "SNOW"]
    assert any("only the balanced case SNOW" in note for note in snowy.notes)


def test_balanced_and_drifted_snow_never_share_a_combination() -> None:
    from opensees_studio.core.warehouse import WarehouseSeismic, WarehouseWind

    loads = WarehouseLoads(
        code="asce7_lrfd",
        roof_dead=100.0,
        roof_live=957.6,
        snow=WarehouseSnow("asce7", 1436.0),
        wind=WarehouseWind(method="asce7", speed=50.0, exposure="C"),
        seismic=WarehouseSeismic(method="asce7", sds=0.9, reduction=3.0),
    )
    plan = plan_warehouse(_project(), _spec(), loads=loads)
    snow = _snow_ids(plan)
    assert len(snow) == 3
    assert any("3 case(s) by ASCE 7-16 chapter 7" in note for note in plan.notes)
    used: set[int] = set()
    for combination in plan.combinations:
        if combination.combination_type == "Envelope":
            continue
        here = snow & {t.ref_id for t in combination.terms}
        assert len(here) <= 1, combination.name
        used |= here
    assert used == snow
    names = [c.name for c in plan.combinations]
    assert len(names) == len(set(names))


def test_a_taken_name_gets_a_number() -> None:
    project = _project()
    series, patterns, cases = make_load_cases(project, ["ASH"])
    project.time_series.extend(series)
    project.load_patterns.extend(patterns)
    project.analyses.extend(cases)
    plan = plan_warehouse(
        project, _spec(), loads=WarehouseLoads(code="nscm", snow=WarehouseSnow("ash", ASH))
    )
    assert [c.name for c in plan.cases] == ["DEAD", "ASH (2)"]


def test_the_loads_follow_the_project_units() -> None:
    spec = _spec()
    si = warehouse_snow_cases(spec, WarehouseSnow("asce7", 1436.0), SI)
    kn_units = UnitSystem.SI_M_KN
    kn = warehouse_snow_cases(
        spec, WarehouseSnow("asce7", pressure_from_kpa(1.436, kn_units)), kn_units
    )
    for a, b in zip(si, kn, strict=True):
        assert [x for x, _p in b.points] == pytest.approx([x for x, _p in a.points])
        assert [p for _x, p in b.points] == pytest.approx([p / 1e3 for _x, p in a.points])
    # In feet the roof is the same roof: the drift is as wide in metres.
    feet = UnitSystem.US_FT_KIP
    us_spec = _spec(span=20.0 / 0.3048, eave_height=20.0, frame_spacing=20.0, purlin_spacing=5.0)
    us = warehouse_snow_cases(us_spec, WarehouseSnow("asce7", pressure_from_kpa(1.436, feet)), feet)
    assert [x * 0.3048 for x, _p in us[1].points] == pytest.approx([x for x, _p in si[1].points])
    assert us[1].peak == pytest.approx(pressure_from_kpa(si[1].peak / 1e3, feet))
