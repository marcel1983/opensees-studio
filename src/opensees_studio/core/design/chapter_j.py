"""AISC 360 Chapter J: welds, bolts and affected connection elements.

The functions return the same :class:`Strength` record as the member engine,
so a connection check can be reported with its nominal strength, available
strength, equation and calculation steps.

Implemented limit states:

* J2.4 fillet weld in shear, ``Rn = 0.60 Fexx (0.707 w) l``;
* J3.1 bolt shear/tension, ``Rn = Fn Ab``;
* J3.6 bolt bearing and tearout, ``2.4 d t Fu`` / ``1.2 lc t Fu`` (or the
  3.0 and 1.5 variants when deformation is not a design consideration);
* J3.4 slip-critical bolts, ``Rn = mu Du hf Tb ns``;
* J4.3 plate shear yielding, ``0.60 Fy Agv``;
* J4.4 plate shear rupture, ``0.60 Fu Anv``;
* J4.5 block shear, the lesser of ``0.60 Fu Anv + Ubs Fu Ant`` and
  ``0.60 Fy Agv + Ubs Fu Ant``.

The caller supplies consistent units; no Qt, no OpenSees.
"""

from __future__ import annotations

import math
from typing import Literal

from opensees_studio.core.design.aisc360 import Method, Strength
from opensees_studio.core.design.calc import CalcStep

#: AISC 360 J2.4: fillet-weld throat and factors.
FILLET_THROAT = math.sqrt(0.5)
FILLET_PHI = 0.75
FILLET_OMEGA = 2.00
#: AISC 360 J3.1/J3.6: bolt factors.
BOLT_PHI = 0.75
BOLT_OMEGA = 2.00
#: AISC 360 J4.3/J4.4: plate shear factors.
SHEAR_YIELD_PHI = 1.00
SHEAR_YIELD_OMEGA = 1.50
SHEAR_RUPTURE_PHI = 0.75
SHEAR_RUPTURE_OMEGA = 2.00
#: AISC 360 J4.5: block-shear factor.
BLOCK_SHEAR_PHI = 0.75
BLOCK_SHEAR_OMEGA = 2.00
#: AISC 360 J3.4: slip-critical factors by hole type.
SLIP_FACTORS: dict[str, tuple[float, float]] = {
    "standard": (1.00, 1.50),
    "oversized": (0.85, 1.76),
    "long_slotted": (0.70, 2.14),
}
#: AISC 360 J3.4: the hole factor and the filler factor.
SLIP_DU = 1.13
SLIP_HF = 1.0

HoleType = Literal["standard", "oversized", "long_slotted"]


def _available(nominal: float, phi: float, omega: float, method: Method) -> float:
    return nominal * (phi if method == "LRFD" else 1.0 / omega)


def _strength(
    nominal: float,
    available: float,
    equation: str,
    steps: tuple[CalcStep, ...],
) -> Strength:
    return Strength(nominal, available, equation, (), steps)


def fillet_weld_strength(
    *,
    fexx: float,
    leg: float,
    length: float,
    both_sides: bool = True,
    method: Method = "LRFD",
) -> Strength:
    """J2.4: fillet-weld shear strength, ``Rn = 0.60 Fexx (0.707 w) l``."""
    if min(fexx, leg, length) <= 0.0:
        raise ValueError("Fexx, the weld leg and the length must be positive.")
    sides = 2.0 if both_sides else 1.0
    throat = FILLET_THROAT * leg
    area = throat * length * sides
    nominal = 0.60 * fexx * area
    available = _available(nominal, FILLET_PHI, FILLET_OMEGA, method)
    return _strength(
        nominal,
        available,
        "J2-4 fillet weld shear",
        (
            CalcStep("Effective throat", "0.707 w", f"0.707 x {leg:g}", throat),
            CalcStep(
                "Effective area",
                "Awe = throat x l x sides",
                f"{throat:.6g} x {length:g} x {sides:g}",
                area,
            ),
            CalcStep("Nominal strength", "0.60 Fexx Awe", f"{nominal:.6g}", nominal),
        ),
    )


