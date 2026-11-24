"""AISI S100-16 by the Direct Strength Method (``core.design.aisi_s100``).

The published numbers are those of the AISI *Direct Strength Method (DSM)
Design Guide* (CF06-1, 2006) for the lipped channel 9CS2.5x059 with Fy = 55 ksi:
the buckling loads of its Section 3.2.1 (CUFSM, printed to two decimals) and
the fully braced beam of its Example 8.1.1. The closed forms of global
buckling are checked against the finite strips, which know nothing of them.
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
import pytest

from opensees_studio.core.design import aisi_s100, fsm
from opensees_studio.core.design.aisc360 import Demand, Steel
from opensees_studio.core.design.aisi_s100 import (
    FACTORS,
    check_member,
    cold_formed_member,
    compression,
    distortional_closed_form,
    flexure_local_only,
    flexure_major,
    flexure_minor,
    flexure_sheeted,
    global_column_stress,
    shear_major,
    tension,
    uplift_r_factor,
)
from opensees_studio.core.sections.cold_formed import ColdFormedShape

E = 29500.0
G = 11300.0


def _c9() -> ColdFormedShape:
    return ColdFormedShape(profile="CS", d=9.0, bf=2.5, t=0.059, r=0.1875, lip=0.773)


def _z8() -> ColdFormedShape:
    return ColdFormedShape(
        profile="ZS", d=8.0, bf=2.25, t=0.059, r=0.1875, lip=0.91, lip_angle=50.0
    )


def _purlin_mm() -> ColdFormedShape:
    return ColdFormedShape(profile="CS", d=150.0, bf=50.0, t=2.38, r=2.38, lip=15.0)


def _track() -> ColdFormedShape:
    return ColdFormedShape(profile="CU", d=6.0, bf=1.5, t=0.097, r=0.1)


def _steel(fy: float = 55.0, fu: float | None = 70.0) -> Steel:
    return Steel(Fy=fy, E=E, G=G, Fu=fu)


def _value(strength: object, label: str) -> float:
    step = next(s for s in strength.steps if s.label.startswith(label))  # type: ignore[attr-defined]
    assert step.value is not None
    return float(step.value)


# ───────────────────────────── the published example ─────────────────────────────
def test_the_buckling_loads_of_the_dsm_guide_channel() -> None:
    """Section 3.2.1: Mcrl = 0.67 My, Mcrd = 0.85 My, Pcrl = 0.12 Py, Pcrd = 0.27 Py."""
    member = cold_formed_member(_c9(), E)
    my = 55.0 * member.Sx
    py = 55.0 * member.A
    assert member.bending_x.local / my == pytest.approx(0.67, abs=0.02)
    assert member.bending_x.distortional / my == pytest.approx(0.85, abs=0.02)
    assert member.axial.local / py == pytest.approx(0.12, abs=0.01)
    assert member.axial.distortional / py == pytest.approx(0.27, abs=0.01)


def test_the_distortional_load_in_compression_is_read_at_lcrd() -> None:
    """The channel's curve in compression has no distortional minimum (ADR-0005)."""
    member = cold_formed_member(_c9(), E)
    assert member.axial.distortional_is_minimum is False
    assert member.axial.distortional_length == pytest.approx(distortional_closed_form(_c9(), E)[1])
    assert member.bending_x.distortional_is_minimum is True
    strength = compression(member, _steel(), "LRFD", length_x=0.0, length_y=0.0)
    assert any("Lcrd" in note for note in strength.notes)


def test_the_fully_braced_beam_of_the_dsm_guide() -> None:
    """Example 8.1.1: Mnl = 94, Mnd = 93, Mn = 93 kip-in; φMn = 84 and Mn/Ω = 56 kip-in."""
    member = cold_formed_member(_c9(), E)
    lrfd = flexure_major(member, _steel(), "LRFD", unbraced=0.0)
    assert _value(lrfd, "Yield moment") == pytest.approx(126.55, rel=0.01)
    assert _value(lrfd, "F3.2.1 local-global") == pytest.approx(94.0, rel=0.01)
    assert _value(lrfd, "F4.1 distortional buckling") == pytest.approx(93.0, rel=0.01)
    assert lrfd.nominal == pytest.approx(93.0, rel=0.01)
    assert lrfd.available == pytest.approx(84.0, rel=0.01)
    assert lrfd.equation == "AISI S100-16 F4.1 distortional buckling"
    asd = flexure_major(member, _steel(), "ASD", unbraced=0.0)
    assert asd.available == pytest.approx(56.0, rel=0.01)


