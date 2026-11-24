"""AISI S100-16 available strengths of cold-formed steel members by the Direct Strength Method.

The equations of the *North American Specification for the Design of
Cold-Formed Steel Structural Members* (AISI S100-16) a frame check needs, for a
single lipped channel (``CS``), plain channel (``CU``) or lipped zee (``ZS``):

* **D2 / D3** tension: yielding of the gross section and, when the caller
  supplies a net area, rupture of the net section;
* **E2** global buckling in compression (flexural, torsional and
  flexural-torsional), **E3.2** its interaction with local buckling and **E4**
  distortional buckling;
* **F2** lateral-torsional buckling with ``Cb``, **F3.2** its interaction with
  local buckling and **F4** distortional buckling, about both geometric axes;
* **G2.1** shear of a web without stiffeners;
* **H1.1 / H1.2** axial force with biaxial bending and **H2** bending with
  shear.

The elastic local and distortional buckling loads (``Pcrl``, ``Pcrd``,
``Mcrl``, ``Mcrd``) come from the finite strip signature curve of the section
(:mod:`core.design.fsm`, Appendix 2 of the specification allows a rational
analysis). Where the curve has no distinct distortional minimum (often a
lipped channel in compression) the distortional load is the curve's value at
the half-wavelength ``Lcrd`` of the closed-form flange model (Appendix 2,
2.3.1.3 and 2.3.3.3; Schafer and Peköz): the length is from the closed form,
the load from the finite strips. The global buckling stresses are the closed
forms of E2 and F2 with the section's own properties.

Bending is about the geometric axes: ``x`` (major, perpendicular to the web)
and ``y`` (minor). A zee bends about ``x`` as if its sheeting held it
(F2.1.3). The sign of a minor-axis moment is not known to a line model, so the
minor flexural strength is the lower of the two senses (the flange tips or the
web in compression).

Not included: web crippling (G5, H3), the inelastic reserve, holes, built-up
pairs, hats and angles, the R-factor of a purlin under uplift (I6.2.1).

Every function works in one consistent unit system (the project's). LRFD uses
the resistance factors φ, ASD the safety factors Ω. No Qt, no OpenSees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from opensees_studio.core.design import fsm
from opensees_studio.core.design.aisc360 import Demand, MemberCheck, Method, Steel, Strength
from opensees_studio.core.design.calc import CalcStep, LimitStateCheck
from opensees_studio.core.design.stability import b1, pe1, tau_b
from opensees_studio.core.sections.cold_formed import (
    ColdFormedProperties,
    ColdFormedShape,
    outline,
    properties,
)

SPECIFICATION = "AISI S100-16"

#: Resistance factor φ (LRFD) and safety factor Ω (ASD) per limit state.
FACTORS: dict[str, tuple[float, float]] = {
    "tension": (0.90, 1.67),  # D2
    "tension_rupture": (0.75, 2.00),  # D3
    "compression": (0.85, 1.80),  # E1
    "flexure": (0.90, 1.67),  # F1
    "shear": (0.95, 1.60),  # G1
}

#: Profiles the check covers.
CHECKED_PROFILES = frozenset({"CS", "CU", "ZS"})
#: Profiles with an edge stiffener: they can buckle distortionally.
LIPPED_PROFILES = frozenset({"CS", "ZS"})

#: Shear buckling coefficient of a web without transverse stiffeners (G2.3).
KV_UNREINFORCED = 5.34

#: Stress gradient of the web in pure bending, (f1 - f2) / f1 (Appendix 2, 2.3.3.3).
XI_WEB_BENDING = 2.0


def _available(nominal: float, kind: str, method: Method) -> float:
    phi, omega = FACTORS[kind]
    return phi * nominal if method == "LRFD" else nominal / omega


def _step(label: str, formula: str, value: float, substitution: str = "") -> CalcStep:
    return CalcStep(label, formula, substitution or f"{value:.6g}", value)


# ───────────────────────────── elastic buckling ─────────────────────────────
@dataclass(frozen=True)
class Buckling:
    """Elastic local and distortional buckling load of one loading (``Pcr`` or ``Mcr``)."""

    local: float
    local_length: float
    distortional: float | None = None
    distortional_length: float | None = None
    local_is_minimum: bool = True
    """False when the signature curve has no local minimum and its lowest value
    over half-wavelengths up to the section's size was taken."""
    distortional_is_minimum: bool = True
    """False when the curve has no distortional minimum and its value at the
    closed-form ``Lcrd`` was taken."""


