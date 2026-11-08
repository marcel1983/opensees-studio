"""AISC 360 Chapter J: welds, bolts and affected connection elements."""

from __future__ import annotations

import math

import pytest

from opensees_studio.core.design.chapter_j import (
    block_shear_strength,
    bolt_bearing_strength,
    bolt_shear_strength,
    bolt_tension_strength,
    fillet_weld_strength,
    plate_shear_rupture,
    plate_shear_yielding,
    slip_critical_strength,
)


def test_fillet_weld_j2_4() -> None:
    strength = fillet_weld_strength(fexx=70.0, leg=0.25, length=10.0, both_sides=False)
    throat = 0.70710678 * 0.25
    area = throat * 10.0
    assert strength.nominal == pytest.approx(0.60 * 70.0 * area)
    assert strength.available == pytest.approx(0.75 * strength.nominal)
    asd = fillet_weld_strength(fexx=70.0, leg=0.25, length=10.0, both_sides=False, method="ASD")
    assert asd.available == pytest.approx(strength.nominal / 2.0)


def test_bolt_shear_and_tension_j3_1() -> None:
    area = math.pi * 0.75**2 / 4.0
    shear = bolt_shear_strength(fnv=54.0, diameter=0.75, count=4)
    assert shear.nominal == pytest.approx(4 * 54.0 * area)
    assert shear.available == pytest.approx(0.75 * shear.nominal)
    tension = bolt_tension_strength(fnt=90.0, diameter=0.75, count=4)
    assert tension.nominal == pytest.approx(4 * 90.0 * area)
    assert tension.available == pytest.approx(0.75 * tension.nominal)


def test_bolt_bearing_and_tearout_j3_6() -> None:
    strength = bolt_bearing_strength(
        fu=65.0,
        thickness=0.5,
        diameter=0.75,
        count=4,
        edge_distance=1.5,
        hole_diameter=0.8125,
    )
    clear = 1.5 - 0.8125 / 2.0
    tearout = 1.2 * clear * 0.5 * 65.0
    bearing = 2.4 * 0.75 * 0.5 * 65.0
    assert strength.nominal == pytest.approx(4 * min(bearing, tearout))
    assert strength.available == pytest.approx(0.75 * strength.nominal)


def test_slip_critical_j3_4() -> None:
    standard = slip_critical_strength(mu=0.3, tb=28.0, ns=1, count=4, hole_type="standard")
    assert standard.nominal == pytest.approx(4 * 0.3 * 1.13 * 28.0)
    assert standard.available == pytest.approx(standard.nominal)
    oversized = slip_critical_strength(mu=0.3, tb=28.0, ns=1, count=4, hole_type="oversized")
    assert oversized.available == pytest.approx(0.85 * oversized.nominal)


def test_plate_shear_j4_3_and_j4_4() -> None:
    yielding = plate_shear_yielding(fy=50.0, agv=6.0)
    assert yielding.nominal == pytest.approx(180.0)
    assert yielding.available == pytest.approx(180.0)
    rupture = plate_shear_rupture(fu=65.0, anv=4.375)
    assert rupture.nominal == pytest.approx(170.625)
    assert rupture.available == pytest.approx(0.75 * 170.625)


def test_block_shear_j4_5() -> None:
    strength = block_shear_strength(
        fy=50.0,
        fu=65.0,
        agv=6.0,
        anv=4.375,
        ant=1.0,
    )
    rupture = 0.60 * 65.0 * 4.375 + 65.0
    yield_path = 0.60 * 50.0 * 6.0 + 65.0
    assert strength.nominal == pytest.approx(min(rupture, yield_path))
    nonuniform = block_shear_strength(
        fy=50.0,
        fu=65.0,
        agv=6.0,
        anv=4.375,
        ant=1.0,
        uniform_tension=False,
    )
    assert nonuniform.nominal == pytest.approx(
        min(0.60 * 65.0 * 4.375 + 0.5 * 65.0, 0.60 * 50.0 * 6.0 + 0.5 * 65.0)
    )


def test_chapter_j_inputs_are_guarded() -> None:
    with pytest.raises(ValueError, match="positive"):
        fillet_weld_strength(fexx=0.0, leg=0.25, length=10.0)
    with pytest.raises(ValueError, match="positive"):
        bolt_shear_strength(fnv=54.0, diameter=0.75, count=0)
    with pytest.raises(ValueError, match="positive"):
        plate_shear_yielding(fy=50.0, agv=0.0)
    with pytest.raises(ValueError, match="Unknown hole"):
        slip_critical_strength(
            mu=0.3,
            tb=28.0,
            ns=1,
            count=1,
            hole_type="round",  # type: ignore[arg-type]
        )


def test_fillers_follow_j5() -> None:
    from opensees_studio.core.design.chapter_j import (
        filler_bolt_factor,
        filler_weld_required_leg,
    )

    assert filler_bolt_factor(0.25) == pytest.approx(1.0)
    assert filler_bolt_factor(0.5) == pytest.approx(0.9)
    assert filler_bolt_factor(1.0) == pytest.approx(0.85)
    assert filler_bolt_factor(6.0, metric=True) == pytest.approx(1.0)
    assert filler_bolt_factor(10.0, metric=True) == pytest.approx(1.0 - 0.0154 * 4.0)
    assert filler_weld_required_leg(0.25, 0.125) == pytest.approx(0.375)
    assert filler_weld_required_leg(0.25, 0.125, transfers_force=True) == pytest.approx(0.25)


def test_the_filler_reduces_the_bolt_shear() -> None:
    plain = bolt_shear_strength(fnv=54.0, diameter=0.75, count=4)
    filled = bolt_shear_strength(fnv=54.0, diameter=0.75, count=4, filler_thickness=0.5)
    assert filled.nominal == pytest.approx(plain.nominal * 0.9)
    assert any("J5.2" in note for note in filled.notes)


def test_bearing_concrete_and_splice_j6_to_j8() -> None:
    from opensees_studio.core.design.chapter_j import (
        bearing_strength,
        concrete_bearing_strength,
        splice_strength,
    )

    bearing = bearing_strength(fy=50.0, apb=2.0)
    assert bearing.nominal == pytest.approx(180.0)
    assert bearing.available == pytest.approx(0.75 * 180.0)

    full = concrete_bearing_strength(fc=4.0, a1=100.0)
    assert full.nominal == pytest.approx(0.85 * 4.0 * 100.0)
    assert full.available == pytest.approx(0.65 * full.nominal)
    partial = concrete_bearing_strength(fc=4.0, a1=100.0, a2=400.0)
    assert partial.nominal == pytest.approx(1.7 * 4.0 * 100.0)

    splice = splice_strength(nominal=1000.0)
    assert splice.nominal == pytest.approx(1000.0)
    assert splice.available == pytest.approx(1000.0)
