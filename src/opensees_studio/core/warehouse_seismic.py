"""The static earthquake on a generated warehouse, direction by direction.

The reduction factor of the code (Q of RNC-07, Ro of NSCM, R of ASCE 7, q of
EN 1998-1) is that of the lateral system of each direction, so each direction
has its own seismic coefficient ``c = V / W``. It is either the plateau of the
design spectrum (no period, on the safe side) or the design spectrum at the
period of that direction: typed, or the code's empirical period of the
direction's system at the mean roof height (RNC-07 has none, so its period is
always typed). :func:`seismic_loads` shares ``c W`` between the joints by
weight and height. Split out of :mod:`opensees_studio.core.warehouse`, which
re-exports it.

No Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from opensees_studio.core.units import UnitSystem
    from opensees_studio.core.warehouse import Warehouse, WarehouseSpec

#: The static methods the wizard offers.
SEISMIC_METHODS: dict[str, str] = {
    "rnc07": "RNC-07 Art. 32",
    "nscm": "NSCM Managua 8.2.1",
    "asce7": "ASCE 7-16 12.8",
    "en1998": "EN 1998-1 4.3.3.2",
}
#: Where the spectral acceleration of each direction is read.
PERIOD_METHODS: dict[str, str] = {
    "plateau": "Plateau of the spectrum (no period)",
    "period": "Spectrum at the period of each direction",
}

#: The directions an earthquake case can act in.
SEISMIC_DIRECTIONS: tuple[str, ...] = ("X", "Y")
#: Design codes whose combinations take each earthquake direction with 30 % of
#: the other: RNC-07 Art. 32 f (Efectos bidireccionales), NSCM and EN 1998-1
#: 4.3.3.5.1 (3).
ORTHOGONAL_RULE_CODES: tuple[str, ...] = ("rnc07", "nscm", "en1990")

#: EN 1998-1 Table 3.2: soil factor S of the Type 1 spectrum per ground type.
EN1998_SOIL_FACTORS: dict[str, float] = {"A": 1.0, "B": 1.2, "C": 1.15, "D": 1.35, "E": 1.4}
#: EN 1998-1 Table 3.2: corner periods TB, TC, TD of the Type 1 spectrum, s.
EN1998_CORNER_PERIODS: dict[str, tuple[float, float, float]] = {
    "A": (0.15, 0.4, 2.0),
    "B": (0.15, 0.5, 2.0),
    "C": (0.20, 0.6, 2.0),
    "D": (0.20, 0.8, 2.0),
    "E": (0.15, 0.5, 2.0),
}
#: EN 1998-1 3.2.2.5 (4), Note: recommended lower bound factor β.
EN1998_BETA = 0.2
#: EN 1998-1 4.3.3.2.2 (3), Expression (4.6): Ct of T1 = Ct H^(3/4) (H in m),
#: per key of ``ASCE_PERIOD_SYSTEMS``.
EN1998_CT: dict[str, float] = {
    "steel_mrf": 0.085,
    "concrete_mrf": 0.075,
    "braced_ebf": 0.075,
    "other": 0.05,
}
#: EN 1998-1 4.2.5 (5), Note: recommended importance factor per importance class.
EN1998_IMPORTANCE: dict[str, float] = {"I": 0.8, "II": 1.0, "III": 1.2, "IV": 1.4}


def _refuse(message: str) -> NoReturn:
    from opensees_studio.core.warehouse import WarehouseError

    raise WarehouseError(message)


def _period_systems() -> Mapping[str, tuple[str, float, float]]:
    from opensees_studio.core.seismic_codes.asce7_16 import ASCE_PERIOD_SYSTEMS

    return ASCE_PERIOD_SYSTEMS


@dataclass(frozen=True)
class WarehouseSeismic:
    """The earthquake on a warehouse by the static method of a code."""

    method: str = "rnc07"
    """Key of :data:`SEISMIC_METHODS`."""
    a0: float = 0.3
    """RNC-07 and NSCM: peak ground acceleration, in g (RNC-07 zone C; NSCM Tabla 14.2).
    EN 1998-1: the reference acceleration agR on type A ground, in g."""
    soil: str = "II"
    """RNC-07 soil type I to III, NSCM site class A to D or EN 1998-1 ground type A to E."""
    importance_class: str = ""
    """RNC-07 group A to C, NSCM risk category or EN 1998-1 importance class I to IV;
    "" = Group B / category II / class II."""
    reduction: float = 2.0
    """Q of RNC-07, Ro of NSCM, R of ASCE 7 or the behaviour factor q of EN 1998-1,
    of the lateral system along X."""
    regularity: str = "regular"
    """RNC-07 Art. 23 regularity, for Q'."""
    sds: float = 1.0
    """ASCE 7: design spectral acceleration at short periods, g."""
    importance: float = 1.0
    """ASCE 7: importance factor Ie."""
    roof_live: float = 0.0
    """Roof live load that counts as seismic weight, per area of horizontal
    projection, in project units (the CVR of RNC-07)."""
    directions: tuple[str, ...] = SEISMIC_DIRECTIONS
    reduction_y: float = 0.0
    """The reduction factor of the lateral system along Y; 0 = the same as along X."""
    period_method: str = "plateau"
    """Key of :data:`PERIOD_METHODS`."""
    period_x: float = 0.0
    """The period along X, s, for ``period_method="period"``; 0 takes the
    code's empirical period of ``system_x`` (RNC-07 has none: type it)."""
    period_y: float = 0.0
    system_x: str = "steel_mrf"
    """Key of ``ASCE_PERIOD_SYSTEMS``: the lateral system along X, for the
    empirical period. Across the frames it is a moment frame."""
    system_y: str = "other"
    """The same along Y; along the building it is braced."""
    sd1: float = 0.6
    """ASCE 7: design spectral acceleration at 1 s, g (with a period only)."""

    def __post_init__(self) -> None:
        if self.method not in SEISMIC_METHODS:
            _refuse(f"Unknown seismic method {self.method!r}.")
        if self.reduction <= 0.0:
            _refuse("The seismic reduction factor must be positive.")
        if self.reduction_y < 0.0:
            _refuse("The seismic reduction factor along Y cannot be negative (0 = as along X).")
        if self.period_method not in PERIOD_METHODS:
            _refuse(f"Unknown period method {self.period_method!r}.")
        if self.period_x < 0.0 or self.period_y < 0.0:
            _refuse("A period cannot be negative.")
        for system in (self.system_x, self.system_y):
            if system not in _period_systems():
                _refuse(f"Unknown structural system {system!r}.")
        if self.sd1 < 0.0:
            _refuse("SD1 cannot be negative.")
        if self.roof_live < 0.0:
            _refuse("Loads are entered as positive, downward values.")
        if not self.directions:
            _refuse("Choose at least one earthquake direction.")
        for direction in self.directions:
            if direction not in SEISMIC_DIRECTIONS:
                _refuse(f"Unknown earthquake direction {direction!r}.")

    def reduction_of(self, direction: str) -> float:
        """The reduction factor of the lateral system along ``direction``."""
        if direction == "Y" and self.reduction_y > 0.0:
            return self.reduction_y
        return self.reduction

    def period_of(self, direction: str) -> float:
        """The period typed for ``direction``, s; 0 = none."""
        return self.period_y if direction == "Y" else self.period_x

    def system_of(self, direction: str) -> str:
        """The lateral system along ``direction``."""
        return self.system_y if direction == "Y" else self.system_x


