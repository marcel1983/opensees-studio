"""AISC 341-22 Section D1.1: width-to-thickness limits of ductile members.

The seismic provisions classify members as *highly ductile* or *moderately
ductile* and cap the width-to-thickness ratio of their compression elements.
Table D1.1a covers diagonal braces; Table D1.1b covers every other member.

The limits use the expected yield stress ``Ry Fy`` and, for webs under combined
axial force and flexure, the axial ratio

    Ca = Pr / (alpha_s Ry Fy Ag)      D1.1b footnote [b]

with ``alpha_s = 1.0`` in LRFD and ``1.5`` in ASD. Case 11 (webs of moment
frames) and case 13 (webs of braced frames and box sections) are the two that
depend on ``Ca``; case 13 switches expression at ``Ca = 0.113`` and has a floor.

The functions return the limiting ratio itself; the caller compares it with the
element's ratio and reports the case. No Qt, no OpenSees. The limits are those
of ANSI/AISC 341-22, Tables D1.1a and D1.1b, as published.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from opensees_studio.core.design.aisc360 import IShape
from opensees_studio.core.design.aisc360_shapes import (
    Channel,
    EqualLegAngle,
    RectHSS,
    RoundHSS,
    Tee,
)

Ductility = Literal["moderate", "high"]
Method = Literal["LRFD", "ASD"]
Role = Literal["brace", "beam", "column"]

#: Tables D1.1a and D1.1b: (highly ductile, moderately ductile) coefficients.
#: The simple cases are ``coefficient * sqrt(E / (Ry Fy))``.
_SIMPLE: dict[int, tuple[float, float]] = {
    1: (0.30, 0.38),
    2: (0.55, 0.64),
    3: (0.038, 0.044),
    4: (1.49, 1.49),
    5: (1.40, 2.26),
    6: (0.076, 0.15),
    7: (0.30, 0.38),
    8: (0.47, 0.54),
    12: (0.55, 1.00),
    14: (0.55, 0.64),
    15: (0.064, 1.67),
    16: (0.038, 0.070),
    17: (1.40, 2.26),
    18: (0.076, 0.15),
}
#: Cases that only have a moderately ductile limit (H-piles).
_MODERATE_ONLY: dict[int, float] = {9: 0.45, 10: 1.50}
#: Case 13 switches branch at this Ca.
_CASE_13_BREAK = 0.113
#: Case 13 never goes below this fraction of ``sqrt(E / (Ry Fy))``.
_CASE_13_FLOOR = 1.56


def alpha_s(method: Method) -> float:
    """D1.1b [b]: the LRFD-ASD force level adjustment of ``Ca``."""
    if method == "LRFD":
        return 1.0
    if method == "ASD":
        return 1.5
    raise ValueError(f"Unknown design method {method!r}: use 'LRFD' or 'ASD'.")


def ca(
    pr: float,
    ry: float,
    fy: float,
    ag: float,
    *,
    method: Method = "LRFD",
) -> float:
    """D1.1b [b]: ``Ca = Pr / (alpha_s Ry Fy Ag)``.

    ``pr`` is the required axial strength (compression positive here, the sign
    of the demand ratio). A negative or zero value gives 0.
    """
    if ry <= 0.0 or fy <= 0.0 or ag <= 0.0:
        raise ValueError("Ry, Fy and Ag must be positive for Ca.")
    return max(0.0, pr) / (alpha_s(method) * ry * fy * ag)


def _root(e: float, ry: float, fy: float) -> float:
    if e <= 0.0 or ry <= 0.0 or fy <= 0.0:
        raise ValueError("E, Ry and Fy must be positive.")
    return math.sqrt(e / (ry * fy))


def limit(
    case: int,
    e: float,
    ry: float,
    fy: float,
    *,
    ductility: Ductility = "high",
    ca_value: float = 0.0,
) -> float:
    """The limiting width-to-thickness ratio of ``case`` of Tables D1.1a/b.

    ``case`` is 1 to 18 as numbered in AISC 341-22; ``ca_value`` enters only
    cases 11 and 13. H-pile cases 9 and 10 have no highly ductile limit and
    raise :class:`ValueError` for one.
    """
    if ductility not in ("moderate", "high"):
        raise ValueError(f"Unknown ductility {ductility!r}.")
    root = _root(e, ry, fy)
    if case in _SIMPLE:
        high, moderate = _SIMPLE[case]
        return (high if ductility == "high" else moderate) * root
    if case in _MODERATE_ONLY:
        if ductility == "high":
            raise ValueError(f"Case {case} has no highly ductile limit.")
        return _MODERATE_ONLY[case] * root
    ratio = max(0.0, ca_value)
    if case == 11:
        # AISC 341-22 Table D1.1b: the new deep-column expression.
        coefficient = 2.5 if ductility == "high" else 5.4
        return coefficient * math.pow(1.0 - min(1.0, ratio), 2.3) * root
    if case == 13:
        high = ratio <= _CASE_13_BREAK
        if ductility == "high":
            value = 2.45 * (1.0 - 1.04 * ratio) if high else 2.26 * (1.0 - 0.38 * ratio)
        else:
            value = 3.76 * (1.0 - 3.05 * ratio) if high else 2.61 * (1.0 - 0.49 * ratio)
        return max(value, _CASE_13_FLOOR) * root
    raise ValueError(f"Unknown AISC 341 case {case}: use 1 to 18.")


def admissible(
    ratio: float,
    case: int,
    e: float,
    ry: float,
    fy: float,
    *,
    ductility: Ductility = "high",
    ca_value: float = 0.0,
) -> bool:
    """Whether an element ratio ``b/t`` (or ``h/tw``, ``D/t``) passes the case."""
    return ratio <= limit(case, e, ry, fy, ductility=ductility, ca_value=ca_value) + 1e-9


#: Systems the layer knows, and the ductility their members are designed for.
SYSTEM_DUCTILITY: dict[str, Ductility] = {
    "SMF": "high",
    "IMF": "moderate",
    "SCBF": "high",
    "OCBF": "moderate",
}
SEISMIC_SYSTEMS = ("none", "SMF", "IMF", "SCBF", "OCBF")


def system_ductility(system: str) -> Ductility | None:
    """The ductility class of a seismic system, or None for ``"none"``."""
    if system == "none":
        return None
    try:
        return SYSTEM_DUCTILITY[system]
    except KeyError:
        raise ValueError(f"Unknown seismic system {system!r}.") from None


@dataclass(frozen=True)
class ElementLimit:
    """One compression element, its ratio and the D1.1 case it is checked with."""

    element: str
    case: int
    ratio: float
    limit: float

    @property
    def utilization(self) -> float:
        """``ratio / limit``; the check reports it like any other ratio."""
        return self.ratio / self.limit if self.limit > 0.0 else math.inf


def member_limits(
    shape: object,
    *,
    role: Role,
    system: str,
    e: float,
    ry: float,
    fy: float,
    ca_value: float = 0.0,
) -> list[ElementLimit]:
    """The Table D1.1 checks of a shape for one member role and system.

    Braces use Table D1.1a; beams and columns use Table D1.1b. Webs of I-shapes
    and channels follow case 11 in moment frames (SMF, IMF) and case 13 in
    braced frames (SCBF, OCBF). ``ca_value`` only enters those two cases.
    """
    ductility = system_ductility(system)
    if ductility is None:
        return []
    if role not in ("brace", "beam", "column"):
        raise ValueError(f"Unknown member role {role!r}.")
    out: list[ElementLimit] = []

    def add(element: str, case: int, ratio: float) -> None:
        out.append(
            ElementLimit(
                element,
                case,
                ratio,
                limit(case, e, ry, fy, ductility=ductility, ca_value=ca_value),
            )
        )

    if isinstance(shape, IShape | Channel):
        add("Flange", 7, shape.flange_ratio)
        if role == "brace":
            add("Web", 4, shape.web_ratio)
        else:
            add("Web", 11 if system in ("SMF", "IMF") else 13, shape.web_ratio)
    elif isinstance(shape, Tee):
        add("Flange", 7, shape.flange_ratio)
        add("Stem", 7, shape.stem_ratio)
    elif isinstance(shape, EqualLegAngle):
        add("Leg", 7, shape.leg_ratio)
    elif isinstance(shape, RectHSS):
        case = 2 if role == "brace" else (13 if system in ("SCBF", "OCBF") else 12)
        add("Wall B", case, shape.b_flat / shape.t)
        add("Wall H", case, shape.h_flat / shape.t)
    elif isinstance(shape, RoundHSS):
        add("Wall", 3 if role == "brace" else 16, shape.D / shape.t)
    return out


# ─────────────────────── SMF E3.4a: strong-column/weak-beam ───────────────────────
def cpr(fy: float, fu: float | None = None) -> float:
    """AISC 358: ``Cpr = (Fy + Fu)/(2 Fy) <= 1.2``; 1.2 without ``Fu``."""
    if fu is None or fy <= 0.0:
        return 1.2
    return min(1.2, (fy + fu) / (2.0 * fy))


def mpr(ry: float, fy: float, zb: float, *, fu: float | None = None) -> float:
    """Maximum probable moment at the plastic hinge, ``Cpr Ry Fy Zb``."""
    if ry <= 0.0 or fy <= 0.0 or zb <= 0.0:
        raise ValueError("Ry, Fy and Zb must be positive for Mpr.")
    return cpr(fy, fu) * ry * fy * zb


def mpc_star(
    zc: float,
    fyc: float,
    pr: float,
    ag: float,
    *,
    method: Method = "LRFD",
) -> float:
    """E3-2: a column's nominal flexural strength reduced for axial force.

    ``M*pc = Zc (Fyc - alpha_s Pr / Ag)``; a column whose axial force exceeds
    its yield force contributes no flexural strength (the expression is
    clamped at zero).
    """
    if ag <= 0.0:
        raise ValueError("Ag must be positive for M*pc.")
    return zc * max(0.0, fyc - alpha_s(method) * max(0.0, pr) / ag)


def mbe_star(mpr_value: float, mv: float = 0.0, *, method: Method = "LRFD") -> float:
    """E3-3: ``M*be = Mpr + alpha_s Mv`` for one beam at the joint."""
    return mpr_value + alpha_s(method) * max(0.0, mv)


def scwb_ratio(mpc_sum: float, mbe_sum: float) -> float:
    """E3-1: ``sum M*pc / sum M*be``; infinite when the beams contribute none."""
    if mbe_sum <= 0.0:
        return math.inf
    return mpc_sum / mbe_sum


def scwb_exempt(
    prc: float,
    pyc: float,
    *,
    method: Method = "LRFD",
    one_story_or_top: bool = False,
    story_shear_share: float = 1.0,
    line_shear_share: float = 1.0,
) -> bool:
    """The E3.4a exception: light columns, in the cases the provisions allow.

    ``alpha_s Prc < 0.3 Pyc`` and either the column is in a one-story building
    or the top story, or its available shear is a small share of the story and
    of its column line (20% and 33%).
    """
    light = alpha_s(method) * max(0.0, prc) < 0.3 * pyc
    small_share = story_shear_share < 0.20 and line_shear_share < 0.33
    return light and (one_story_or_top or small_share)