def _flange_properties(shape: ColdFormedShape) -> dict[str, float]:
    """The compression flange and its lip about their own centroid (Appendix 2, Table 2.3.1.3-1).

    ``b`` and ``d`` are the midline flange width and lip length, θ the lip's
    angle to the flange. ``x`` runs along the flange from the web; the shear
    centre of the two plates is their junction, so the warping constant is 0.
    """
    t = shape.t
    theta = math.radians(shape.lip_angle if shape.profile == "ZS" else 90.0)
    b = shape.bf - t
    d = shape.lip - t / 2.0
    c, s = math.cos(theta), math.sin(theta)
    total = b + d
    return {
        "Af": total * t,
        "Jf": total * t**3 / 3.0,
        "Ixf": t
        * (t**2 * b**2 + 4 * b * d**3 * s**2 + t**2 * b * d + d**4 * s**2)
        / (12.0 * total),
        "Iyf": t
        * (b**4 + 4 * d * b**3 + 6 * d**2 * b**2 * c + 4 * d**3 * b * c**2 + d**4 * c**2)
        / (12.0 * total),
        "Ixyf": t * b * d**2 * s * (b + d * c) / (4.0 * total),
        "xof": (b**2 - d**2 * c) / (2.0 * total),
        "hxf": -(b**2 + 2 * d * b + d**2 * c) / (2.0 * total),
        "yof": -(d**2) * s / (2.0 * total),
    }


def distortional_closed_form(
    shape: ColdFormedShape, elastic_modulus: float, nu: float = 0.3, *, bending: bool = False
) -> tuple[float, float]:
    """``(Fcrd, Lcrd)`` of a lipped channel or zee by the flange model of Appendix 2.

    ``Fcrd = (kφfe + kφwe) / (k̃φfg + k̃φwg)`` at the critical half-wavelength
    ``Lcrd``: the rotational stiffness the flange and the web give the
    flange-web junction over the geometric stiffness they demand, in uniform
    compression (2.3.1.3) or in bending about the axis perpendicular to the
    web (2.3.3.3). No bracing of the flange is counted (``kφ = 0``, ``β = 1``).
    """
    if shape.profile not in LIPPED_PROFILES:
        raise ValueError("Distortional buckling needs a lipped channel or zee.")
    f = _flange_properties(shape)
    t, ho = shape.t, shape.d
    g = elastic_modulus / (2.0 * (1.0 + nu))
    arm = f["xof"] - f["hxf"]
    core = f["Ixf"] * arm**2 - f["Ixyf"] ** 2 / f["Iyf"] * arm**2
    plate = math.pi**4 * ho * (1.0 - nu**2) / t**3
    if bending:
        length = (4.0 * plate * core + math.pi**4 * ho**4 / 720.0) ** 0.25
    else:
        length = (6.0 * plate * core) ** 0.25
    k = math.pi / length
    flange_elastic = k**4 * elastic_modulus * core + k**2 * g * f["Jf"]
    ratio = f["Ixyf"] / f["Iyf"]
    flange_geometric = k**2 * (
        f["Af"] * (arm**2 * ratio**2 - 2.0 * f["yof"] * arm * ratio + f["hxf"] ** 2 + f["yof"] ** 2)
        + f["Ixf"]
        + f["Iyf"]
    )
    bending_rigidity = elastic_modulus * t**3 / (12.0 * (1.0 - nu**2))
    if bending:
        web_elastic = bending_rigidity * (3.0 / ho + k**2 * 19.0 * ho / 60.0 + k**4 * ho**3 / 240.0)
        slender = length / ho
        xi = XI_WEB_BENDING
        web_geometric = (
            ho
            * t
            * math.pi**2
            / 13440.0
            * (
                (45360.0 * (1.0 - xi) + 62160.0) * slender**2
                + 448.0 * math.pi**2
                + (53.0 + 3.0 * (1.0 - xi)) * math.pi**4 / slender**2
            )
            / (math.pi**4 + 28.0 * math.pi**2 * slender**2 + 420.0 * slender**4)
        )
    else:
        web_elastic = 2.0 * bending_rigidity / ho
        web_geometric = k**2 * t * ho**3 / 60.0
    stress = (flange_elastic + web_elastic) / (flange_geometric + web_geometric)
    return stress, length


def _classify(
    model: fsm.StripModel,
    stress: np.ndarray,
    reference: float,
    size: float,
    lcrd: float | None,
    *,
    fallback: bool,
) -> Buckling:
    """Local and distortional loads off one signature curve.

    A minimum is local up to the geometric mean of the section's size and
    ``Lcrd``, distortional beyond; without ``Lcrd`` (no lips) every minimum is
    local. ``fallback`` reads the curve at ``Lcrd`` when it has no distortional
    minimum.
    """
    curve = fsm.signature_curve(model, stress)
    minima = curve.minima()
    limit = math.sqrt(size * lcrd) if lcrd is not None else math.inf
    local_minima = [m for m in minima if m[0] <= limit]
    later = [m for m in minima if m[0] > limit]
    if local_minima:
        local_length, local = min(local_minima, key=lambda m: m[1])
        local_is_minimum = True
    else:
        short = curve.lengths <= size
        k = int(np.argmin(np.where(short, curve.factors, np.inf)))
        local_length, local = float(curve.lengths[k]), float(curve.factors[k])
        local_is_minimum = False
    distortional: float | None = None
    distortional_length: float | None = None
    distortional_is_minimum = True
    if later:
        distortional_length, distortional = later[0]
    elif lcrd is not None and fallback:
        factor = fsm.buckling_factor(model, stress, lcrd)[0]
        if math.isfinite(factor):
            distortional, distortional_length = factor, lcrd
            distortional_is_minimum = False
    return Buckling(
        local=local * reference,
        local_length=local_length,
        distortional=None if distortional is None else distortional * reference,
        distortional_length=distortional_length,
        local_is_minimum=local_is_minimum,
        distortional_is_minimum=distortional_is_minimum,
    )