def test_the_guide_numbers_follow_from_its_own_buckling_loads() -> None:
    """With the guide's My, Mcrl and Mcrd the equations give its Mnl and Mnd to the unit."""
    my = 126.55
    _lam, mnl = aisi_s100._local(my, 0.67 * my)
    _lam, mnd = aisi_s100._distortional_beam(my, 0.85 * my)
    assert round(mnl) == 94
    assert round(mnd) == 93


# ───────────────────────────── the strength curves ─────────────────────────────
@pytest.mark.parametrize(
    ("curve", "limit"),
    [
        (aisi_s100._local, 0.776),
        (aisi_s100._distortional_column, 0.561),
        (aisi_s100._distortional_beam, 0.673),
    ],
)
def test_a_strength_curve_is_continuous_at_its_limit(curve, limit: float) -> None:  # type: ignore[no-untyped-def]
    below = curve(1.0, 1.0 / (limit * 0.9999) ** 2)[1]
    above = curve(1.0, 1.0 / (limit * 1.0001) ** 2)[1]
    assert below == 1.0
    assert above == pytest.approx(1.0, abs=2e-3)
    assert curve(1.0, 0.05)[1] < curve(1.0, 0.5)[1] < 1.0


def test_the_column_curve() -> None:
    assert aisi_s100._column_stress(50.0, math.inf) == 50.0
    assert aisi_s100._column_stress(50.0, 50.0) == pytest.approx(0.658 * 50.0)
    # Beyond λc = 1.5 it is 0.877 of the elastic stress.
    assert aisi_s100._column_stress(50.0, 10.0) == pytest.approx(8.77)
    at = aisi_s100._column_stress(50.0, 50.0 / 1.5**2)
    assert at == pytest.approx(0.877 * 50.0 / 1.5**2, rel=2e-3)


def test_the_beam_curve() -> None:
    assert aisi_s100._beam_stress(50.0, 2.78 * 50.0) == 50.0
    assert aisi_s100._beam_stress(50.0, 0.5 * 50.0) == 25.0
    middle = aisi_s100._beam_stress(50.0, 50.0)
    assert middle == pytest.approx(10.0 / 9.0 * 50.0 * (1.0 - 10.0 / 36.0))
    assert aisi_s100._beam_stress(50.0, 0.5601 * 50.0) == pytest.approx(0.56 * 50.0, rel=1e-3)


# ───────────────────────────── closed forms against finite strips ─────────────────────────────
@pytest.mark.parametrize("shape", [_c9(), _purlin_mm(), _z8()], ids=["9CS", "C150", "8ZS"])
@pytest.mark.parametrize("bending", [False, True], ids=["compression", "bending"])
def test_the_closed_form_distortional_length_finds_the_curve_minimum(
    shape: ColdFormedShape, bending: bool
) -> None:
    """Where the signature curve has a distortional minimum, Lcrd and Fcrd are near it."""
    modulus = 200000.0 if shape.d > 50 else E
    member = cold_formed_member(shape, modulus)
    buckling = member.bending_x if bending else member.axial
    stress, length = distortional_closed_form(shape, modulus, bending=bending)
    if not buckling.distortional_is_minimum:
        pytest.skip("no distortional minimum on this curve")
    assert buckling.distortional_length == pytest.approx(length, rel=0.20)
    reference = member.props.Ix / (shape.d / 2 - shape.t / 2) if bending else member.A
    assert buckling.distortional == pytest.approx(stress * reference, rel=0.20)
    # Reading the curve at Lcrd is as good as finding its minimum.
    model = fsm.strip_model(shape, modulus)
    load = fsm.bending_stress(model, member.props, "x") if bending else fsm.axial_stress(model)
    at_lcrd = fsm.buckling_factor(model, load, length)[0] * reference
    assert at_lcrd == pytest.approx(buckling.distortional, rel=0.03)


@pytest.mark.parametrize("shape", [_c9(), _track(), _z8()], ids=["9CS", "CU", "8ZS"])
def test_the_global_column_stress_is_the_finite_strip_one(shape: ColdFormedShape) -> None:
    member = cold_formed_member(shape, E)
    length = 40.0 * shape.d
    closed, _mode = global_column_stress(
        member, _steel(), length_x=length, length_y=length, length_t=length
    )
    model = fsm.strip_model(shape, E)
    strips = fsm.buckling_factor(model, fsm.axial_stress(model), length)[0]
    assert closed == pytest.approx(strips, rel=0.015)