def empirical_period(seismic: WarehouseSeismic, direction: str, height_m: float) -> float:
    """The code's empirical period along ``direction`` of a building ``height_m`` tall.

    ASCE 7 and NSCM: Eq. 12.8-7, ``Ta = Ct hn^x``. EN 1998-1: Expression (4.6),
    ``T1 = Ct H^(3/4)``.

    Raises:
        WarehouseError: for RNC-07, which has no empirical period (Art. 32 b),
            or without a height.
    """
    from opensees_studio.core.seismic_codes.asce7_16 import asce7_period

    if seismic.method == "rnc07":
        _refuse(
            f"RNC-07 gives no empirical period: type the period along {direction} "
            "(Art. 32 b, Ec. 12), or use the plateau of the spectrum."
        )
    if height_m <= 0.0:
        _refuse("The building has no height above its base.")
    system = seismic.system_of(direction)
    if seismic.method == "en1998":
        return float(EN1998_CT[system] * height_m**0.75)
    return asce7_period(system, height_m)


def seismic_height(spec: WarehouseSpec, units: UnitSystem) -> float:
    """The mean height of the roof above the base, in metres: the hn of the empirical period."""
    from opensees_studio.core.units import UnitSystem, length_scale

    mean = 0.5 * (spec.eave_height + spec.ridge_height)
    return mean * length_scale(units, UnitSystem.SI_M_N)