# ───────────────────────────── the design shape ─────────────────────────────
@dataclass(frozen=True)
class ColdFormedMember:
    """A cold-formed profile with what the Direct Strength Method needs of it.

    The buckling loads do not depend on the yield stress, so one of these
    serves every member made of the section.
    """

    name: str
    shape: ColdFormedShape
    props: ColdFormedProperties
    E: float
    nu: float
    axial: Buckling
    """``Pcrl`` and ``Pcrd``."""
    bending_x: Buckling
    """``Mcrl`` and ``Mcrd`` about x (the major axis)."""
    bending_y_tips: Buckling
    """About y with the flange tips (+x) in compression."""
    bending_y_web: Buckling
    """About y with the web side (-x) in compression."""
    cx: float
    """Extreme fibre from the centroid for bending about x."""
    cy_tips: float
    """Extreme fibre on the flange-tip side (+x) for bending about y."""
    cy_web: float
    """Extreme fibre on the web side (-x)."""

    @property
    def A(self) -> float:
        return self.props.A

    @property
    def Ix(self) -> float:
        return self.props.Ix

    @property
    def Iy(self) -> float:
        return self.props.Iy

    @property
    def J(self) -> float:
        return self.props.J

    @property
    def Cw(self) -> float:
        return self.props.Cw

    @property
    def d(self) -> float:
        return self.shape.d

    @property
    def bf(self) -> float:
        return self.shape.bf

    @property
    def t(self) -> float:
        return self.shape.t

    @property
    def Sx(self) -> float:
        """Elastic section modulus about x."""
        return self.props.Ix / self.cx

    @property
    def Sy(self) -> float:
        """Elastic section modulus about y at the fibre that yields first."""
        return self.props.Iy / max(self.cy_tips, self.cy_web)

    @property
    def rx(self) -> float:
        return math.sqrt(self.props.Ix / self.props.A)

    @property
    def ry(self) -> float:
        return math.sqrt(self.props.Iy / self.props.A)

    @property
    def web_flat(self) -> float:
        """Flat depth of the web."""
        return self.shape.d - 2.0 * (self.shape.r + self.shape.t)

    @property
    def flange_flat(self) -> float:
        """Flat width of a flange."""
        bends = 2.0 if self.shape.profile in LIPPED_PROFILES else 1.0
        return self.shape.bf - bends * (self.shape.r + self.shape.t)


@lru_cache(maxsize=64)
def _member(shape_json: str, name: str, elastic_modulus: float, nu: float) -> ColdFormedMember:
    shape = ColdFormedShape.model_validate_json(shape_json)
    props = properties(shape)
    model = fsm.strip_model(shape, elastic_modulus, nu)
    size = float(max(shape.d, shape.bf))
    lipped = shape.profile in LIPPED_PROFILES
    lcrd_axial = lcrd_bending = None
    if lipped:
        lcrd_axial = distortional_closed_form(shape, elastic_modulus, nu)[1]
        lcrd_bending = distortional_closed_form(shape, elastic_modulus, nu, bending=True)[1]
    x_mid = model.nodes[:, 0] - props.xc
    y_mid = model.nodes[:, 1] - props.yc
    # The finite strip reference is a unit stress at the extreme midline node:
    # the moment that produces it is I over that node's distance.
    mx_ref = props.Ix / float(np.abs(y_mid).max())
    my_ref = props.Iy / float(np.abs(x_mid).max())
    points = outline(shape)
    xs = [x - props.xc for x, _ in points]
    ys = [y - props.yc for _, y in points]
    return ColdFormedMember(
        name=name or shape.dimension_name,
        shape=shape,
        props=props,
        E=elastic_modulus,
        nu=nu,
        axial=_classify(model, fsm.axial_stress(model), props.A, size, lcrd_axial, fallback=True),
        bending_x=_classify(
            model, fsm.bending_stress(model, props, "x"), mx_ref, size, lcrd_bending, fallback=True
        ),
        bending_y_tips=_classify(
            model, fsm.bending_stress(model, props, "y"), my_ref, size, lcrd_axial, fallback=True
        ),
        bending_y_web=_classify(
            model,
            fsm.bending_stress(model, props, "y", positive=False),
            my_ref,
            size,
            lcrd_axial,
            fallback=False,
        ),
        cx=max(abs(y) for y in ys),
        cy_tips=max(xs),
        cy_web=-min(xs),
    )


