"""The warehouse's earthquake direction by direction: reduction factor, period, spectrum."""

from __future__ import annotations

import pytest

from opensees_studio.core import nscm, rnc07
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.project import Project
from opensees_studio.core.seismic_codes.asce7_16 import asce7_period
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    WarehouseError,
    WarehouseLoads,
    WarehouseSeismic,
    WarehouseSpec,
    plan_warehouse,
    seismic_coefficient,
    seismic_height,
)
from opensees_studio.core.warehouse_seismic import (
    EN1998_CORNER_PERIODS,
    empirical_period,
    en1998_design_spectrum,
)

SI = UnitSystem.SI_M_N
SPEC = WarehouseSpec(span=20.0, eave_height=6.0, frame_spacing=6.0, n_frames=5, slope=0.1)


def _project(units: UnitSystem = SI) -> Project:
    project = Project(ndm=3, ndf=6)
    project.meta.units = units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)
    return project


def test_each_direction_takes_its_own_reduction_factor() -> None:
    seismic = WarehouseSeismic(method="nscm", a0=0.36667, soil="C", reduction=2.0, reduction_y=4.0)
    assert seismic.reduction_of("X") == 2.0 and seismic.reduction_of("Y") == 4.0
    cx, _ = seismic_coefficient(seismic, "X")
    cy, _ = seismic_coefficient(seismic, "Y")
    assert cx == pytest.approx(2.0 * cy)  # on the plateau, βA0/Ro
    same = WarehouseSeismic(method="nscm", a0=0.36667, soil="C", reduction=2.0)
    assert seismic_coefficient(same, "Y") == seismic_coefficient(same, "X")
    assert seismic_coefficient(seismic) == seismic_coefficient(seismic, "X")


def test_the_mean_roof_height_sets_the_empirical_period() -> None:
    assert seismic_height(SPEC, SI) == pytest.approx(6.5)  # 6 m eave, 1 m rise to the ridge
    assert seismic_height(SPEC, UnitSystem.SI_MM_N) == pytest.approx(6.5e-3)
    seismic = WarehouseSeismic(method="asce7", period_method="period")
    assert empirical_period(seismic, "X", 6.5) == pytest.approx(0.0724 * 6.5**0.8)
    assert empirical_period(seismic, "Y", 6.5) == pytest.approx(0.0488 * 6.5**0.75)
    eurocode = WarehouseSeismic(method="en1998", soil="C", a0=0.15, period_method="period")
    assert empirical_period(eurocode, "X", 6.5) == pytest.approx(0.085 * 6.5**0.75)
    assert empirical_period(eurocode, "Y", 6.5) == pytest.approx(0.05 * 6.5**0.75)
    with pytest.raises(WarehouseError, match="no empirical period"):
        empirical_period(WarehouseSeismic(period_method="period"), "X", 6.5)


def test_rnc07_reads_its_spectrum_at_the_period_typed() -> None:
    with pytest.raises(WarehouseError, match="type the period along X"):
        seismic_coefficient(WarehouseSeismic(period_method="period"), "X", 6.5)
    seismic = WarehouseSeismic(period_method="period", period_x=1.5, period_y=0.3, reduction=2.0)
    s = rnc07.soil_factor("C", "II")
    for direction, period in (("X", 1.5), ("Y", 0.3)):
        c, clause = seismic_coefficient(seismic, direction, 6.5)
        expected = rnc07.static_coefficient(0.3, s, 2.0, period=period).c
        assert c == pytest.approx(expected)
        assert "Ec. 13" in clause and f"T = {period:g} s" in clause
    plateau, _ = seismic_coefficient(WarehouseSeismic(reduction=2.0), "X")
    assert seismic_coefficient(seismic, "X", 6.5)[0] < plateau  # a long period


def test_nscm_takes_the_empirical_period_and_caps_a_longer_one() -> None:
    fields = {"method": "nscm", "a0": 0.36667, "soil": "C", "reduction": 2.0}
    site = nscm.NscmSite(a0=0.36667, site_class="C", risk_category="II", r0=2.0)
    ta = asce7_period("steel_mrf", 6.5)
    c, clause = seismic_coefficient(WarehouseSeismic(**fields, period_method="period"), "X", 6.5)
    assert c == pytest.approx(site.seismic_coefficient(ta)[0])
    assert f"Ta = {ta:.3g} s" in clause
    long = WarehouseSeismic(**fields, period_method="period", period_x=3.0)
    c, clause = seismic_coefficient(long, "X", 6.5)
    assert c == pytest.approx(site.seismic_coefficient(site.cu * ta)[0])
    assert "capped at Cu Ta" in clause


