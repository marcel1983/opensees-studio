"""Wind pressures on a closed building: RNC-07 Título IV, ASCE 7-16 and EN 1991-1-4.

The table values are the regulation's, typed here a second time; the cases are
checked against pressures worked out by hand.
"""

from __future__ import annotations

import math

import pytest

from opensees_studio.core.wind import (
    ASCE7_ROOF_CP_MAX,
    DIRECTIONS,
    KGF,
    BuildingShape,
    Profile,
    Surface,
    WindError,
    asce7_area_reduction,
    asce7_kz,
    asce7_leeward_roof_cp,
    asce7_leeward_wall_cp,
    asce7_roof_zones,
    asce7_velocity_pressure,
    asce7_wind_cases,
    asce7_windward_roof_cp,
    constant,
    en1991_peak_pressure,
    en1991_roof_cp,
    en1991_roof_zone,
    en1991_side_wall_zones,
    en1991_wall_cp,
    en1991_wind_cases,
    rnc07_design_speed,
    rnc07_height_factor,
    rnc07_internal_cp,
    rnc07_pressure,
    rnc07_regional_speed,
    rnc07_topography_factor,
    rnc07_wind_cases,
    rnc07_windward_roof_cp,
    steps,
)

GABLE = BuildingShape(width=20.0, length=30.0, eave_height=6.0, roof="gable", slope=0.10)


# ───────────────────────────── profiles ─────────────────────────────
def test_a_stepped_profile_averages_exactly_across_its_steps() -> None:
    profile = steps((0.0, 2.0, 5.0, math.inf), (10.0, 4.0, 1.0))
    assert [profile.at(x) for x in (-1.0, 0.0, 1.99, 2.0, 4.0, 5.0, 99.0)] == [
        10.0, 10.0, 10.0, 4.0, 4.0, 1.0, 1.0,
    ]  # fmt: skip
    assert profile.mean(0.0, 2.0) == pytest.approx(10.0)
    assert profile.mean(1.0, 6.0) == pytest.approx((10.0 + 3 * 4.0 + 1.0) / 5.0)
    assert profile.mean(6.0, 1.0) == profile.mean(1.0, 6.0)
    assert profile.mean(3.0, 3.0) == 4.0
    with pytest.raises(WindError):
        steps((0.0, 1.0), (1.0, 2.0))


def test_a_smooth_profile_is_integrated_between_its_breaks() -> None:
    kink = Profile(lambda z: max(z, 2.0) ** 2, (2.0,))
    exact = (2.0 * 4.0 + (4.0**3 - 2.0**3) / 3.0) / 4.0
    assert kink.mean(0.0, 4.0) == pytest.approx(exact, rel=1e-12)
    assert kink.scaled(2.0, -1.0).at(3.0) == pytest.approx(17.0)
    assert constant(7.0).mean(-5.0, 5.0) == 7.0


# ───────────────────────────── the building ─────────────────────────────
def test_the_roof_planes_of_each_shape() -> None:
    assert GABLE.ridge_height == pytest.approx(7.0)
    assert GABLE.mean_roof_height == pytest.approx(6.5)
    assert GABLE.roof_angle == pytest.approx(math.degrees(math.atan(0.1)))
    assert [(p.x0, p.x1, p.rise) for p in GABLE.planes()] == [(0.0, 10.0, 1), (10.0, 20.0, -1)]
    mono = BuildingShape(width=12.0, length=20.0, eave_height=5.0, roof="mono", slope=0.25)
    assert mono.ridge_height == pytest.approx(8.0) and mono.roof_height(6.0) == pytest.approx(6.5)
    assert [(p.x0, p.x1, p.rise) for p in mono.planes()] == [(0.0, 12.0, 1)]
    for flat in (
        BuildingShape(width=12.0, length=20.0, eave_height=5.0, roof="flat", slope=0.3),
        BuildingShape(width=12.0, length=20.0, eave_height=5.0, roof="gable", slope=0.0),
    ):
        assert flat.is_flat and flat.roof_angle == 0.0 and flat.ridge_height == 5.0
        assert [p.rise for p in flat.planes()] == [0]


@pytest.mark.parametrize(
    "fields",
    [{"width": 0.0}, {"length": -1.0}, {"eave_height": 0.0}, {"roof": "dome"}, {"slope": -0.1}],
)
def test_a_shape_that_is_not_a_building_is_refused(fields) -> None:  # type: ignore[no-untyped-def]
    values = {"width": 10.0, "length": 20.0, "eave_height": 5.0, **fields}
    with pytest.raises(WindError):
        BuildingShape(**values)