def cold_formed_member(
    shape: ColdFormedShape, elastic_modulus: float, nu: float = 0.3, *, name: str = ""
) -> ColdFormedMember:
    """The design shape of ``shape``: its properties and elastic buckling loads (cached).

    Raises:
        ValueError: a profile or an assembly the check does not cover.
    """
    if shape.assembly != "single":
        raise ValueError("a box or back-to-back pair of channels is not covered yet")
    if shape.profile not in CHECKED_PROFILES:
        raise ValueError(f"profile {shape.profile} (hats and angles) is not covered yet")
    props = properties(shape)
    if props.Ix < props.Iy:
        raise ValueError("a profile wider than it is deep is not covered")
    return _member(shape.model_dump_json(), name, float(elastic_modulus), float(nu))


# ───────────────────────────── global buckling stresses ─────────────────────────────
def _euler(elastic_modulus: float, length: float, radius: float) -> float:
    """``π² E / (KL / r)²``; infinite for a zero length."""
    if length <= 0.0:
        return math.inf
    return math.pi**2 * elastic_modulus / (length / radius) ** 2


def _torsional(member: ColdFormedMember, steel: Steel, length: float) -> float:
    """``sigma_t = (G J + π² E Cw / (Kt Lt)²) / (A ro²)``."""
    p = member.props
    if length <= 0.0:
        return math.inf
    return (steel.G * p.J + math.pi**2 * steel.E * p.Cw / length**2) / (p.A * p.ro**2)


def _column_stress(fy: float, fcre: float) -> float:
    """E2: ``Fn`` from the global buckling stress ``Fcre``."""
    if not math.isfinite(fcre):
        return fy
    lam = math.sqrt(fy / fcre)
    if lam <= 1.5:
        return float(0.658 ** (lam**2)) * fy
    return 0.877 / lam**2 * fy


def _beam_stress(fy: float, fcre: float) -> float:
    """F2.1: ``Fn`` from the lateral-torsional buckling stress ``Fcre``."""
    if fcre >= 2.78 * fy:
        return fy
    if fcre > 0.56 * fy:
        return 10.0 / 9.0 * fy * (1.0 - 10.0 * fy / (36.0 * fcre))
    return fcre


def _local(global_strength: float, critical: float) -> tuple[float, float]:
    """E3.2.1 / F3.2.1: ``(λl, strength)`` of local buckling interacting with the global one."""
    lam = math.sqrt(global_strength / critical)
    if lam <= 0.776:
        return lam, global_strength
    ratio = (critical / global_strength) ** 0.4
    return lam, (1.0 - 0.15 * ratio) * ratio * global_strength


def _distortional_column(py: float, pcrd: float) -> tuple[float, float]:
    """E4.1: ``(λd, Pnd)``."""
    lam = math.sqrt(py / pcrd)
    if lam <= 0.561:
        return lam, py
    ratio = (pcrd / py) ** 0.6
    return lam, (1.0 - 0.25 * ratio) * ratio * py


def _distortional_beam(my: float, mcrd: float) -> tuple[float, float]:
    """F4.1: ``(λd, Mnd)``."""
    lam = math.sqrt(my / mcrd)
    if lam <= 0.673:
        return lam, my
    ratio = (mcrd / my) ** 0.5
    return lam, (1.0 - 0.22 * ratio) * ratio * my


def _buckling_notes(buckling: Buckling, what: str) -> list[str]:
    notes = []
    if not buckling.local_is_minimum:
        notes.append(
            f"{what}: the signature curve has no local minimum; its lowest value up to the "
            "section's size was taken."
        )
    if buckling.distortional is not None and not buckling.distortional_is_minimum:
        notes.append(
            f"{what}: the signature curve has no distortional minimum; its value at the "
            f"closed-form Lcrd = {buckling.distortional_length:.4g} was taken (Appendix 2)."
        )
    return notes


