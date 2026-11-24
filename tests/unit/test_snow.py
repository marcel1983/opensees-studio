"""Snow and volcanic ash on a roof: the loads of ASCE 7-16, EN 1991-1-3 and RNC-07 / NSCM."""

from __future__ import annotations

import math

import pytest

from opensees_studio.core.snow import (
    ASCE_EXPOSURE,
    ASCE_IMPORTANCE,
    ASCE_THERMAL,
    ASH_LOAD_KPA,
    EN_EXPOSURE,
    SnowCase,
    SnowError,
    asce7_drift_height,
    asce7_flat_roof_load,
    asce7_minimum_load,
    asce7_slope_factor,
    asce7_snow_cases,
    asce7_snow_density,
    ash_cases,
    en1991_mu1,
    en1991_mu2,
    en1991_snow_cases,
    roof_planes,
)

PSF = 0.04788026
FT = 0.3048
PCF = 0.1570875


# ───────────────────────────── the roof and a case ─────────────────────────────
def test_the_planes_of_a_roof() -> None:
    gable = roof_planes(20.0, 2, "gable")
    assert [(p.x0, p.x1, p.rise) for p in gable] == [
        (0.0, 10.0, 1), (10.0, 20.0, -1), (20.0, 30.0, 1), (30.0, 40.0, -1)
    ]  # fmt: skip
    assert [(p.x0, p.x1, p.rise) for p in roof_planes(12.0, 2, "mono")] == [
        (0.0, 12.0, 1), (12.0, 24.0, 1)
    ]  # fmt: skip
    assert [(p.x0, p.x1, p.rise) for p in roof_planes(12.0, 1, "flat")] == [(0.0, 12.0, 0)]
    for arguments in ((0.0, 1, "gable"), (10.0, 0, "gable"), (10.0, 1, "dome")):
        with pytest.raises(SnowError):
            roof_planes(*arguments)


def test_a_case_is_piecewise_linear_with_steps() -> None:
    case = SnowCase("x", ((0.0, 1.0), (10.0, 1.0), (10.0, 3.0), (20.0, 5.0)))
    assert case.at(5.0) == 1.0
    assert case.at(10.0) == 3.0  # at a step, the far side
    assert case.at(15.0) == 4.0
    assert case.at(25.0) == 0.0
    assert case.mean(0.0, 10.0) == pytest.approx(1.0)
    assert case.mean(10.0, 20.0) == pytest.approx(4.0)
    assert case.mean(20.0, 10.0) == pytest.approx(4.0)
    assert case.mean(5.0, 15.0) == pytest.approx((5.0 * 1.0 + 5.0 * 3.5) / 10.0)
    assert case.mean(15.0, 25.0) == pytest.approx(5.0 * 4.5 / 10.0)  # nothing beyond the eave
    assert case.mean(7.0, 7.0) == 1.0
    assert case.peak == 5.0
    assert case.resultant() == pytest.approx(10.0 * 1.0 + 10.0 * 4.0)


def test_what_is_not_a_load_is_refused() -> None:
    planes = roof_planes(20.0)
    with pytest.raises(SnowError, match="slope"):
        asce7_snow_cases(planes, -0.1, 1.0)
    with pytest.raises(SnowError, match="ground load"):
        en1991_snow_cases(planes, 0.1, -1.0)
    with pytest.raises(SnowError, match="positive"):
        asce7_snow_cases(planes, 0.1, 1.0, ce=0.0)
    with pytest.raises(SnowError, match="positive"):
        en1991_snow_cases(planes, 0.1, 1.0, ct=0.0)
    with pytest.raises(SnowError, match="no planes"):
        ash_cases(())
    assert asce7_snow_cases(planes, 0.1, 0.0) == []
    assert en1991_snow_cases(planes, 0.1, 0.0) == []
    assert ash_cases(planes, 0.0) == []