def bolt_shear_strength(
    *,
    fnv: float,
    diameter: float,
    count: int,
    method: Method = "LRFD",
) -> Strength:
    """J3.1: bolt shear, ``Rn = n Fnv Ab``."""
    if min(fnv, diameter) <= 0.0 or count < 1:
        raise ValueError("Fnv and the bolt diameter must be positive, and n >= 1.")
    area = math.pi * diameter**2 / 4.0
    nominal = count * fnv * area
    available = _available(nominal, BOLT_PHI, BOLT_OMEGA, method)
    return _strength(
        nominal,
        available,
        "J3-1 bolt shear",
        (
            CalcStep("Bolt area", "Ab = pi d^2 / 4", f"pi x {diameter:g}^2 / 4", area),
            CalcStep(
                "Nominal strength",
                "n Fnv Ab",
                f"{count} x {fnv:g} x {area:.6g}",
                nominal,
            ),
        ),
    )


def bolt_tension_strength(
    *,
    fnt: float,
    diameter: float,
    count: int,
    method: Method = "LRFD",
) -> Strength:
    """J3.1: bolt tension, ``Rn = n Fnt Ab``."""
    if min(fnt, diameter) <= 0.0 or count < 1:
        raise ValueError("Fnt and the bolt diameter must be positive, and n >= 1.")
    area = math.pi * diameter**2 / 4.0
    nominal = count * fnt * area
    available = _available(nominal, BOLT_PHI, BOLT_OMEGA, method)
    return _strength(
        nominal,
        available,
        "J3-1 bolt tension",
        (
            CalcStep("Bolt area", "Ab = pi d^2 / 4", f"pi x {diameter:g}^2 / 4", area),
            CalcStep(
                "Nominal strength",
                "n Fnt Ab",
                f"{count} x {fnt:g} x {area:.6g}",
                nominal,
            ),
        ),
    )


def bolt_bearing_strength(
    *,
    fu: float,
    thickness: float,
    diameter: float,
    count: int,
    edge_distance: float,
    hole_diameter: float | None = None,
    deformation: bool = True,
    method: Method = "LRFD",
) -> Strength:
    """J3.6: bolt bearing and tearout at a standard hole.

    ``edge_distance`` is measured from the bolt center to the material edge;
    the clear distance ``lc`` subtracts half the hole. ``hole_diameter``
    defaults to ``diameter`` plus 1/16 in. in the same units (the caller can
    pass the exact value, e.g. 2 mm in SI).
    """
    if min(fu, thickness, diameter, edge_distance) <= 0.0 or count < 1:
        raise ValueError("Fu, t, d, the edge distance must be positive, and n >= 1.")
    hole = diameter + 0.0625 if hole_diameter is None else hole_diameter
    clear = max(0.0, edge_distance - hole / 2.0)
    bearing_factor = 2.4 if deformation else 3.0
    tearout_factor = 1.2 if deformation else 1.5
    bearing = bearing_factor * diameter * thickness * fu
    tearout = tearout_factor * clear * thickness * fu
    nominal = count * min(bearing, tearout)
    available = _available(nominal, BOLT_PHI, BOLT_OMEGA, method)
    return _strength(
        nominal,
        available,
        "J3-6a/c bearing and tearout",
        (
            CalcStep(
                "Bearing",
                f"{bearing_factor:g} d t Fu",
                f"{bearing_factor:g} x {diameter:g} x {thickness:g} x {fu:g}",
                bearing,
            ),
            CalcStep(
                "Tearout",
                f"{tearout_factor:g} lc t Fu",
                f"{tearout_factor:g} x {clear:.6g} x {thickness:g} x {fu:g}",
                tearout,
            ),
            CalcStep(
                "Nominal strength",
                "n min(bearing, tearout)",
                f"{count} x {min(bearing, tearout):.6g}",
                nominal,
            ),
        ),
    )