# ───────────────────────────── tension and compression ─────────────────────────────
def tension(
    member: ColdFormedMember,
    steel: Steel,
    method: Method,
    *,
    net_area: float | None = None,
    shear_lag: float = 1.0,
) -> Strength:
    """D2 yielding of the gross section and, with a net area and ``Fu``, D3 rupture."""
    yielding = steel.Fy * member.A
    candidates: list[tuple[float, float, str, tuple[CalcStep, ...]]] = [
        (
            _available(yielding, "tension", method),
            yielding,
            "D2 yielding",
            (_step("D2 yielding", "Tn = Ag Fy", yielding, f"{member.A:g} x {steel.Fy:g}"),),
        )
    ]
    notes: list[str] = []
    if net_area is None:
        notes.append("Tensile rupture (D3) needs the net area and is not checked.")
    elif steel.Fu is None:
        notes.append("Tensile rupture (D3) needs Fu and is not checked.")
    else:
        if net_area <= 0.0:
            raise ValueError("net_area must be positive")
        if not 0.0 < shear_lag <= 1.0:
            raise ValueError("shear_lag must be in (0, 1]")
        effective = shear_lag * net_area
        rupture = steel.Fu * effective
        candidates.append(
            (
                _available(rupture, "tension_rupture", method),
                rupture,
                "D3 rupture",
                (
                    _step("Effective net area", "Ae = U An", effective),
                    _step("D3 rupture", "Tn = Ae Fu", rupture, f"{effective:g} x {steel.Fu:g}"),
                ),
            )
        )
    available, nominal, equation, steps = min(candidates, key=lambda c: c[0])
    return Strength(nominal, available, f"{SPECIFICATION} {equation}", tuple(notes), steps)


def global_column_stress(
    member: ColdFormedMember,
    steel: Steel,
    *,
    length_x: float,
    length_y: float,
    length_t: float,
) -> tuple[float, str]:
    """E2: the elastic global buckling stress ``Fcre`` and the mode that gives it.

    A channel is singly symmetric about x: flexural buckling about y, or
    flexural-torsional buckling (about x with torsion, E2.2). A zee is
    point-symmetric: torsional buckling, or flexural buckling about its minor
    principal axis over the longer of the two lengths (E2.3).
    """
    p = member.props
    sigma_t = _torsional(member, steel, length_t)
    if member.shape.profile == "ZS":
        r2 = math.sqrt(p.I2 / p.A)
        flexural = _euler(steel.E, max(length_x, length_y), r2)
        return min((flexural, "flexural, minor principal axis"), (sigma_t, "torsional"))
    sigma_ex = _euler(steel.E, length_x, member.rx)
    sigma_ey = _euler(steel.E, length_y, member.ry)
    beta = 1.0 - (p.x0 / p.ro) ** 2
    if math.isinf(sigma_ex) or math.isinf(sigma_t):
        flexural_torsional = min(sigma_ex, sigma_t)
    else:
        total = sigma_ex + sigma_t
        flexural_torsional = (
            total - math.sqrt(max(0.0, total**2 - 4.0 * beta * sigma_ex * sigma_t))
        ) / (2.0 * beta)
    return min((sigma_ey, "flexural about y"), (flexural_torsional, "flexural-torsional"))


def compression(
    member: ColdFormedMember,
    steel: Steel,
    method: Method,
    *,
    length_x: float,
    length_y: float,
    length_t: float | None = None,
    k_x: float = 1.0,
    k_y: float = 1.0,
    k_t: float = 1.0,
) -> Strength:
    """E2 to E4: the least of global, local-global and distortional buckling.

    ``length_t`` is the unbraced length for twisting; the minor-axis length
    when not given (a brace of the weak axis is taken to hold the twist too).
    """
    torsion_length = k_t * (length_y if length_t is None else length_t)
    fcre, mode = global_column_stress(
        member, steel, length_x=k_x * length_x, length_y=k_y * length_y, length_t=torsion_length
    )
    py = steel.Fy * member.A
    fn = _column_stress(steel.Fy, fcre)
    pne = fn * member.A
    lam_l, pnl = _local(pne, member.axial.local)
    steps = [
        _step("Yield load", "Py = Ag Fy", py),
        _step(f"E2 global buckling stress ({mode})", "Fcre", fcre),
        _step("E2 global buckling", "Pne = Ag Fn", pne, f"Fn = {fn:.6g}"),
        _step("Local buckling load (finite strips)", "Pcrl", member.axial.local),
        _step("E3.2.1 local slenderness", "lambda_l = sqrt(Pne / Pcrl)", lam_l),
        _step("E3.2.1 local-global buckling", "Pnl", pnl),
    ]
    first = "E2 yielding" if pne >= py else "E2 global buckling"
    candidates = [(pne, first), (pnl, "E3.2.1 local buckling")]
    if member.axial.distortional is not None:
        lam_d, pnd = _distortional_column(py, member.axial.distortional)
        steps += [
            _step("Distortional buckling load (finite strips)", "Pcrd", member.axial.distortional),
            _step("E4.1 distortional slenderness", "lambda_d = sqrt(Py / Pcrd)", lam_d),
            _step("E4.1 distortional buckling", "Pnd", pnd),
        ]
        candidates.append((pnd, "E4.1 distortional buckling"))
    nominal, equation = min(candidates)
    steps.append(_step("Nominal strength", "Pn = min(Pne, Pnl, Pnd)", nominal))
    return Strength(
        nominal,
        _available(nominal, "compression", method),
        f"{SPECIFICATION} {equation}",
        tuple(_buckling_notes(member.axial, "Compression")),
        tuple(steps),
    )