# ───────────────────────────── RNC-07 ─────────────────────────────
def test_rnc07_tabla_5_regional_velocities() -> None:
    assert [rnc07_regional_speed(z) for z in (1, 2, 3)] == [30.0, 45.0, 56.0]
    assert [rnc07_regional_speed(z, "A") for z in (1, 2, 3)] == [36.0, 60.0, 70.0]
    with pytest.raises(WindError):
        rnc07_regional_speed(4)
    with pytest.raises(WindError):
        rnc07_regional_speed(1, "C")


def test_rnc07_height_factor_of_ec_29() -> None:
    assert rnc07_height_factor(3.0, "R3") == 1.0
    assert rnc07_height_factor(10.0, "R1") == 1.0
    assert rnc07_height_factor(20.0, "R2") == pytest.approx(2.0**0.128)
    assert rnc07_height_factor(40.0, "R4") == pytest.approx(4.0**0.170)
    # Above the gradient height the velocity no longer grows.
    assert rnc07_height_factor(500.0, "R1") == pytest.approx(24.5**0.099)
    assert rnc07_height_factor(400.0, "R3") == pytest.approx(39.0**0.156)
    with pytest.raises(WindError):
        rnc07_height_factor(5.0, "R9")


def test_rnc07_topography_factor_of_tabla_7() -> None:
    table = {
        "T1": (0.8, 0.7, 0.66),
        "T2": (0.9, 0.79, 0.74),
        "T3": (1.0, 0.88, 0.82),
        "T4": (1.1, 0.97, 0.9),
        "T5": (1.2, 1.06, 0.98),
    }
    for topography, row in table.items():
        assert rnc07_topography_factor(topography, "R1") == 1.0  # Art. 52: always 1 on R1
        assert tuple(rnc07_topography_factor(topography, r) for r in ("R2", "R3", "R4")) == row
    with pytest.raises(WindError):
        rnc07_topography_factor("T9", "R2")


def test_rnc07_pressure_of_ec_30() -> None:
    vd = rnc07_design_speed(45.0, 8.0, "R2", "T3")
    assert vd == 45.0
    assert rnc07_pressure(1.0, vd) == pytest.approx(0.0479 * 45.0**2 * KGF)  # 97 kg/m²
    assert rnc07_design_speed(30.0, 20.0, "R3", "T4") == pytest.approx(0.97 * 2.0**0.156 * 30.0)


def test_rnc07_windward_roof_of_tabla_8() -> None:
    assert rnc07_windward_roof_cp(5.0) == -0.8  # 0.04 θ - 1.6 = -1.4, not below -0.8
    assert rnc07_windward_roof_cp(20.0) == -0.8
    assert rnc07_windward_roof_cp(30.0) == pytest.approx(-0.4)
    assert rnc07_windward_roof_cp(40.0) == pytest.approx(0.0)
    assert rnc07_windward_roof_cp(60.0) == pytest.approx(0.8)
    assert rnc07_windward_roof_cp(89.0) == 1.8


def test_rnc07_internal_pressure_of_art_55() -> None:
    assert rnc07_internal_cp("closed", "+X") == 0.0
    assert rnc07_internal_cp("uniform", "-Y") == -0.3
    assert [rnc07_internal_cp("x0", d) for d in DIRECTIONS] == [0.75, -0.6, -0.5, -0.5]
    assert [rnc07_internal_cp("y1", d) for d in DIRECTIONS] == [-0.5, -0.5, -0.6, 0.75]
    with pytest.raises(WindError):
        rnc07_internal_cp("roof", "+X")


def test_rnc07_cases_of_a_closed_gable_building() -> None:
    q = 0.0479 * 45.0**2 * KGF
    cases = rnc07_wind_cases(GABLE, regional_speed=45.0)
    assert [c.name for c in cases] == ["WIND +X", "WIND -X", "WIND +Y", "WIND -Y"]
    plus_x, minus_x, plus_y, _minus_y = cases
    assert plus_x.walls["x0"].at(3.0) == pytest.approx(0.8 * q)
    assert plus_x.walls["x1"].at(3.0) == pytest.approx(-0.4 * q)
    assert plus_x.walls["y0"].at(3.0) == plus_x.walls["y1"].at(5.0) == pytest.approx(-0.8 * q)
    # 5.7 degrees: the windward slope is at the -0.8 floor, the leeward at -0.7.
    assert [load.profile.at(5.0) for load in plus_x.roof] == pytest.approx([-0.8 * q, -0.7 * q])
    assert [load.profile.at(5.0) for load in minus_x.roof] == pytest.approx([-0.7 * q, -0.8 * q])
    assert minus_x.walls["x1"].at(1.0) == pytest.approx(0.8 * q)
    # Along the ridge the roof is parallel to the flow: -0.8 on both slopes.
    assert [load.profile.at(5.0) for load in plus_y.roof] == pytest.approx([-0.8 * q, -0.8 * q])
    assert plus_y.walls["y0"].at(6.5) == pytest.approx(0.8 * q)
    assert plus_y.walls["x0"].at(2.0) == pytest.approx(-0.8 * q)
    assert plus_x.coefficients == {
        "windward_wall": 0.8, "leeward_wall": -0.4, "side_wall": -0.8, "internal": 0.0,
        "windward_roof": -0.8, "leeward_roof": -0.7,
    }  # fmt: skip