def test_flexural_torsional_buckling_solves_its_quadratic() -> None:
    member = cold_formed_member(_c9(), E)
    steel = _steel()
    # The weak axis held: the channel twists while it bends about x.
    stress, mode = global_column_stress(member, steel, length_x=120.0, length_y=1.0, length_t=120.0)
    assert mode == "flexural-torsional"
    p = member.props
    sigma_ex = math.pi**2 * E / (120.0 / member.rx) ** 2
    sigma_t = (G * p.J + math.pi**2 * E * p.Cw / 120.0**2) / (p.A * p.ro**2)
    beta = 1.0 - (p.x0 / p.ro) ** 2
    assert beta * stress**2 - (sigma_ex + sigma_t) * stress + sigma_ex * sigma_t == pytest.approx(
        0.0, abs=1e-6
    )
    assert stress < min(sigma_ex, sigma_t)


@pytest.mark.parametrize("shape", [_c9(), _track()], ids=["9CS", "CU"])
def test_lateral_torsional_buckling_about_x_is_the_finite_strip_one(
    shape: ColdFormedShape,
) -> None:
    member = cold_formed_member(shape, E)
    length = 40.0 * shape.d
    strength = flexure_major(member, _steel(fy=1e6), "LRFD", unbraced=length)
    closed = _value(strength, "F2.1 lateral-torsional buckling stress") * member.Sx
    model = fsm.strip_model(shape, E)
    reference = member.props.Ix / float(np.abs(model.nodes[:, 1] - member.props.yc).max())
    stress = fsm.bending_stress(model, member.props, "x")
    strips = fsm.buckling_factor(model, stress, length)[0] * reference
    assert closed == pytest.approx(strips, rel=0.015)


@pytest.mark.parametrize("shape", [_c9(), _track()], ids=["9CS", "CU"])
def test_lateral_torsional_buckling_about_y_is_the_finite_strip_one(
    shape: ColdFormedShape,
) -> None:
    """F2.1.2 with the flange tips in compression (Cs = -1), the sense that governs."""
    member = cold_formed_member(shape, E)
    length = 40.0 * shape.d
    nominal, _equation, steps = aisi_s100._flexure_minor_sense(
        member, _steel(fy=1e6), unbraced=length, tips=True
    )
    fcre = next(s.value for s in steps if s.label.startswith("F2.1.2"))
    assert fcre is not None
    closed = fcre * member.props.Iy / member.cy_tips
    model = fsm.strip_model(shape, E)
    reference = member.props.Iy / float(np.abs(model.nodes[:, 0] - member.props.xc).max())
    stress = fsm.bending_stress(model, member.props, "y")
    strips = fsm.buckling_factor(model, stress, length)[0] * reference
    assert closed == pytest.approx(strips, rel=0.015)
    assert nominal <= closed


def test_a_zee_takes_half_the_channel_formula_and_stays_below_the_strips() -> None:
    member = cold_formed_member(_z8(), E)
    length = 320.0
    strength = flexure_major(member, _steel(fy=1e6), "LRFD", unbraced=length)
    closed = _value(strength, "F2.1 lateral-torsional buckling stress") * member.Sx
    model = fsm.strip_model(_z8(), E)
    reference = member.props.Ix / float(np.abs(model.nodes[:, 1] - member.props.yc).max())
    stress = fsm.bending_stress(model, member.props, "x")
    strips = fsm.buckling_factor(model, stress, length)[0] * reference
    assert 0.6 * strips < closed < strips
    assert any("F2.1.3" in note for note in strength.notes)


# ───────────────────────────── members ─────────────────────────────
def test_a_longer_unbraced_length_never_gives_more_strength() -> None:
    member = cold_formed_member(_purlin_mm(), 200000.0)
    steel = Steel(Fy=345.0, E=200000.0, G=77000.0, Fu=450.0)
    lengths = (0.0, 500.0, 1000.0, 2000.0, 4000.0, 6000.0)
    major = [flexure_major(member, steel, "LRFD", unbraced=x).available for x in lengths]
    minor = [flexure_minor(member, steel, "LRFD", unbraced=x).available for x in lengths]
    axial = [compression(member, steel, "LRFD", length_x=x, length_y=x).available for x in lengths]
    for values in (major, minor, axial):
        assert all(b <= a * (1 + 1e-12) for a, b in pairwise(values))
        assert values[-1] < 0.5 * values[0]
    # Fully braced, this stocky purlin yields: no local or distortional reduction.
    braced = flexure_major(member, steel, "LRFD", unbraced=0.0)
    assert braced.equation == "AISI S100-16 F2.1 yielding"
    assert braced.nominal == pytest.approx(345.0 * member.Sx)
    assert flexure_major(member, steel, "LRFD", unbraced=6000.0, cb=1.3).available > major[-1]