# ───────────────────────────── flexure ─────────────────────────────
def _flexure(
    my: float,
    mne: float,
    buckling: Buckling,
    steps: list[CalcStep],
) -> tuple[float, str]:
    """F3.2.1 and F4.1 on top of the global strength ``Mne``; appends to ``steps``."""
    lam_l, mnl = _local(mne, buckling.local)
    steps += [
        _step("Local buckling moment (finite strips)", "Mcrl", buckling.local),
        _step("F3.2.1 local slenderness", "lambda_l = sqrt(Mne / Mcrl)", lam_l),
        _step("F3.2.1 local-global buckling", "Mnl", mnl),
    ]
    first = "F2.1 yielding" if mne >= my else "F2.1 lateral-torsional buckling"
    candidates = [(mne, first), (mnl, "F3.2.1 local buckling")]
    if buckling.distortional is not None:
        lam_d, mnd = _distortional_beam(my, buckling.distortional)
        steps += [
            _step("Distortional buckling moment (finite strips)", "Mcrd", buckling.distortional),
            _step("F4.1 distortional slenderness", "lambda_d = sqrt(My / Mcrd)", lam_d),
            _step("F4.1 distortional buckling", "Mnd", mnd),
        ]
        candidates.append((mnd, "F4.1 distortional buckling"))
    return min(candidates)


def flexure_major(
    member: ColdFormedMember,
    steel: Steel,
    method: Method,
    *,
    unbraced: float,
    cb: float = 1.0,
) -> Strength:
    """F2 to F4 about x: lateral-torsional, local and distortional buckling.

    ``Fcre = Cb ro A sqrt(sigma_ey sigma_t) / Sf`` for a channel (F2.1.1) and half that
    for a zee held to bend about x (F2.1.3). ``unbraced`` is the laterally
    unbraced length, also taken for the twist; 0 is a fully braced member.
    """
    p = member.props
    sf = member.Sx
    my = steel.Fy * sf
    steps = [_step("Yield moment", "My = Sf Fy", my, f"{sf:.6g} x {steel.Fy:g}")]
    if unbraced <= 0.0:
        fcre = math.inf
        fn = steel.Fy
    else:
        sigma_ey = _euler(steel.E, unbraced, member.ry)
        sigma_t = _torsional(member, steel, unbraced)
        fcre = cb * p.ro * p.A * math.sqrt(sigma_ey * sigma_t) / sf
        if member.shape.profile == "ZS":
            fcre /= 2.0
        fn = _beam_stress(steel.Fy, fcre)
        steps.append(
            _step(
                "F2.1 lateral-torsional buckling stress",
                "Fcre = Cb ro A sqrt(sey st) / Sf"
                + (" / 2" if member.shape.profile == "ZS" else ""),
                fcre,
                f"Cb = {cb:.4g}, Lb = {unbraced:.6g}",
            )
        )
    mne = min(fn * sf, my)
    steps.append(_step("F2.1 lateral-torsional buckling", "Mne = Sf Fn <= My", mne))
    nominal, equation = _flexure(my, mne, member.bending_x, steps)
    steps.append(_step("Nominal strength", "Mn = min(Mne, Mnl, Mnd)", nominal))
    notes = _buckling_notes(member.bending_x, "Major flexure")
    if member.shape.profile == "ZS":
        notes.append("The zee bends about the axis perpendicular to its web (F2.1.3).")
    return Strength(
        nominal,
        _available(nominal, "flexure", method),
        f"{SPECIFICATION} {equation}",
        tuple(notes),
        tuple(steps),
    )


def _flexure_minor_sense(
    member: ColdFormedMember, steel: Steel, *, unbraced: float, tips: bool
) -> tuple[float, str, list[CalcStep]]:
    """Minor-axis strength with the flange tips (or the web) in compression."""
    p = member.props
    sense = "flange tips in compression" if tips else "web in compression"
    sf = p.Iy / (member.cy_tips if tips else member.cy_web)
    my = steel.Fy * member.Sy
    steps = [_step(f"Yield moment ({sense})", "My = Sfy Fy", my)]
    fn = steel.Fy
    if member.shape.profile != "ZS" and unbraced > 0.0:
        # F2.1.2: bending about the axis perpendicular to the axis of symmetry.
        sigma_ex = _euler(steel.E, unbraced, member.rx)
        sigma_t = _torsional(member, steel, unbraced)
        j = abs(p.jy)
        cs = -1.0 if tips else 1.0  # +1: compression on the shear centre's side
        fcre = cs * p.A * sigma_ex / sf * (j + cs * math.sqrt(j**2 + p.ro**2 * sigma_t / sigma_ex))
        fn = _beam_stress(steel.Fy, fcre)
        steps.append(
            _step(
                "F2.1.2 lateral-torsional buckling stress",
                "Fcre = Cs A sex (j + Cs sqrt(j^2 + ro^2 st/sex)) / (CTF Sf)",
                fcre,
                f"Cs = {cs:+g}, CTF = 1, j = {j:.6g}",
            )
        )
    mne = min(fn * sf, my)
    steps.append(_step("F2.1 lateral-torsional buckling", "Mne = Sf Fn <= My", mne))
    nominal, equation = _flexure(
        my, mne, member.bending_y_tips if tips else member.bending_y_web, steps
    )
    return nominal, equation, steps