def test_rnc07_steep_roof_and_openings() -> None:
    steep = BuildingShape(width=10.0, length=30.0, eave_height=4.0, roof="gable", slope=1.0)
    q = 0.0479 * 30.0**2 * KGF
    (case,) = rnc07_wind_cases(steep, regional_speed=30.0, openings="x0", directions=("+X",))
    internal = 0.75 * q  # the openings face the wind
    assert case.roof[0].profile.at(2.0) == pytest.approx((0.04 * 45.0 - 1.6) * q - internal)
    assert case.roof[1].profile.at(8.0) == pytest.approx(-0.7 * q - internal)
    assert case.walls["x0"].at(1.0) == pytest.approx(0.8 * q - internal)
    assert case.walls["x1"].at(1.0) == pytest.approx(-0.4 * q - internal)
    (back,) = rnc07_wind_cases(steep, regional_speed=30.0, openings="x0", directions=("-X",))
    assert back.walls["x0"].at(1.0) == pytest.approx(-0.4 * q + 0.6 * q)  # leeward openings


def test_rnc07_the_pressure_grows_above_ten_metres_except_on_the_leeward_wall() -> None:
    tall = BuildingShape(width=20.0, length=30.0, eave_height=30.0, roof="flat")
    (case,) = rnc07_wind_cases(tall, regional_speed=30.0, roughness="R3", directions=("+X",))
    q = 0.0479 * (0.88 * 30.0) ** 2 * KGF
    assert case.walls["x0"].at(10.0) == pytest.approx(0.8 * q)
    assert case.walls["x0"].at(30.0) == pytest.approx(0.8 * q * 3.0 ** (2 * 0.156))
    assert case.walls["y0"].at(20.0) == pytest.approx(-0.8 * q * 2.0 ** (2 * 0.156))
    # Tabla 8: constant, at the mid height of the building (15 m).
    leeward = -0.4 * q * 1.5 ** (2 * 0.156)
    assert case.walls["x1"].at(1.0) == case.walls["x1"].at(29.0) == pytest.approx(leeward)
    assert case.roof[0].profile.at(3.0) == pytest.approx(-0.8 * q * 3.0 ** (2 * 0.156))


def test_wrong_wind_inputs_are_refused() -> None:
    with pytest.raises(WindError):
        rnc07_wind_cases(GABLE, regional_speed=0.0)
    with pytest.raises(WindError):
        rnc07_wind_cases(GABLE, regional_speed=30.0, directions=("north",))
    with pytest.raises(WindError):
        rnc07_wind_cases(GABLE, regional_speed=30.0, roughness="C")
    with pytest.raises(WindError):
        asce7_wind_cases(GABLE, speed=50.0, exposure="R2")
    with pytest.raises(WindError):
        asce7_wind_cases(GABLE, speed=50.0, kzt=0.0)
    with pytest.raises(WindError):
        asce7_wind_cases(GABLE, speed=-1.0)


# ───────────────────────────── ASCE 7-16 ─────────────────────────────
def test_asce7_kz_matches_table_26_10_1() -> None:
    # Heights in feet as tabulated; the table is good to about 0.01.
    table = {
        "B": {15: 0.57, 30: 0.70, 60: 0.85, 100: 0.99},
        "C": {15: 0.85, 30: 0.98, 60: 1.13, 100: 1.26},
        "D": {15: 1.03, 30: 1.16, 60: 1.31, 100: 1.43},
    }
    for exposure, row in table.items():
        for feet, kz in row.items():
            assert asce7_kz(feet * 0.3048, exposure) == pytest.approx(kz, abs=0.01)
        assert asce7_kz(1.0, exposure) == asce7_kz(4.572, exposure)  # constant below 15 ft
    with pytest.raises(WindError):
        asce7_kz(10.0, "A")


def test_asce7_velocity_pressure_of_eq_26_10_1() -> None:
    q = asce7_velocity_pressure(6.5, 45.0, "C")
    assert q == pytest.approx(0.613 * asce7_kz(6.5, "C") * 0.85 * 45.0**2)
    assert asce7_velocity_pressure(6.5, 45.0, "C", kzt=1.2, kd=1.0, ke=0.9) == pytest.approx(
        q * 1.2 * 0.9 / 0.85
    )