# ─────────────────────────────── volcanic ash ───────────────────────────────
def test_the_ash_is_20_kg_per_square_metre_all_over_the_plan() -> None:
    (case,) = ash_cases(roof_planes(20.0, 2, "gable"))
    assert case.name == "ASH"
    assert case.points == ((0.0, ASH_LOAD_KPA), (40.0, ASH_LOAD_KPA))
    assert pytest.approx(0.196133) == ASH_LOAD_KPA
    assert ash_cases(roof_planes(20.0), 0.3)[0].peak == 0.3


# ─────────────────────────────── ASCE 7-16 ───────────────────────────────
def test_the_asce_tables() -> None:
    assert ASCE_EXPOSURE["B"] == {"full": 0.9, "partial": 1.0, "sheltered": 1.2}
    assert ASCE_EXPOSURE["C"]["sheltered"] == 1.1 and ASCE_EXPOSURE["D"]["full"] == 0.8
    assert ASCE_THERMAL == {
        "heated": 1.0, "cold_ventilated": 1.1, "unheated": 1.2, "freezer": 1.3
    }  # fmt: skip
    assert ASCE_IMPORTANCE == {"I": 0.8, "II": 1.0, "III": 1.1, "IV": 1.2}


def test_the_flat_roof_load_and_its_minimum() -> None:
    assert asce7_flat_roof_load(1.0) == pytest.approx(0.7)
    assert asce7_flat_roof_load(30 * PSF, 0.9, 1.2, 1.1) == pytest.approx(
        0.7 * 0.9 * 1.2 * 1.1 * 30 * PSF
    )
    with pytest.raises(SnowError):
        asce7_flat_roof_load(1.0, importance=0.0)
    # 7.3.4: Is pg up to 20 psf of ground snow, 20 Is psf above it.
    assert asce7_minimum_load(15 * PSF) == pytest.approx(15 * PSF)
    assert asce7_minimum_load(40 * PSF, 1.1) == pytest.approx(22 * PSF)


@pytest.mark.parametrize(
    ("ct", "slippery", "full"),
    [(1.0, True, 5.0), (1.0, False, 30.0), (1.1, True, 10.0), (1.1, False, 37.5),
     (1.2, True, 15.0), (1.2, False, 45.0), (1.3, False, 45.0)],
)  # fmt: skip
def test_the_slope_factor_of_fig_7_4_1(ct: float, slippery: bool, full: float) -> None:
    assert asce7_slope_factor(0.0, ct, slippery) == 1.0
    assert asce7_slope_factor(full, ct, slippery) == 1.0
    assert asce7_slope_factor(70.0, ct, slippery) == 0.0
    assert asce7_slope_factor(85.0, ct, slippery) == 0.0
    middle = 0.5 * (full + 70.0)
    assert asce7_slope_factor(middle, ct, slippery) == pytest.approx(0.5)


def test_the_drift_height_and_the_density() -> None:
    # Fig. 7.6-1: lu = 30 ft and pg = 30 psf give 0.43 x 3.107 x 2.515 - 1.5 = 1.86 ft.
    assert asce7_drift_height(30 * FT, 30 * PSF) == pytest.approx(1.86 * FT, rel=1e-3)
    # A fetch under 20 ft counts as 20 ft.
    assert asce7_drift_height(3.0, 30 * PSF) == asce7_drift_height(20 * FT, 30 * PSF)
    assert asce7_drift_height(20 * FT, 0.0) > 0.0
    # Eq. 7.7-1: 0.13 pg + 14, at most 30 pcf.
    assert asce7_snow_density(30 * PSF) == pytest.approx(17.9 * PCF)
    assert asce7_snow_density(200 * PSF) == pytest.approx(30.0 * PCF)