def flexure_minor(
    member: ColdFormedMember,
    steel: Steel,
    method: Method,
    *,
    unbraced: float,
) -> Strength:
    """F2 to F4 about y: the lower of the two senses of the moment.

    A channel bent about y buckles laterally about x with twist (F2.1.2,
    ``CTF = 1``); a zee has no lateral-torsional buckling about its weaker
    geometric axis.
    """
    senses = [
        _flexure_minor_sense(member, steel, unbraced=unbraced, tips=tips) for tips in (True, False)
    ]
    nominal, equation, steps = min(senses, key=lambda s: s[0])
    steps = [*steps, _step("Nominal strength", "Mn = min(Mne, Mnl, Mnd)", nominal)]
    notes = [
        "Minor flexure: the lower strength of the two senses of the moment "
        "(flange tips or web in compression).",
        *_buckling_notes(member.bending_y_tips, "Minor flexure"),
    ]
    return Strength(
        nominal,
        _available(nominal, "flexure", method),
        f"{SPECIFICATION} {equation}",
        tuple(notes),
        tuple(steps),
    )


def flexure_local_only(member: ColdFormedMember, steel: Steel, method: Method) -> float:
    """``Malo``: the available major-axis strength of a globally braced member (H2)."""
    my = steel.Fy * member.Sx
    return _available(_local(my, member.bending_x.local)[1], "flexure", method)


# ───────────────────────────── shear ─────────────────────────────
def _shear(
    flat: float, count: int, t: float, steel: Steel, nu: float
) -> tuple[float, list[CalcStep]]:
    """G2.1 with the elastic buckling of G2.3 for ``count`` flats of width ``flat``."""
    area = count * flat * t
    vy = 0.6 * area * steel.Fy
    fcr = math.pi**2 * steel.E * KV_UNREINFORCED / (12.0 * (1.0 - nu**2) * (flat / t) ** 2)
    vcr = area * fcr
    lam = math.sqrt(vy / vcr)
    if lam <= 0.815:
        vn = vy
    elif lam <= 1.227:
        vn = 0.815 * math.sqrt(vcr * vy)
    else:
        vn = vcr
    steps = [
        _step("Shear yield", "Vy = 0.6 Aw Fy", vy, f"Aw = {area:.6g}"),
        _step("G2.3 shear buckling", "Vcr = Aw pi^2 E kv / (12 (1 - mu^2) (h/t)^2)", vcr,
              f"kv = {KV_UNREINFORCED:g}, h/t = {flat / t:.4g}"),
        _step("G2.1 slenderness", "lambda_v = sqrt(Vy / Vcr)", lam),
        _step("G2.1 shear strength", "Vn", vn),
    ]  # fmt: skip
    return vn, steps


def shear_major(member: ColdFormedMember, steel: Steel, method: Method) -> Strength:
    """G2.1: shear along the web, without transverse stiffeners."""
    vn, steps = _shear(member.web_flat, 1, member.shape.t, steel, member.nu)
    return Strength(
        vn, _available(vn, "shear", method), f"{SPECIFICATION} G2.1 web shear", (), tuple(steps)
    )


def shear_minor(member: ColdFormedMember, steel: Steel, method: Method) -> Strength:
    """Shear across the depth: the two flanges taken as webs (G2.1)."""
    vn, steps = _shear(member.flange_flat, 2, member.shape.t, steel, member.nu)
    return Strength(
        vn,
        _available(vn, "shear", method),
        f"{SPECIFICATION} G2.1 flange shear",
        ("Minor shear: the two flanges as webs of G2.1 (kv = 5.34).",),
        tuple(steps),
    )


# ───────────────────────────── a member check ─────────────────────────────
def _record(check: MemberCheck, name: str, strength: Strength, demand: float) -> None:
    capacity = strength.available
    ratio = abs(demand) / capacity if capacity > 0.0 else math.inf
    check.ratios[name] = ratio
    check.equations[name] = strength.equation
    steps = (
        *strength.steps,
        _step("Available strength", "phi Rn (LRFD) / Rn / Omega (ASD)", capacity),
    )
    check.checks.append(
        LimitStateCheck(
            name, strength.equation, abs(demand), capacity, ratio, steps, strength.notes
        )
    )
    check.notes.extend(strength.notes)