def test_asce7_wall_coefficients_of_figure_27_3_1() -> None:
    assert [asce7_leeward_wall_cp(r) for r in (0.3, 1.0, 2.0, 4.0, 9.0)] == pytest.approx(
        [-0.5, -0.5, -0.3, -0.2, -0.2]
    )
    assert asce7_leeward_wall_cp(1.5) == pytest.approx(-0.4)
    assert asce7_leeward_wall_cp(3.0) == pytest.approx(-0.25)


def test_asce7_windward_roof_of_figure_27_3_1() -> None:
    assert asce7_windward_roof_cp(10.0, 0.25) == pytest.approx((-0.7, -0.18))
    assert asce7_windward_roof_cp(20.0, 0.25) == pytest.approx((-0.3, 0.2))
    assert asce7_windward_roof_cp(20.0, 0.5) == pytest.approx((-0.4, 0.0))
    assert asce7_windward_roof_cp(30.0, 1.0) == pytest.approx((-0.3, 0.2))
    assert asce7_windward_roof_cp(45.0, 0.1) == pytest.approx((0.4, 0.4))
    assert asce7_windward_roof_cp(45.0, 2.0) == pytest.approx((0.0, 0.3))
    assert asce7_windward_roof_cp(70.0, 0.5) == pytest.approx((0.7, 0.7))
    # Between angles and between h/L: straight lines.
    assert asce7_windward_roof_cp(12.5, 0.25) == pytest.approx((-0.6, -0.09))
    assert asce7_windward_roof_cp(15.0, 0.375) == pytest.approx((-0.6, -0.09))
    # The -1.3 of a steep building is reduced with the area it acts on.
    assert asce7_windward_roof_cp(10.0, 1.0)[0] == pytest.approx(-1.3)
    assert asce7_windward_roof_cp(10.0, 1.0, area=100.0)[0] == pytest.approx(-1.04)
    with pytest.raises(WindError):
        asce7_windward_roof_cp(5.0, 0.5)


def test_asce7_leeward_roof_of_figure_27_3_1() -> None:
    assert [asce7_leeward_roof_cp(a, 0.25) for a in (10.0, 15.0, 20.0, 40.0)] == pytest.approx(
        [-0.3, -0.5, -0.6, -0.6]
    )
    assert [asce7_leeward_roof_cp(a, 0.5) for a in (10.0, 15.0, 20.0)] == pytest.approx(
        [-0.5, -0.5, -0.6]
    )
    assert [asce7_leeward_roof_cp(a, 1.5) for a in (10.0, 15.0, 20.0)] == pytest.approx(
        [-0.7, -0.6, -0.6]
    )


def test_asce7_flat_roof_zones_of_figure_27_3_1() -> None:
    low = asce7_roof_zones(6.0, 30.0, 20.0)  # h/L = 0.2
    assert [low.at(d) for d in (0.0, 2.9, 5.9, 6.1, 11.9, 12.1, 29.0)] == pytest.approx(
        [-0.9, -0.9, -0.9, -0.5, -0.5, -0.3, -0.3]
    )
    assert low.mean(0.0, 30.0) == pytest.approx((6 * -0.9 + 6 * -0.5 + 18 * -0.3) / 30.0)
    high = asce7_roof_zones(20.0, 10.0, 12.0)  # h/L = 2, the first zone 12 x 10 m
    assert [asce7_area_reduction(a) for a in (5.0, 9.29, 23.23, 92.9, 500.0)] == pytest.approx(
        [1.0, 1.0, 0.9, 0.8, 0.8]
    )
    assert high.at(5.0) == pytest.approx(-1.3 * 0.8) and high.at(15.0) == pytest.approx(-0.7)
    between = asce7_roof_zones(7.5, 10.0, 100.0)  # h/L = 0.75: half way between the two
    assert between.at(1.0) == pytest.approx((-0.9 - 1.3 * 0.8) / 2.0)
    assert between.at(5.0) == pytest.approx((-0.9 - 0.7) / 2.0)
    assert between.at(9.0) == pytest.approx((-0.5 - 0.7) / 2.0)