def test_a_plain_channel_has_no_distortional_buckling() -> None:
    member = cold_formed_member(_track(), E)
    assert member.axial.distortional is None
    assert member.bending_x.distortional is None
    strength = compression(member, _steel(), "LRFD", length_x=0.0, length_y=0.0)
    assert not any(step.label.startswith("E4.1") for step in strength.steps)
    with pytest.raises(ValueError, match="lipped"):
        distortional_closed_form(_track(), E)


def test_the_factors_of_each_limit_state() -> None:
    member = cold_formed_member(_c9(), E)
    steel = _steel()
    for kind, strength_of in (
        ("compression", lambda m: compression(member, steel, m, length_x=60.0, length_y=60.0)),
        ("flexure", lambda m: flexure_major(member, steel, m, unbraced=60.0)),
        ("flexure", lambda m: flexure_minor(member, steel, m, unbraced=60.0)),
        ("shear", lambda m: shear_major(member, steel, m)),
        ("tension", lambda m: tension(member, steel, m)),
    ):
        phi, omega = FACTORS[kind]
        lrfd, asd = strength_of("LRFD"), strength_of("ASD")
        assert lrfd.nominal == asd.nominal
        assert lrfd.available == pytest.approx(phi * lrfd.nominal)
        assert asd.available == pytest.approx(asd.nominal / omega)


def test_shear_yields_buckles_inelastically_or_elastically() -> None:
    steel = _steel()
    slender = cold_formed_member(_c9(), E)  # h/t = 144
    strength = shear_major(slender, steel, "LRFD")
    assert _value(strength, "G2.1 slenderness") > 1.227
    assert strength.nominal == pytest.approx(_value(strength, "G2.3 shear buckling"))
    h = slender.web_flat
    assert strength.nominal == pytest.approx(
        h * 0.059 * math.pi**2 * E * 5.34 / (12 * (1 - 0.3**2) * (h / 0.059) ** 2)
    )
    stocky = cold_formed_member(_track(), E)  # h/t = 58
    strength = shear_major(stocky, _steel(fy=33.0), "LRFD")
    assert _value(strength, "G2.1 slenderness") <= 0.815
    assert strength.nominal == pytest.approx(0.6 * stocky.web_flat * 0.097 * 33.0)
    middle = cold_formed_member(
        ColdFormedShape(profile="CS", d=8.0, bf=2.5, t=0.097, r=0.1875, lip=0.75), E
    )
    strength = shear_major(middle, steel, "LRFD")
    assert 0.815 < _value(strength, "G2.1 slenderness") <= 1.227
    vy, vcr = _value(strength, "Shear yield"), _value(strength, "G2.3 shear buckling")
    assert strength.nominal == pytest.approx(0.815 * math.sqrt(vy * vcr))


def test_tension_yields_or_ruptures() -> None:
    member = cold_formed_member(_c9(), E)
    plain = tension(member, _steel(), "LRFD")
    assert plain.nominal == pytest.approx(55.0 * member.A)
    assert plain.available == pytest.approx(0.9 * 55.0 * member.A)
    assert any("net area" in note for note in plain.notes)
    net = 0.6 * member.A
    ruptured = tension(member, _steel(), "LRFD", net_area=net, shear_lag=0.9)
    assert ruptured.equation == "AISI S100-16 D3 rupture"
    assert ruptured.available == pytest.approx(0.75 * 70.0 * 0.9 * net)
    assert any(
        "Fu" in note for note in tension(member, _steel(fu=None), "LRFD", net_area=net).notes
    )


def test_the_interaction_adds_the_three_ratios() -> None:
    member = cold_formed_member(_c9(), E)
    steel = _steel()
    demand = Demand(
        axial=-3.0, moment_major=20.0, moment_minor=2.0, shear_major=1.0, shear_minor=0.1
    )
    check = check_member(
        member, steel, "LRFD", demand, length_x=96.0, length_y=48.0, length_ltb=48.0
    )
    ratios = check.ratios
    assert ratios["P-M interaction"] == pytest.approx(
        ratios["Compression"] + ratios["Major flexure"] + ratios["Minor flexure"]
    )
    assert check.equations["P-M interaction"] == "AISI S100-16 H1.2"
    malo = aisi_s100.flexure_local_only(member, steel, "LRFD")
    assert ratios["Flexure and shear"] == pytest.approx(
        math.hypot(20.0 / malo, ratios["Major shear"])
    )
    assert check.equations["Compression"].startswith("AISI S100-16 E")
    assert "Web crippling (G5, H3) is not checked." in check.notes
    assert len(check.notes) == len(set(check.notes))
    assert {c.name for c in check.checks} == set(ratios)
    assert check.governing[0] == "P-M interaction"