def check_member(
    member: ColdFormedMember,
    steel: Steel,
    method: Method,
    demand: Demand,
    *,
    length_x: float,
    length_y: float,
    length_ltb: float,
    k_x: float = 1.0,
    k_y: float = 1.0,
    net_area: float | None = None,
    shear_lag: float = 1.0,
    p_delta: bool = False,
) -> MemberCheck:
    """Ratios of axial force, flexure, shear and the H1 and H2 interactions for one demand.

    With ``p_delta``, a member in compression gets its moments amplified by
    ``B1 = 1 / (1 - α P / Pe1)`` (C1.2.1.1, ``Cm = 1``) with ``Pe1`` on
    ``0.90 τb EI``.
    """
    check = MemberCheck()
    mrx = demand.moment_major
    mry = demand.moment_minor
    if p_delta and demand.axial < 0.0:
        alpha = 1.0 if method == "LRFD" else 1.6
        rigidity = 0.9 * tau_b(-demand.axial, steel.Fy * member.A, alpha=alpha) * steel.E
        b_major = b1(-demand.axial, pe1(rigidity, member.Ix, length_x, k=k_x), alpha=alpha)
        b_minor = b1(-demand.axial, pe1(rigidity, member.Iy, length_y, k=k_y), alpha=alpha)
        mrx *= b_major
        mry *= b_minor
        check.notes.append(
            f"P-delta (C1.2.1.1): B1 = {b_major:.3f} major, {b_minor:.3f} minor, "
            "Pe1 on 0.90 tau_b EI."
        )
    in_tension = demand.axial >= 0.0
    if in_tension:
        axial = tension(member, steel, method, net_area=net_area, shear_lag=shear_lag)
        label = "Tension"
    else:
        axial = compression(
            member, steel, method, length_x=length_x, length_y=length_y, k_x=k_x, k_y=k_y
        )
        label = "Compression"
    major = flexure_major(member, steel, method, unbraced=length_ltb, cb=demand.cb)
    minor = flexure_minor(member, steel, method, unbraced=length_ltb)
    v_major = shear_major(member, steel, method)
    v_minor = shear_minor(member, steel, method)
    for strength, name, value in (
        (axial, label, demand.axial),
        (major, "Major flexure", mrx),
        (minor, "Minor flexure", mry),
        (v_major, "Major shear", demand.shear_major),
        (v_minor, "Minor shear", demand.shear_minor),
    ):
        _record(check, name, strength, value)

    p = abs(demand.axial) / axial.available
    mx = abs(mrx) / major.available
    my = abs(mry) / minor.available
    if in_tension:
        # H1.1: the tension flange (yield moments), and the compression flange
        # relieved by the tension.
        mxt = _available(steel.Fy * member.Sx, "flexure", method)
        myt = _available(steel.Fy * member.Sy, "flexure", method)
        on_tension = abs(mrx) / mxt + abs(mry) / myt + p
        on_compression = mx + my - p
        ratio = max(on_tension, on_compression)
        equation = f"{SPECIFICATION} H1.1"
        steps = (
            _step("Tension flange", "Mx/Maxt + My/Mayt + T/Ta", on_tension),
            _step("Compression flange", "Mx/Max + My/May - T/Ta", on_compression),
            _step("Interaction", "H1.1", ratio),
        )
    else:
        ratio = p + mx + my
        equation = f"{SPECIFICATION} H1.2"
        steps = (
            _step("Axial ratio", "P / Pa", p),
            _step("Moment ratio", "Mx/Max + My/May", mx + my),
            _step("Interaction", "P/Pa + Mx/Max + My/May", ratio),
        )
    check.ratios["P-M interaction"] = ratio
    check.equations["P-M interaction"] = equation
    check.checks.append(LimitStateCheck("P-M interaction", equation, ratio, 1.0, ratio, steps))

    malo = flexure_local_only(member, steel, method)
    bending = abs(mrx) / malo
    shear = abs(demand.shear_major) / v_major.available
    combined = math.hypot(bending, shear)
    equation = f"{SPECIFICATION} H2"
    check.ratios["Flexure and shear"] = combined
    check.equations["Flexure and shear"] = equation
    check.checks.append(
        LimitStateCheck(
            "Flexure and shear",
            equation,
            combined,
            1.0,
            combined,
            (
                _step("Globally braced flexural strength", "Malo", malo),
                _step("Bending ratio", "M / Malo", bending),
                _step("Shear ratio", "V / Va", shear),
                _step("Interaction", "sqrt((M/Malo)^2 + (V/Va)^2)", combined),
            ),
        )
    )
    note = "Web crippling (G5, H3) is not checked."
    check.notes.append(note)
    check.notes[:] = list(dict.fromkeys(check.notes))
    return check


__all__ = [
    "CHECKED_PROFILES",
    "FACTORS",
    "SPECIFICATION",
    "Buckling",
    "ColdFormedMember",
    "check_member",
    "cold_formed_member",
    "compression",
    "distortional_closed_form",
    "flexure_local_only",
    "flexure_major",
    "flexure_minor",
    "global_column_stress",
    "shear_major",
    "shear_minor",
    "tension",
]