def test_a_gable_roof_gets_the_balanced_and_the_two_unbalanced_loads() -> None:
    # 60 ft wide, 4 on 12, pg = 30 psf: pf = ps = 21 psf (above the 20 psf minimum).
    planes = roof_planes(60 * FT)
    balanced, plus, minus = asce7_snow_cases(planes, 4.0 / 12.0, 30 * PSF)
    assert [c.name for c in (balanced, plus, minus)] == ["SNOW", "SNOW +X", "SNOW -X"]
    assert balanced.points == ((0.0, pytest.approx(21 * PSF)), (60 * FT, pytest.approx(21 * PSF)))
    # 7.6.1: 0.3 ps to windward; to leeward ps and hd gamma / sqrt(S) = 1.86 x 17.9 /
    # sqrt(3) = 19.2 psf over 8 hd sqrt(S) / 3 = 8.59 ft from the ridge.
    assert plus.mean(0.0, 30 * FT) == pytest.approx(6.3 * PSF)
    assert plus.at(31 * FT) == pytest.approx((21 + 19.22) * PSF, rel=1e-3)
    assert plus.at(38.5 * FT) == pytest.approx((21 + 19.22) * PSF, rel=1e-3)
    assert plus.at(38.7 * FT) == pytest.approx(21 * PSF)
    assert plus.at(59 * FT) == pytest.approx(21 * PSF)
    # The other wind is the mirror image.
    for x in (1.0, 5.0, 8.0, 9.2, 11.0, 17.0):
        assert minus.at(x) == pytest.approx(plus.at(60 * FT - x))
    assert minus.resultant() == pytest.approx(plus.resultant())


@pytest.mark.parametrize(
    ("slope", "names"),
    [
        (0.02, ["SNOW"]),  # under 1/2 on 12
        (0.5 / 12.0, ["SNOW", "SNOW +X", "SNOW -X"]),
        (7.0 / 12.0, ["SNOW", "SNOW +X", "SNOW -X"]),
        (0.7, ["SNOW"]),  # over 7 on 12
    ],
)
def test_the_unbalanced_load_has_its_range_of_slopes(slope: float, names: list[str]) -> None:
    assert [c.name for c in asce7_snow_cases(roof_planes(20.0), slope, 1.5)] == names
    assert [c.name for c in asce7_snow_cases(roof_planes(20.0), slope, 1.5, unbalanced=False)] == [
        "SNOW"
    ]


def test_low_slopes_take_the_minimum_and_steep_slippery_ones_shed() -> None:
    # pg = 15 psf: pf = 10.5 psf, under the minimum Is pg = 15 psf while below 15 degrees.
    (low,) = asce7_snow_cases(roof_planes(20.0, 1, "mono"), 0.1, 15 * PSF)
    assert low.peak == pytest.approx(15 * PSF)
    (flat,) = asce7_snow_cases(roof_planes(20.0, 1, "flat"), 0.0, 15 * PSF)
    assert flat.peak == pytest.approx(15 * PSF)
    (steep,) = asce7_snow_cases(roof_planes(20.0, 1, "mono"), 0.3, 15 * PSF)
    assert steep.peak == pytest.approx(10.5 * PSF)  # 16.7 degrees: no minimum
    angle = math.degrees(math.atan(0.5))
    (slippery,) = asce7_snow_cases(roof_planes(20.0, 1, "mono"), 0.5, 2.0, slippery=True)
    assert slippery.peak == pytest.approx(1.4 * (70.0 - angle) / 65.0)