def test_p_delta_amplifies_the_moments_of_a_member_in_compression() -> None:
    member = cold_formed_member(_c9(), E)
    demand = Demand(axial=-3.0, moment_major=20.0, moment_minor=2.0, shear_major=0, shear_minor=0)
    lengths = {"length_x": 96.0, "length_y": 48.0, "length_ltb": 48.0}
    plain = check_member(member, _steel(), "LRFD", demand, **lengths)
    amplified = check_member(member, _steel(), "LRFD", demand, p_delta=True, **lengths)
    assert amplified.ratios["Major flexure"] > plain.ratios["Major flexure"]
    assert amplified.ratios["Minor flexure"] > plain.ratios["Minor flexure"]
    assert amplified.ratios["Compression"] == plain.ratios["Compression"]
    assert any("C1.2.1.1" in note for note in amplified.notes)
    tension_demand = Demand(
        axial=3.0, moment_major=20.0, moment_minor=0, shear_major=0, shear_minor=0
    )
    in_tension = check_member(member, _steel(), "LRFD", tension_demand, p_delta=True, **lengths)
    assert not any("C1.2.1.1" in note for note in in_tension.notes)


def test_tension_with_bending_checks_both_flanges() -> None:
    member = cold_formed_member(_c9(), E)
    steel = _steel()
    lengths = {"length_x": 96.0, "length_y": 48.0, "length_ltb": 48.0}
    demand = Demand(axial=10.0, moment_major=30.0, moment_minor=0.0, shear_major=0, shear_minor=0)
    check = check_member(member, steel, "LRFD", demand, **lengths)
    assert check.equations["P-M interaction"] == "AISI S100-16 H1.1"
    t = check.ratios["Tension"]
    on_tension = 30.0 / (0.9 * 55.0 * member.Sx) + t
    on_compression = check.ratios["Major flexure"] - t
    assert check.ratios["P-M interaction"] == pytest.approx(max(on_tension, on_compression))


# ───────────────────────────── sheeting ─────────────────────────────
def test_the_r_factor_follows_the_depth_and_the_profile() -> None:
    """I6.2.1, simple span: 0.70 up to 6.5 in, 0.65 up to 8.5 in, then C 0.40 and Z 0.50."""
    assert uplift_r_factor(cold_formed_member(_c9(), E), inch=1.0) == (0.40, ())
    assert uplift_r_factor(cold_formed_member(_z8(), E), inch=1.0) == (0.65, ())
    deep_zee = _z8().model_copy(update={"d": 10.0, "t": 0.085})
    assert uplift_r_factor(cold_formed_member(deep_zee, E), inch=1.0) == (0.50, ())
    shallow = ColdFormedShape(profile="CS", d=6.0, bf=2.125, t=0.07, r=0.1875, lip=0.6)
    assert uplift_r_factor(cold_formed_member(shallow, E), inch=1.0) == (0.70, ())
    assert uplift_r_factor(cold_formed_member(_c9(), E), inch=1.0, continuous=True) == (0.60, ())
    assert uplift_r_factor(cold_formed_member(_z8(), E), inch=1.0, continuous=True) == (0.70, ())


def test_the_r_factor_is_refused_outside_its_limits() -> None:
    # 150 x 50 mm: the flange is narrower than 2.125 in (54 mm).
    r, reasons = uplift_r_factor(cold_formed_member(_purlin_mm(), 200000.0), inch=25.4)
    assert r is None
    assert reasons == ("flange width 1.97 in < 2.125 in",)
    r, reasons = uplift_r_factor(cold_formed_member(_track(), E), inch=1.0)
    assert r is None
    assert "the flanges have no edge stiffener" in reasons
    # The same channel read in millimetres is 9 mm deep: every length limit depends on the unit.
    assert uplift_r_factor(cold_formed_member(_c9(), E), inch=25.4)[0] is None