def test_asce7_cases_of_a_low_gable_building() -> None:
    cases = asce7_wind_cases(GABLE, speed=45.0, exposure="C")
    assert [c.name for c in cases] == [
        f"WIND {d} {label}" for d in DIRECTIONS for label in ("A", "B")
    ]
    h = 6.5
    qh = asce7_velocity_pressure(h, 45.0, "C")
    a, b = cases[0], cases[1]
    internal = 0.18 * qh
    # Windward wall: qz at each height; everything else at qh.
    q3 = asce7_velocity_pressure(3.0, 45.0, "C")
    assert a.walls["x0"].at(3.0) == pytest.approx(q3 * 0.85 * 0.8 - internal)
    assert b.walls["x0"].at(3.0) == pytest.approx(q3 * 0.85 * 0.8 + internal)
    assert a.walls["x1"].at(3.0) == pytest.approx(qh * 0.85 * -0.5 - internal)  # L/B = 0.67
    assert a.walls["y0"].at(3.0) == pytest.approx(qh * 0.85 * -0.7 - internal)
    # 5.7 degrees: flat-roof zones from the windward edge, h/L = 0.325.
    assert a.roof[0].axis == "x"
    assert a.roof[0].profile.at(3.0) == pytest.approx(qh * 0.85 * -0.9 - internal)
    assert a.roof[0].profile.at(8.0) == pytest.approx(qh * 0.85 * -0.5 - internal)
    assert a.roof[1].profile.at(15.0) == pytest.approx(qh * 0.85 * -0.3 - internal)
    assert b.roof[1].profile.at(15.0) == pytest.approx(qh * 0.85 * ASCE7_ROOF_CP_MAX + internal)
    # The other way the zones start from the other eave.
    back = cases[2]
    assert back.roof[1].profile.at(17.0) == pytest.approx(qh * 0.85 * -0.9 - internal)
    assert back.roof[0].profile.at(3.0) == pytest.approx(qh * 0.85 * -0.3 - internal)
    # Along the ridge: L/B = 1.5, zones along Y.
    along = cases[4]
    assert along.walls["y1"].at(1.0) == pytest.approx(qh * 0.85 * -0.4 - internal)
    assert [load.axis for load in along.roof] == ["y", "y"]
    assert along.roof[0].profile.at(20.0) == pytest.approx(qh * 0.85 * -0.3 - internal)
    assert cases[6].roof[0].profile.at(29.0) == pytest.approx(qh * 0.85 * -0.9 - internal)
    assert a.coefficients["internal"] == 0.18 and b.coefficients["internal"] == -0.18


def test_asce7_steep_roof_and_a_dominant_opening() -> None:
    steep = BuildingShape(width=20.0, length=40.0, eave_height=5.0, roof="gable", slope=0.5)
    angle = math.degrees(math.atan(0.5))  # 26.57 degrees
    h = 7.5
    qh = asce7_velocity_pressure(h, 50.0, "B")
    a, b = asce7_wind_cases(steep, speed=50.0, exposure="B", openings="y0", directions=("+X",))
    internal = 0.55 * qh  # partially enclosed
    low, high = asce7_windward_roof_cp(angle, h / 20.0)
    assert low < 0.0 < high
    assert a.roof[0].profile.at(5.0) == pytest.approx(qh * 0.85 * low - internal)
    assert b.roof[0].profile.at(5.0) == pytest.approx(qh * 0.85 * high + internal)
    assert a.roof[1].profile.at(15.0) == pytest.approx(qh * 0.85 * -0.6 - internal)
    assert b.roof[1].profile.at(15.0) == pytest.approx(qh * 0.85 * -0.6 + internal)
    # The other way the far slope is the windward one.
    c, _d = asce7_wind_cases(steep, speed=50.0, exposure="B", directions=("-X",))
    assert c.coefficients["windward_roof"] == pytest.approx(low)
    assert c.roof[1].profile.at(15.0) == pytest.approx(qh * 0.85 * low - 0.18 * qh)
    # A single slope with the wind from its high side is a leeward slope.
    mono = BuildingShape(width=20.0, length=40.0, eave_height=5.0, roof="mono", slope=0.3)
    m, _n = asce7_wind_cases(mono, speed=50.0, directions=("-X",))
    assert "windward_roof" not in m.coefficients and m.coefficients["leeward_roof"] < 0.0


# ───────────────────────────── EN 1991-1-4 ─────────────────────────────
#: 20 x 40 m, eave 6 m, 1 in 5: the ridge at 8 m, 11.3 degrees.
EN_GABLE = BuildingShape(width=20.0, length=40.0, eave_height=6.0, roof="gable", slope=0.2)


def test_a_surface_averages_its_zones_exactly() -> None:
    corner = Surface(lambda s, t: 3.0 if s < 1.0 and t < 2.0 else 1.0, (1.0,), (2.0,))
    assert corner.at(0.5, 0.5) == 3.0 and corner.at(0.5, 2.5) == 1.0
    assert corner.mean(0.0, 4.0, 0.0, 4.0) == pytest.approx((3.0 * 2.0 + 1.0 * 14.0) / 16.0)
    smooth = Surface(lambda s, t: s * s * t)
    assert smooth.mean(0.0, 3.0, 0.0, 2.0) == pytest.approx(3.0 * 1.0)