def test_several_gables_drift_into_their_valleys() -> None:
    # 7.4.4 and 7.6.3: Cs = 1; 0.5 pf at the ridges, 2 pf / Ce in the valleys.
    planes = roof_planes(20.0, 3, "gable")
    balanced, valleys = asce7_snow_cases(planes, 1.0, 1.0, ce=0.9)
    pf = 0.7 * 0.9
    assert balanced.points == ((0.0, pytest.approx(pf)), (60.0, pytest.approx(pf)))
    assert valleys.name == "SNOW VALLEYS"
    assert valleys.at(5.0) == pytest.approx(pf)  # an outer slope
    assert valleys.at(55.0) == pytest.approx(pf)
    assert valleys.at(10.0) == pytest.approx(0.5 * pf)
    assert valleys.at(20.0) == pytest.approx(2.0 * pf / 0.9)
    assert valleys.at(30.0) == pytest.approx(0.5 * pf)
    assert valleys.at(40.0) == pytest.approx(2.0 * pf / 0.9)
    assert valleys.at(15.0) == pytest.approx(0.5 * (0.5 * pf + 2.0 * pf / 0.9))
    # A nearly flat folded roof and a sawtooth get the balanced load only.
    assert len(asce7_snow_cases(planes, 0.02, 1.0)) == 1
    (sawtooth,) = asce7_snow_cases(roof_planes(20.0, 3, "mono"), 1.0, 1.0)
    assert sawtooth.peak == pytest.approx(0.7)


# ─────────────────────────────── EN 1991-1-3 ───────────────────────────────
def test_the_shape_coefficients_of_table_5_2() -> None:
    assert EN_EXPOSURE == {"windswept": 0.8, "normal": 1.0, "sheltered": 1.2}
    assert [en1991_mu1(a) for a in (0.0, 30.0, 45.0, 60.0, 75.0)] == pytest.approx(
        [0.8, 0.8, 0.4, 0.0, 0.0]
    )
    assert [en1991_mu2(a) for a in (0.0, 15.0, 30.0, 45.0, 60.0)] == pytest.approx(
        [0.8, 1.2, 1.6, 1.6, 0.0]
    )


def test_a_duopitch_roof_gets_the_three_arrangements_of_5_3_3() -> None:
    cases = en1991_snow_cases(roof_planes(20.0), 0.2, 1.5, ce=0.8)
    s = 0.8 * 0.8 * 1.5
    assert [c.name for c in cases] == ["SNOW", "SNOW +X", "SNOW -X"]
    assert [(c.mean(0.0, 10.0), c.mean(10.0, 20.0)) for c in cases] == [
        (pytest.approx(s), pytest.approx(s)),
        (pytest.approx(0.5 * s), pytest.approx(s)),
        (pytest.approx(s), pytest.approx(0.5 * s)),
    ]
    assert [c.name for c in en1991_snow_cases(roof_planes(20.0), 0.2, 1.5, drifted=False)] == [
        "SNOW"
    ]
    # Monopitch and flat roofs have the one arrangement; at 60 degrees nothing stays.
    assert len(en1991_snow_cases(roof_planes(20.0, 1, "mono"), 0.2, 1.5)) == 1
    (flat,) = en1991_snow_cases(roof_planes(20.0, 1, "flat"), 0.0, 1.5)
    assert flat.peak == pytest.approx(1.2)
    (bare,) = en1991_snow_cases(roof_planes(20.0), math.tan(math.radians(61.0)), 1.5)
    assert bare.peak == 0.0


def test_a_multi_span_roof_drifts_into_its_valleys() -> None:
    slope = math.tan(math.radians(15.0))
    balanced, valleys = en1991_snow_cases(roof_planes(20.0, 2, "gable"), slope, 1.0)
    assert balanced.points == ((0.0, pytest.approx(0.8)), (40.0, pytest.approx(0.8)))
    assert valleys.name == "SNOW VALLEYS"
    assert valleys.at(5.0) == pytest.approx(0.8) and valleys.at(35.0) == pytest.approx(0.8)
    assert valleys.at(10.0) == pytest.approx(0.8)
    assert valleys.at(20.0) == pytest.approx(1.2)  # mu2 at 15 degrees
    assert valleys.at(15.0) == pytest.approx(1.0)
    assert valleys.at(30.0) == pytest.approx(0.8)
    assert len(en1991_snow_cases(roof_planes(20.0, 2, "mono"), slope, 1.0)) == 1