def test_sheeting_on_the_compression_flange_braces_the_member() -> None:
    member = cold_formed_member(_c9(), E)
    steel = _steel()
    braced = flexure_major(member, steel, "LRFD", unbraced=0.0)
    unbraced = flexure_major(member, steel, "LRFD", unbraced=240.0)
    sheeted = flexure_sheeted(member, steel, "LRFD", in_compression=True, unbraced=240.0)
    assert sheeted.available == braced.available
    assert sheeted.available > 3.0 * unbraced.available
    assert "the sheeting braces the compression flange" in sheeted.notes[0]


def test_sheeting_on_the_tension_flange_takes_the_r_factor() -> None:
    """Uplift: ``Mn = R Mnlo``, and never less than the discrete braces give."""
    member = cold_formed_member(_c9(), E)
    steel = _steel()
    malo = flexure_local_only(member, steel, "LRFD")
    uplift = flexure_sheeted(member, steel, "LRFD", in_compression=False, unbraced=240.0)
    assert uplift.equation == "AISI S100-16 I6.2.1 R = 0.4"
    assert uplift.available == pytest.approx(0.40 * malo)
    assert _value(uplift, "Globally braced strength") == pytest.approx(malo / 0.9)
    # Braced every 2 ft the member is stronger than R Mnlo: the braces govern.
    close = flexure_sheeted(member, steel, "LRFD", in_compression=False, unbraced=24.0)
    assert close.available == flexure_major(member, steel, "LRFD", unbraced=24.0).available
    assert close.available > uplift.available
    assert "I6.2.1" not in close.equation


def test_outside_the_limits_of_the_r_factor_the_unbraced_length_governs() -> None:
    member = cold_formed_member(_purlin_mm(), 200000.0)
    steel = Steel(Fy=345.0, E=200000.0, G=77000.0, Fu=450.0)
    uplift = flexure_sheeted(
        member, steel, "LRFD", in_compression=False, unbraced=6000.0, cb=1.14, inch=25.4
    )
    plain = flexure_major(member, steel, "LRFD", unbraced=6000.0, cb=1.14)
    assert uplift.available == plain.available
    assert "I6.2.1 does not apply (flange width 1.97 in < 2.125 in)" in uplift.notes[0]


def test_the_member_check_takes_the_side_of_the_sheeting() -> None:
    member = cold_formed_member(_c9(), E)
    lengths = {"length_x": 240.0, "length_y": 240.0, "length_ltb": 240.0}
    demand = Demand(axial=0.0, moment_major=20.0, moment_minor=0, shear_major=0, shear_minor=0)
    bare = check_member(member, _steel(), "LRFD", demand, **lengths)
    gravity = check_member(member, _steel(), "LRFD", demand, sheeted=True, **lengths)
    uplift = check_member(member, _steel(), "LRFD", demand, sheeted=False, **lengths)
    assert gravity.ratios["Major flexure"] < uplift.ratios["Major flexure"]
    assert uplift.ratios["Major flexure"] < bare.ratios["Major flexure"]
    assert uplift.equations["Major flexure"].endswith("I6.2.1 R = 0.4")
    assert gravity.ratios["Major flexure"] == pytest.approx(
        20.0 / flexure_major(member, _steel(), "LRFD", unbraced=0.0).available
    )


# ───────────────────────────── what is covered ─────────────────────────────
def test_the_design_shape_is_cached_and_carries_the_section() -> None:
    first = cold_formed_member(_c9(), E)
    assert cold_formed_member(_c9(), E) is first
    assert cold_formed_member(_c9(), E, name="P1") is not first
    assert first.name == _c9().dimension_name
    assert first.Ix > first.Iy
    assert first.Sx == pytest.approx(first.Ix / 4.5)
    assert first.cy_tips > first.cy_web  # the centroid is nearer the web
    assert first.web_flat == pytest.approx(9.0 - 2 * (0.1875 + 0.059))


@pytest.mark.parametrize(
    ("shape", "message"),
    [
        (ColdFormedShape(profile="HU", d=3.0, bf=4.0, t=0.06, r=0.1, b2=1.0), "hats and angles"),
        (ColdFormedShape(profile="LU", d=3.0, bf=3.0, t=0.06, r=0.1), "hats and angles"),
        (_c9().model_copy(update={"assembly": "box"}), "box or back-to-back"),
        (ColdFormedShape(profile="CU", d=2.0, bf=6.0, t=0.06, r=0.1), "wider than it is deep"),
    ],
)
def test_what_the_check_does_not_cover_says_so(shape: ColdFormedShape, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        cold_formed_member(shape, E)