def _asce_cu(sd1: float) -> float:
    """ASCE 7-16 Table 12.8-1: Cu against SD1 (the same rows as NSCM Tabla 8.2.1)."""
    import numpy as np

    from opensees_studio.core.nscm import NSCM_CU

    return float(np.interp(sd1, [r[0] for r in NSCM_CU], [r[1] for r in NSCM_CU]))


def en1998_design_spectrum(
    period: float, ag: float, soil_factor: float, q: float, corners: tuple[float, float, float]
) -> tuple[float, str]:
    """Sd(T) / g of EN 1998-1 Expressions (3.13) to (3.16), and the branch."""
    tb, tc, td = corners
    plateau = ag * soil_factor * 2.5 / q
    floor = EN1998_BETA * ag
    if period <= tb:
        value = ag * soil_factor * (2.0 / 3.0 + period / tb * (2.5 / q - 2.0 / 3.0))
        return value, "(3.13)"
    if period <= tc:
        return plateau, "(3.14)"
    if period <= td:
        value, why = plateau * tc / period, "(3.15)"
    else:
        value, why = plateau * tc * td / period**2, "(3.16)"
    if value < floor:
        return floor, f"{why} lower bound β ag"
    return value, why


def seismic_coefficient(
    seismic: WarehouseSeismic, direction: str = "X", height_m: float = 0.0
) -> tuple[float, str]:
    """``c = V / W`` of the static method along ``direction``, and the clause it comes from.

    ``height_m`` is the mean height of the roof above the base in metres, for
    the empirical period; only ``period_method="period"`` uses it.

    Raises:
        WarehouseError: when the code refuses the values (a soil that needs a
            site study, an Ro below 1, a period RNC-07 cannot estimate, ...).
    """
    from opensees_studio.core import nscm
    from opensees_studio.core.equivalent_lateral import (
        ElfError,
        ElfParameters,
        asce7_cs,
        rnc07_coefficient,
    )
    from opensees_studio.core.seismic_codes.nscm2021 import nscm_cs

    r = seismic.reduction_of(direction)
    with_period = seismic.period_method == "period"
    period = 0.0
    approximate = 0.0
    source = ""
    if with_period:
        given = seismic.period_of(direction)
        if given > 0.0:
            period, source = given, f"T = {given:.4g} s"
        else:
            approximate = empirical_period(seismic, direction, height_m)
            period = approximate
            label = _period_systems()[seismic.system_of(direction)][0]
            symbol = "T1" if seismic.method == "en1998" else "Ta"
            source = f"{symbol} = {approximate:.3g} s, {label.lower()}"
        if seismic.method in ("nscm", "asce7") and approximate == 0.0 and height_m > 0.0:
            approximate = empirical_period(seismic, direction, height_m)
    try:
        if seismic.method == "rnc07":
            found = rnc07_coefficient(
                ElfParameters(
                    code="rnc07",
                    period=period,
                    sds=0.0,
                    sd1=0.0,
                    r=r,
                    a0=seismic.a0,
                    soil=seismic.soil,
                    importance_class=seismic.importance_class,
                    regularity=seismic.regularity,
                    use_period=with_period,
                )
            )
            return found.c, _with(f"RNC-07 {found.why}", source)
        if seismic.method == "nscm":
            if not with_period:
                site = nscm.NscmSite(
                    a0=seismic.a0,
                    site_class=seismic.soil,
                    risk_category=seismic.importance_class or "II",
                    r0=r,
                )
                _tb, tc, _td = site.corner_periods()
                cs, why = site.seismic_coefficient(tc)
                return cs, f"NSCM {why}"
            cs, why, used = nscm_cs(
                ElfParameters(
                    code="nscm2021",
                    period=period,
                    sds=0.0,
                    sd1=0.0,
                    r=r,
                    a0=seismic.a0,
                    soil=seismic.soil,
                    importance_class=seismic.importance_class,
                    approximate_period=approximate,
                )
            )
            if used < period:
                source += f", capped at Cu Ta = {used:.3g} s"
            return cs, _with(f"NSCM {why}", source)
        if seismic.method == "en1998":
            # λ = 1 in (4.5): a building of one storey (4.3.3.2.2), ag = γI agR.
            if seismic.soil not in EN1998_SOIL_FACTORS:
                _refuse(
                    f"EN 1998-1 has ground types A to E, not {seismic.soil!r}: S1 and S2 "
                    "need a special study."
                )
            gamma = EN1998_IMPORTANCE[seismic.importance_class or "II"]
            soil_factor = EN1998_SOIL_FACTORS[seismic.soil]
            ag = gamma * seismic.a0
            if not with_period:
                return 2.5 * ag * soil_factor / r, (
                    f"EN 1998-1 (3.14): Sd = 2.5 ag S / q, ag = {ag:.4g} g, "
                    f"S = {soil_factor:g}, q = {r:g}"
                )
            value, why = en1998_design_spectrum(
                period, ag, soil_factor, r, EN1998_CORNER_PERIODS[seismic.soil]
            )
            return value, _with(
                f"EN 1998-1 {why}: Sd(T), ag = {ag:.4g} g, S = {soil_factor:g}, q = {r:g}",
                source,
            )
        if seismic.sds <= 0.0:
            _refuse("SDS must be positive.")
        if with_period:
            if seismic.sd1 <= 0.0:
                _refuse("SD1 must be positive to read the spectrum at a period.")
            if approximate > 0.0:
                cap = _asce_cu(seismic.sd1) * approximate
                if period > cap:
                    period = cap
                    source += f", capped at Cu Ta = {cap:.3g} s"
        cs, why = asce7_cs(
            ElfParameters(
                code="asce7_16",
                period=period,
                sds=seismic.sds,
                sd1=seismic.sd1 if with_period else 0.0,
                r=r,
                importance=seismic.importance,
            )
        )
        return cs, _with(f"ASCE 7-16 {why}", source)
    except (ElfError, nscm.NscmError, KeyError) as exc:
        _refuse(str(exc))