def slip_critical_strength(
    *,
    mu: float,
    tb: float,
    ns: int,
    count: int,
    hole_type: HoleType = "standard",
    method: Method = "LRFD",
) -> Strength:
    """J3.4: slip-critical bolt strength, ``Rn = mu Du hf Tb ns`` per bolt."""
    if min(mu, tb) <= 0.0 or ns < 1 or count < 1:
        raise ValueError("mu, Tb and ns must be positive, and n >= 1.")
    if hole_type not in SLIP_FACTORS:
        raise ValueError(f"Unknown hole type {hole_type!r}.")
    phi, omega = SLIP_FACTORS[hole_type]
    nominal = count * mu * SLIP_DU * SLIP_HF * tb * ns
    available = _available(nominal, phi, omega, method)
    return _strength(
        nominal,
        available,
        "J3-4 slip-critical",
        (
            CalcStep(
                "Nominal slip resistance",
                "n mu Du hf Tb ns",
                f"{count} x {mu:g} x {SLIP_DU:g} x {SLIP_HF:g} x {tb:g} x {ns}",
                nominal,
            ),
        ),
    )


def plate_shear_yielding(*, fy: float, agv: float, method: Method = "LRFD") -> Strength:
    """J4.3: plate shear yielding, ``Rn = 0.60 Fy Agv``."""
    if min(fy, agv) <= 0.0:
        raise ValueError("Fy and Agv must be positive.")
    nominal = 0.60 * fy * agv
    available = _available(nominal, SHEAR_YIELD_PHI, SHEAR_YIELD_OMEGA, method)
    return _strength(
        nominal,
        available,
        "J4-3 shear yielding",
        (
            CalcStep("Gross shear area", "Agv", f"{agv:g}", agv),
            CalcStep("Nominal strength", "0.60 Fy Agv", f"{nominal:.6g}", nominal),
        ),
    )


def plate_shear_rupture(*, fu: float, anv: float, method: Method = "LRFD") -> Strength:
    """J4.4: plate shear rupture, ``Rn = 0.60 Fu Anv``."""
    if min(fu, anv) <= 0.0:
        raise ValueError("Fu and Anv must be positive.")
    nominal = 0.60 * fu * anv
    available = _available(nominal, SHEAR_RUPTURE_PHI, SHEAR_RUPTURE_OMEGA, method)
    return _strength(
        nominal,
        available,
        "J4-4 shear rupture",
        (
            CalcStep("Net shear area", "Anv", f"{anv:g}", anv),
            CalcStep("Nominal strength", "0.60 Fu Anv", f"{nominal:.6g}", nominal),
        ),
    )


def block_shear_strength(
    *,
    fy: float,
    fu: float,
    agv: float,
    anv: float,
    ant: float,
    uniform_tension: bool = True,
    method: Method = "LRFD",
) -> Strength:
    """J4.5: block shear, the lesser of the two failure paths."""
    if min(fy, fu, agv, anv) <= 0.0 or ant < 0.0:
        raise ValueError("Fy, Fu, Agv and Anv must be positive; Ant cannot be negative.")
    ubs = 1.0 if uniform_tension else 0.5
    shear_rupture = 0.60 * fu * anv + ubs * fu * ant
    shear_yield = 0.60 * fy * agv + ubs * fu * ant
    nominal = min(shear_rupture, shear_yield)
    available = _available(nominal, BLOCK_SHEAR_PHI, BLOCK_SHEAR_OMEGA, method)
    return _strength(
        nominal,
        available,
        "J4-5 block shear",
        (
            CalcStep(
                "Shear rupture path",
                "0.60 Fu Anv + Ubs Fu Ant",
                f"0.60 x {fu:g} x {anv:g} + {ubs:g} x {fu:g} x {ant:g}",
                shear_rupture,
            ),
            CalcStep(
                "Shear yield path",
                "0.60 Fy Agv + Ubs Fu Ant",
                f"0.60 x {fy:g} x {agv:g} + {ubs:g} x {fu:g} x {ant:g}",
                shear_yield,
            ),
            CalcStep(
                "Nominal strength",
                "min(rupture, yield)",
                f"{nominal:.6g}",
                nominal,
            ),
        ),
    )