def test_en1991_peak_pressure_of_expression_4_8() -> None:
    basic = 0.5 * 1.25 * 27.0**2
    # The exposure factor of Figure 4.2 at 10 m: 2.35 in terrain II, 1.18 in IV.
    assert en1991_peak_pressure(10.0, 27.0, "II") / basic == pytest.approx(2.352, abs=1e-3)
    assert en1991_peak_pressure(10.0, 27.0, "IV") / basic == pytest.approx(1.176, abs=1e-3)
    by_hand = (1.0 + 7.0 / math.log(8.0 / 0.05)) * (0.19 * math.log(8.0 / 0.05)) ** 2
    assert en1991_peak_pressure(8.0, 27.0) / basic == pytest.approx(by_hand)
    # Constant below zmin (5 m in terrain III) and above 200 m.
    assert en1991_peak_pressure(1.0, 27.0, "III") == en1991_peak_pressure(5.0, 27.0, "III")
    assert en1991_peak_pressure(300.0, 27.0) == en1991_peak_pressure(200.0, 27.0)
    assert en1991_peak_pressure(10.0, 27.0, "0") > en1991_peak_pressure(10.0, 27.0, "I")
    # The orography factor raises the mean velocity, not the turbulence.
    hill = en1991_peak_pressure(10.0, 27.0, orography=1.2) / basic
    log = math.log(200.0)
    assert hill == pytest.approx((1.0 + 7.0 / (1.2 * log)) * (0.19 * log * 1.2) ** 2)
    with pytest.raises(WindError, match="terrain categories"):
        en1991_peak_pressure(10.0, 27.0, "C")


def test_en1991_walls_of_table_7_1() -> None:
    assert en1991_wall_cp(5.0) == pytest.approx((0.8, -0.7))
    assert en1991_wall_cp(1.0) == pytest.approx((0.8, -0.5))
    assert en1991_wall_cp(0.25) == pytest.approx((0.7, -0.3))
    assert en1991_wall_cp(0.1) == pytest.approx((0.7, -0.3))
    assert en1991_wall_cp(8.0) == pytest.approx((0.8, -0.7))
    assert en1991_wall_cp(3.0) == pytest.approx((0.8, -0.6))
    zones = en1991_side_wall_zones(10.0)  # A to e/5, B to e, C beyond
    assert [zones.at(d) for d in (1.0, 5.0, 12.0)] == [-1.2, -0.8, -0.5]
    assert zones.mean(0.0, 20.0) == pytest.approx((-1.2 * 2 - 0.8 * 8 - 0.5 * 10) / 20.0)


def test_en1991_roof_coefficients_of_tables_7_2_to_7_4() -> None:
    flat = en1991_roof_cp("flat", 0, 0.0)
    assert flat == [
        {"F": -1.8, "G": -1.2, "H": -0.7, "I": -0.2},
        {"F": -1.8, "G": -1.2, "H": -0.7, "I": 0.2},
    ]
    assert en1991_roof_cp("gable", 90, 3.0) == flat  # under 5 degrees every roof is flat
    # Table 7.4a: the most negative and the most positive set.
    low, high = en1991_roof_cp("gable", 0, 15.0)
    assert low == {"F": -0.9, "G": -0.8, "H": -0.3, "I": -0.4, "J": -1.0}
    assert high == {"F": 0.2, "G": 0.2, "H": 0.2, "I": 0.0, "J": 0.0}
    low, high = en1991_roof_cp("gable", 0, 5.0)
    assert low == {"F": -1.7, "G": -1.2, "H": -0.6, "I": -0.6, "J": -0.6}
    assert high == {"F": 0.0, "G": 0.0, "H": 0.0, "I": -0.6, "J": 0.2}
    low, high = en1991_roof_cp("gable", 0, 10.0)  # half way between 5 and 15 degrees
    assert low == pytest.approx({"F": -1.3, "G": -1.0, "H": -0.45, "I": -0.5, "J": -0.8})
    assert high["F"] == pytest.approx(0.1)
    low, high = en1991_roof_cp("gable", 0, 30.0)
    assert (low["F"], low["H"], low["J"]) == (-0.5, -0.2, -0.5)
    assert (high["F"], high["H"], high["J"]) == (0.7, 0.4, 0.0)
    assert en1991_roof_cp("gable", 0, 60.0) == [
        {"F": 0.7, "G": 0.7, "H": 0.7, "I": -0.2, "J": -0.3}
    ]
    # Table 7.4b.
    assert en1991_roof_cp("gable", 90, 15.0) == [{"F": -1.3, "G": -1.3, "H": -0.6, "I": -0.5}]
    assert en1991_roof_cp("gable", 90, 30.0) == [{"F": -1.1, "G": -1.4, "H": -0.8, "I": -0.5}]
    # Table 7.3a and 7.3b.
    assert en1991_roof_cp("mono", 0, 15.0) == [
        {"F": -0.9, "G": -0.8, "H": -0.3},
        {"F": 0.2, "G": 0.2, "H": 0.2},
    ]
    assert en1991_roof_cp("mono", 180, 15.0) == [{"F": -2.5, "G": -1.3, "H": -0.9}]
    assert en1991_roof_cp("mono", 180, 30.0) == [{"F": -1.1, "G": -0.8, "H": -0.8}]
    assert en1991_roof_cp("mono", 90, 5.0) == [
        {"Fup": -2.1, "Flow": -2.1, "G": -1.8, "H": -0.6, "I": -0.5}
    ]
    assert en1991_roof_cp("mono", 90, 15.0) == [
        {"Fup": -2.4, "Flow": -1.6, "G": -1.9, "H": -0.8, "I": -0.7}
    ]
    with pytest.raises(WindError, match="180"):
        en1991_roof_cp("gable", 180, 15.0)
    with pytest.raises(WindError, match="0, 90 and 180"):
        en1991_roof_cp("gable", 45, 15.0)
    with pytest.raises(WindError, match="roof shape"):
        en1991_roof_cp("dome", 0, 15.0)