def test_asce7_caps_cs_by_sd1_and_the_period_by_cu_ta() -> None:
    fields = {"method": "asce7", "sds": 1.0, "sd1": 0.3, "reduction": 3.0, "importance": 1.0}
    plateau, _ = seismic_coefficient(WarehouseSeismic(**fields), "X")
    assert plateau == pytest.approx(1.0 / 3.0)
    typed = WarehouseSeismic(**fields, period_method="period", period_x=1.2)
    ta = asce7_period("steel_mrf", 6.5)
    c, clause = seismic_coefficient(typed, "X", 6.5)
    # 1.2 s is above Cu Ta = 1.4 Ta, so T = 1.4 Ta and Cs = SD1 / (T R / Ie).
    assert c == pytest.approx(0.3 / (1.4 * ta * 3.0))
    assert "12.8-3" in clause and "capped at Cu Ta" in clause
    with pytest.raises(WarehouseError, match="SD1"):
        seismic_coefficient(
            WarehouseSeismic(**{**fields, "sd1": 0.0}, period_method="period"), "X", 6.5
        )


@pytest.mark.parametrize(
    ("period", "expected", "branch"),
    [
        (0.0, 0.15 * 1.15 * 2.0 / 3.0, "(3.13)"),
        (0.1, 0.15 * 1.15 * (2.0 / 3.0 + 0.5 * (2.5 / 1.5 - 2.0 / 3.0)), "(3.13)"),
        (0.4, 0.15 * 1.15 * 2.5 / 1.5, "(3.14)"),
        (1.0, 0.15 * 1.15 * 2.5 / 1.5 * 0.6, "(3.15)"),
        (3.0, 0.15 * 1.15 * 2.5 / 1.5 * 0.6 * 2.0 / 9.0, "(3.16)"),
        (10.0, 0.2 * 0.15, "lower bound"),
    ],
)
def test_the_en1998_design_spectrum_has_its_four_branches(
    period: float, expected: float, branch: str
) -> None:
    value, why = en1998_design_spectrum(period, 0.15, 1.15, 1.5, EN1998_CORNER_PERIODS["C"])
    assert value == pytest.approx(expected)
    assert branch in why


def test_en1998_reads_sd_at_the_period_of_each_direction() -> None:
    seismic = WarehouseSeismic(
        method="en1998", a0=0.15, soil="C", reduction=1.5, reduction_y=2.5,
        period_method="period", period_y=0.9,
    )  # fmt: skip
    t1 = 0.085 * 6.5**0.75  # 0.35 s: on the plateau
    cx, _ = seismic_coefficient(seismic, "X", 6.5)
    assert cx == pytest.approx(en1998_design_spectrum(t1, 0.15, 1.15, 1.5, (0.2, 0.6, 2.0))[0])
    cy, clause = seismic_coefficient(seismic, "Y", 6.5)
    assert cy == pytest.approx(0.15 * 1.15 * 2.5 / 2.5 * 0.6 / 0.9)
    assert "(3.15)" in clause and "q = 2.5" in clause


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"reduction_y": -1.0}, "along Y"),
        ({"period_method": "modal"}, "period method"),
        ({"period_x": -0.1}, "period"),
        ({"system_y": "masonry"}, "structural system"),
        ({"sd1": -0.1}, "SD1"),
    ],
)
def test_the_direction_settings_are_checked(fields: dict, message: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(WarehouseError, match=message):
        WarehouseSeismic(**fields)


def test_the_plan_loads_each_direction_with_its_own_coefficient() -> None:
    project = _project()
    seismic = WarehouseSeismic(
        method="nscm", a0=0.36667, soil="C", reduction=2.0, reduction_y=4.0,
        period_method="period",
    )  # fmt: skip
    plan = plan_warehouse(project, SPEC, loads=WarehouseLoads(code="nscm", seismic=seismic))
    plan.apply(project)
    shears = {}
    for pattern in project.load_patterns:
        if pattern.name in ("EQ X", "EQ Y"):
            axis = 0 if pattern.name == "EQ X" else 1
            shears[pattern.name] = sum(load.forces[axis] for load in pattern.nodal_loads)
    cx = seismic_coefficient(seismic, "X", 6.5)[0]
    cy = seismic_coefficient(seismic, "Y", 6.5)[0]
    assert cx != pytest.approx(cy)
    assert shears["EQ X"] / shears["EQ Y"] == pytest.approx(cx / cy, rel=1e-12)
    note = next(n for n in plan.notes if "earthquake case(s)" in n)
    assert f"X: c = {cx:.4g}" in note and f"Y: c = {cy:.4g}" in note
    assert "Mean roof height 6.5 m" in note
