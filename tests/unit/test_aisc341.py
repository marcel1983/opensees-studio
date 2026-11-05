"""AISC 341-22 Tables D1.1a and D1.1b: the width-to-thickness limits."""

from __future__ import annotations

import math

import pytest

from opensees_studio.core.design.aisc341 import (
    admissible,
    alpha_s,
    ca,
    limit,
)

E, RY, FY = 29000.0, 1.1, 50.0
ROOT = math.sqrt(E / (RY * FY))


def test_alpha_s_is_the_lrfd_asd_pair() -> None:
    assert alpha_s("LRFD") == 1.0
    assert alpha_s("ASD") == 1.5
    with pytest.raises(ValueError, match="LRFD"):
        alpha_s("WSD")  # type: ignore[arg-type]


def test_ca_follows_the_footnote_b() -> None:
    # Ca = Pr / (alpha_s Ry Fy Ag)
    assert ca(1000.0, RY, FY, 20.0) == pytest.approx(1000.0 / (1.0 * RY * FY * 20.0))
    assert ca(1000.0, RY, FY, 20.0, method="ASD") == pytest.approx(1000.0 / (1.5 * RY * FY * 20.0))
    assert ca(-50.0, RY, FY, 20.0) == 0.0
    with pytest.raises(ValueError, match="positive"):
        ca(1.0, 0.0, FY, 20.0)


@pytest.mark.parametrize(
    ("case", "high", "moderate"),
    [
        (1, 0.30, 0.38),
        (2, 0.55, 0.64),
        (3, 0.038, 0.044),
        (4, 1.49, 1.49),
        (5, 1.40, 2.26),
        (6, 0.076, 0.15),
        (7, 0.30, 0.38),
        (8, 0.47, 0.54),
        (12, 0.55, 1.00),
        (14, 0.55, 0.64),
        (15, 0.064, 1.67),
        (16, 0.038, 0.070),
        (17, 1.40, 2.26),
        (18, 0.076, 0.15),
    ],
)
def test_simple_cases_are_coefficient_times_root(case: int, high: float, moderate: float) -> None:
    assert limit(case, E, RY, FY, ductility="high") == pytest.approx(high * ROOT)
    assert limit(case, E, RY, FY, ductility="moderate") == pytest.approx(moderate * ROOT)


def test_h_piles_have_only_a_moderately_ductile_limit() -> None:
    assert limit(9, E, RY, FY, ductility="moderate") == pytest.approx(0.45 * ROOT)
    assert limit(10, E, RY, FY, ductility="moderate") == pytest.approx(1.50 * ROOT)
    with pytest.raises(ValueError, match="no highly ductile limit"):
        limit(9, E, RY, FY, ductility="high")


def test_case_11_is_the_new_deep_column_expression() -> None:
    # lambda = 2.5 (1 - Ca)^2.3 sqrt(E/(RyFy)) and 5.4 for moderately ductile.
    assert limit(11, E, RY, FY, ca_value=0.0) == pytest.approx(2.5 * ROOT)
    assert limit(11, E, RY, FY, ca_value=0.5) == pytest.approx(2.5 * 0.5**2.3 * ROOT)
    assert limit(11, E, RY, FY, ductility="moderate", ca_value=0.5) == pytest.approx(
        5.4 * 0.5**2.3 * ROOT
    )
    # Ca above 1 never makes the limit negative.
    assert limit(11, E, RY, FY, ca_value=1.4) == pytest.approx(0.0)


def test_case_13_switches_at_0_113_and_has_a_floor() -> None:
    low_high = limit(13, E, RY, FY, ca_value=0.0)
    low_md = limit(13, E, RY, FY, ductility="moderate", ca_value=0.0)
    assert low_high == pytest.approx(2.45 * ROOT)
    assert low_md == pytest.approx(3.76 * ROOT)
    high_high = limit(13, E, RY, FY, ca_value=0.5)
    high_md = limit(13, E, RY, FY, ductility="moderate", ca_value=0.5)
    assert high_high == pytest.approx(2.26 * (1.0 - 0.38 * 0.5) * ROOT)
    assert high_md == pytest.approx(2.61 * (1.0 - 0.49 * 0.5) * ROOT)
    # The floor of 1.56 sqrt(E/(RyFy)) holds at both branches.
    assert limit(13, E, RY, FY, ca_value=0.0) >= 1.56 * ROOT
    assert limit(13, E, RY, FY, ca_value=2.0) == pytest.approx(1.56 * ROOT)


def test_the_case_11_limit_drops_fast_with_axial_load() -> None:
    ratios = [limit(11, E, RY, FY, ca_value=c) / ROOT for c in (0.0, 0.2, 0.5, 0.8)]
    assert ratios == sorted(ratios, reverse=True)
    assert ratios[1] == pytest.approx(2.5 * 0.8**2.3)


def test_admissible_compares_with_a_tiny_tolerance() -> None:
    cap = limit(7, E, RY, FY)
    assert admissible(cap, 7, E, RY, FY)
    assert not admissible(cap * 1.001, 7, E, RY, FY)


def test_unknown_cases_and_ductility_are_refused() -> None:
    with pytest.raises(ValueError, match="1 to 18"):
        limit(19, E, RY, FY)
    with pytest.raises(ValueError, match="ductility"):
        limit(7, E, RY, FY, ductility="low")  # type: ignore[arg-type]