def test_en1991_roof_zones_of_figures_7_6_to_7_8() -> None:
    # Across the ridge: e = min(40, 2 x 8) = 16, so F and G are 1.6 m deep and F 4 m wide.
    zone = lambda d, x, y: en1991_roof_zone(EN_GABLE, d, x, y)  # noqa: E731
    assert [zone("+X", 1.0, y) for y in (2.0, 20.0, 38.0)] == ["F", "G", "F"]
    assert [zone("+X", x, 2.0) for x in (5.0, 10.5, 15.0)] == ["H", "J", "I"]
    assert [zone("-X", x, 20.0) for x in (19.0, 15.0, 9.0, 5.0)] == ["G", "H", "J", "I"]
    # Along the ridge: e = min(20, 16) = 16; H to e/2 = 8 m, I beyond.
    assert [zone("+Y", x, 1.0) for x in (2.0, 10.0, 18.0)] == ["F", "G", "F"]
    assert [zone("+Y", 2.0, y) for y in (5.0, 9.0, 39.0)] == ["H", "I", "I"]
    assert zone("-Y", 2.0, 39.0) == "F"
    mono = BuildingShape(width=20.0, length=40.0, eave_height=6.0, roof="mono", slope=0.2)
    assert [en1991_roof_zone(mono, "+Y", x, 1.0) for x in (2.0, 10.0, 18.0)] == [
        "Flow", "G", "Fup",
    ]  # fmt: skip
    assert [en1991_roof_zone(mono, "-X", x, 20.0) for x in (19.5, 10.0)] == ["G", "H"]
    flat = BuildingShape(width=20.0, length=40.0, eave_height=6.0, roof="flat")
    # e = min(40, 12) = 12: F and G to 1.2 m, H to 6 m, I beyond.
    assert [en1991_roof_zone(flat, "+X", x, 20.0) for x in (1.0, 5.0, 7.0)] == ["G", "H", "I"]
    assert en1991_roof_zone(flat, "+X", 1.0, 1.0) == "F"