def _with(clause: str, source: str) -> str:
    return f"{clause}; {source}" if source else clause


def nscm_a0_fas(seismic: WarehouseSeismic) -> float:
    """``a0 Fas`` of the NSCM site (Tabla 6.4.1), which sets the vertical component Ev.

    Raises:
        WarehouseError: when the site class needs a site response study.
    """
    from opensees_studio.core import nscm

    try:
        site = nscm.NscmSite(
            a0=seismic.a0,
            site_class=seismic.soil,
            risk_category=seismic.importance_class or "II",
            r0=seismic.reduction,
        )
        return float(site.a0 * site.fas)
    except (nscm.NscmError, KeyError, ValueError) as exc:
        _refuse(str(exc))


def seismic_loads(
    warehouse: Warehouse, weights: Mapping[int, float], coefficient: float, direction: str
) -> list[Any]:
    """The static earthquake forces along ``direction`` ("X" or "Y"), one per node.

    ``weights`` is the seismic weight lumped on each node of the warehouse. The
    base shear ``coefficient × ΣW`` is shared in proportion to weight times
    height above the base, ``Fi = c Wi hi ΣW / ΣWi hi`` (RNC-07 Art. 32, ASCE 7
    Eq. 12.8-12 with k = 1), so the roof takes almost all of it and a joint
    half way up a wall its smaller part.
    """
    from opensees_studio.core.loads import NodalLoad

    axis = SEISMIC_DIRECTIONS.index(direction)
    base = warehouse.spec.origin[2]
    heights = {n.id: n.coords[2] - base for n in warehouse.nodes}
    total = sum(weights.get(n, 0.0) for n in heights)
    moment = sum(weights.get(n, 0.0) * h for n, h in heights.items())
    if total <= 0.0 or moment <= 0.0:
        return []
    loads: list[Any] = []
    for node_id in sorted(heights):
        force = coefficient * weights.get(node_id, 0.0) * heights[node_id] * total / moment
        if force == 0.0:
            continue
        fx, fy = (force, 0.0) if axis == 0 else (0.0, force)
        loads.append(NodalLoad(node_id=node_id, forces=(fx, fy, 0.0, 0.0, 0.0, 0.0)))
    return loads


__all__ = [
    "EN1998_BETA",
    "EN1998_CORNER_PERIODS",
    "EN1998_CT",
    "EN1998_IMPORTANCE",
    "EN1998_SOIL_FACTORS",
    "ORTHOGONAL_RULE_CODES",
    "PERIOD_METHODS",
    "SEISMIC_DIRECTIONS",
    "SEISMIC_METHODS",
    "WarehouseSeismic",
    "empirical_period",
    "en1998_design_spectrum",
    "nscm_a0_fas",
    "seismic_coefficient",
    "seismic_height",
    "seismic_loads",
]