def test_en1991_cases_of_a_closed_duopitch_building() -> None:
    cases = en1991_wind_cases(EN_GABLE, speed=26.0)
    assert [c.name for c in cases] == [
        *(f"WIND {d} {label}" for d in ("+X", "-X") for label in "ABCD"),
        *(f"WIND {d} {label}" for d in ("+Y", "-Y") for label in "AB"),
    ]
    qp = en1991_peak_pressure(8.0, 26.0)
    a, b, c, d = cases[:4]
    low, high = en1991_roof_cp("gable", 0, EN_GABLE.roof_angle)
    assert a.coefficients["internal"] == 0.2 and b.coefficients["internal"] == -0.3
    assert a.coefficients["windward_wall"] == pytest.approx(0.72)  # h/d = 0.4
    assert a.coefficients["leeward_wall"] == pytest.approx(-0.34)
    assert a.walls["x0"].at(3.0) == pytest.approx(qp * (0.72 - 0.2))
    assert b.walls["x0"].at(3.0) == pytest.approx(qp * (0.72 + 0.3))
    assert a.walls["x1"].at(3.0) == pytest.approx(qp * (-0.34 - 0.2))
    # The side walls: A up to e/5 = 3.2 m from the windward corner, B up to e = 16 m, then C.
    side = a.wall_zones["y0"]
    assert side.at(1.0, 3.0) == pytest.approx(qp * (-1.2 - 0.2))
    assert side.at(10.0, 3.0) == pytest.approx(qp * (-0.8 - 0.2))
    assert side.at(18.0, 3.0) == pytest.approx(qp * (-0.5 - 0.2))
    mean = (-1.2 * 3.2 - 0.8 * 12.8 - 0.5 * 4.0) / 20.0
    assert a.walls["y0"].at(3.0) == pytest.approx(qp * (mean - 0.2))
    assert side.mean(0.0, 20.0, 0.0, 6.0) == pytest.approx(qp * (mean - 0.2))
    assert set(a.wall_zones) == {"y0", "y1"}
    # The roof: A all negative, B all positive, C and D one slope of each.
    zones = a.roof[0].zones
    assert zones is not None and a.roof[1].zones is zones
    assert zones.at(1.0, 2.0) == pytest.approx(qp * (low["F"] - 0.2))
    assert zones.at(1.0, 20.0) == pytest.approx(qp * (low["G"] - 0.2))
    assert zones.at(15.0, 20.0) == pytest.approx(qp * (low["I"] - 0.2))
    assert a.roof[0].profile.at(1.0) == pytest.approx(zones.at(1.0, 20.0))
    for case, windward, leeward, inside in ((b, high, high, -0.3), (c, high, low, -0.3), (d, low, high, 0.2)):  # fmt: skip
        field = case.roof[0].zones
        assert field is not None
        assert field.at(5.0, 20.0) == pytest.approx(qp * (windward["H"] - inside))
        assert field.at(10.5, 20.0) == pytest.approx(qp * (leeward["J"] - inside))
    # The other way the roof is the mirror image.
    mirrored = cases[4].roof[0].zones
    assert mirrored is not None
    assert mirrored.at(19.0, 2.0) == pytest.approx(zones.at(1.0, 2.0))
    assert cases[4].wall_zones["y0"].at(19.0, 3.0) == pytest.approx(side.at(1.0, 3.0))
    # Along the ridge there is one set of values: A and B differ inside only.
    ya, yb = cases[8], cases[9]
    along = en1991_roof_cp("gable", 90, EN_GABLE.roof_angle)[0]
    za, zb = ya.roof[0].zones, yb.roof[0].zones
    assert za is not None and zb is not None
    assert za.at(2.0, 1.0) == pytest.approx(qp * (along["F"] - 0.2))
    assert zb.at(2.0, 30.0) == pytest.approx(qp * (along["I"] + 0.3))
    assert ya.roof[0].axis == "y" and a.roof[0].axis == "x"
    assert ya.coefficients["windward_wall"] == pytest.approx(0.7)  # h/d = 0.2
    assert ya.wall_zones["x0"].at(30.0, 3.0) == pytest.approx(qp * (-0.5 - 0.2))  # zone C


def test_en1991_dominant_opening_monopitch_and_flat_roofs() -> None:
    mono = BuildingShape(width=20.0, length=40.0, eave_height=6.0, roof="mono", slope=0.2)
    cases = en1991_wind_cases(mono, speed=26.0, openings="x0")
    # One internal pressure: 0.9 of the coefficient at the open wall (7.2.9, Expression 7.2).
    assert [c.name for c in cases] == ["WIND +X A", "WIND +X B", "WIND -X", "WIND +Y", "WIND -Y"]
    windward, leeward = en1991_wall_cp(10.0 / 20.0)
    assert cases[0].coefficients["internal"] == pytest.approx(0.9 * windward)
    assert cases[2].coefficients["internal"] == pytest.approx(0.9 * leeward)
    assert cases[3].coefficients["internal"] == pytest.approx(
        0.9 * en1991_side_wall_zones(20.0).mean(0.0, 40.0)
    )
    # The wind on the high eave takes Table 7.3a at 180 degrees.
    assert cases[2].coefficients["roof_F"] == pytest.approx(
        en1991_roof_cp("mono", 180, mono.roof_angle)[0]["F"]
    )
    assert {"roof_Fup", "roof_Flow"} <= set(cases[3].coefficients)
    closed = en1991_wind_cases(mono, speed=26.0, directions=("-X",))
    assert [(c.name, c.coefficients["internal"]) for c in closed] == [
        ("WIND -X A", 0.2), ("WIND -X B", -0.3),
    ]  # fmt: skip
    flat = BuildingShape(width=20.0, length=40.0, eave_height=6.0, roof="flat")
    spread = en1991_wind_cases(flat, speed=26.0, openings="uniform", directions=("+Y",))
    assert [(c.coefficients["roof_I"], c.coefficients["internal"]) for c in spread] == [
        (-0.2, 0.2), (0.2, -0.3),
    ]  # fmt: skip
    with pytest.raises(WindError, match="velocity must be positive"):
        en1991_wind_cases(flat, speed=0.0)
    with pytest.raises(WindError, match="factors must be positive"):
        en1991_wind_cases(flat, speed=26.0, orography=0.0)
    with pytest.raises(WindError, match="terrain categories"):
        en1991_wind_cases(flat, speed=26.0, terrain="R2")
