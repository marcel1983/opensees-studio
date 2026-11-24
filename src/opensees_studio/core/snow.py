"""What settles on a roof: snow and volcanic ash, as a load on its horizontal projection.

A :class:`SnowCase` is one arrangement of the load across the building: a
pressure per area of **plan** against the position ``x`` across the roof,
piecewise linear, the same along the whole length. Positions are in metres and
pressures in the unit the ground load was given in (the formulas are linear in
it, except the drift of ASCE 7, which wants kN/m²: see
:func:`asce7_snow_cases`).

* **Volcanic ash** — RNC-07 Art. 14 and NSCM 7.3: a uniform load, 20 kg/m² of
  wet ash when there is no local record. Both ask for the build-up in valleys
  to be estimated; that is left to the engineer.
* **ASCE 7-16 chapter 7** — ``pf = 0.7 Ce Ct Is pg`` (Eq. 7.3-1), the slope
  factor ``Cs`` of Fig. 7.4-1, the minimum of 7.3.4 on a low slope, the
  unbalanced load of a gable roof (7.6.1) and of a roof of several gables
  (7.6.3).
* **EN 1991-1-3** — ``s = mu Ce Ct sk`` (5.1) with the shape coefficients of
  Table 5.2: the three arrangements of a duopitch roof (5.3.3) and the drift in
  the valleys of a multi-span roof (5.3.4).

Pure functions, no project: :mod:`opensees_studio.core.warehouse` puts a case
on the purlins.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

from opensees_studio.core.wind import ROOF_SHAPES, RoofPlane

#: 20 kg/m² of wet ash (RNC-07 Art. 14, NSCM 7.3), kN/m².
ASH_LOAD_KPA = 20 * 9.80665e-3

_PSF = 0.04788026  # one pound per square foot in kN/m²
_FT = 0.3048
_PCF = 0.1570875  # one pound per cubic foot in kN/m³

#: ASCE 7-16 Table 7.3-1: exposure factor Ce by terrain category and roof exposure.
ASCE_EXPOSURE: dict[str, dict[str, float]] = {
    "B": {"full": 0.9, "partial": 1.0, "sheltered": 1.2},
    "C": {"full": 0.9, "partial": 1.0, "sheltered": 1.1},
    "D": {"full": 0.8, "partial": 0.9, "sheltered": 1.0},
}
#: ASCE 7-16 Table 7.3-2: thermal factor Ct.
ASCE_THERMAL: dict[str, float] = {
    "heated": 1.0,
    "cold_ventilated": 1.1,
    "unheated": 1.2,
    "freezer": 1.3,
}
#: ASCE 7-16 Table 1.5-2: snow importance factor Is by risk category.
ASCE_IMPORTANCE: dict[str, float] = {"I": 0.8, "II": 1.0, "III": 1.1, "IV": 1.2}
#: EN 1991-1-3 Table 5.1: exposure coefficient Ce by topography.
EN_EXPOSURE: dict[str, float] = {"windswept": 0.8, "normal": 1.0, "sheltered": 1.2}

#: ASCE 7-16 7.6.1: a gable roof gets an unbalanced load between 1/2 on 12 and 7 on 12.
ASCE_UNBALANCED_SLOPES = (0.5 / 12.0, 7.0 / 12.0)
#: ASCE 7-16 7.6.3: several gables get one above 3/8 on 12.
ASCE_VALLEY_SLOPE = 0.375 / 12.0


class SnowError(ValueError):
    """The numbers do not describe a snow load."""


@dataclass(frozen=True)
class SnowCase:
    """One arrangement of the load: ``(x, pressure on plan)`` points, linear between them.

    Two points at the same ``x`` are a step.
    """

    name: str
    points: tuple[tuple[float, float], ...]

    def mean(self, a: float, b: float) -> float:
        """Average pressure over ``[a, b]`` (exact), 0 outside the roof."""
        if b < a:
            a, b = b, a
        if b - a < 1e-12:
            return self.at(0.5 * (a + b))
        total = 0.0
        for (x0, p0), (x1, p1) in itertools.pairwise(self.points):
            lo, hi = max(a, x0), min(b, x1)
            if x1 <= x0 or hi <= lo:
                continue
            slope = (p1 - p0) / (x1 - x0)
            total += (hi - lo) * (p0 + slope * (0.5 * (lo + hi) - x0))
        return total / (b - a)

    def at(self, x: float) -> float:
        """Pressure at ``x``; at a step, the value on the far side."""
        value = 0.0
        for (x0, p0), (x1, p1) in itertools.pairwise(self.points):
            if x1 > x0 and x0 <= x <= x1:
                value = p0 + (p1 - p0) * (x - x0) / (x1 - x0)
        return value

    @property
    def peak(self) -> float:
        return max(p for _x, p in self.points)

    def resultant(self) -> float:
        """Load per length of building: the pressure integrated across the roof."""
        x0, x1 = self.points[0][0], self.points[-1][0]
        return self.mean(x0, x1) * (x1 - x0)


def _case(name: str, pieces: Sequence[tuple[float, float, float, float]]) -> SnowCase:
    """A case of ``(x0, x1, p0, p1)`` pieces, side by side."""
    points: list[tuple[float, float]] = []
    for x0, x1, p0, p1 in pieces:
        if x1 <= x0:
            continue
        if not points or points[-1] != (x0, p0):
            points.append((x0, p0))
        points.append((x1, p1))
    return SnowCase(name, tuple(points))


def _uniform(name: str, planes: Sequence[RoofPlane], pressure: float) -> SnowCase:
    return _case(name, [(planes[0].x0, planes[-1].x1, pressure, pressure)])


def roof_planes(span: float, n_naves: int = 1, roof: str = "gable") -> tuple[RoofPlane, ...]:
    """The planes of a roof of ``n_naves`` equal naves, from x = 0."""
    if span <= 0.0 or n_naves < 1:
        raise SnowError("The roof needs a positive span and at least one nave.")
    if roof not in ROOF_SHAPES:
        raise SnowError(f"Unknown roof shape {roof!r}.")
    planes: list[RoofPlane] = []
    for nave in range(n_naves):
        x0 = nave * span
        if roof == "gable":
            planes += [
                RoofPlane(x0, x0 + span / 2.0, 1),
                RoofPlane(x0 + span / 2.0, x0 + span, -1),
            ]
        else:
            planes.append(RoofPlane(x0, x0 + span, 1 if roof == "mono" else 0))
    return tuple(planes)


def _check(planes: Sequence[RoofPlane], slope: float, ground: float) -> None:
    if not planes:
        raise SnowError("The roof has no planes.")
    if slope < 0.0:
        raise SnowError("The roof slope cannot be negative.")
    if ground < 0.0:
        raise SnowError("The ground load cannot be negative.")


def _is_gable(planes: Sequence[RoofPlane]) -> bool:
    return len(planes) >= 2 and all(
        a.rise == 1 and b.rise == -1 for a, b in zip(planes[::2], planes[1::2], strict=False)
    )


def _valleys(planes: Sequence[RoofPlane]) -> set[float]:
    """Where a falling plane meets a rising one."""
    return {a.x1 for a, b in itertools.pairwise(planes) if a.rise == -1 and b.rise == 1}


# ─────────────────────────────── volcanic ash ───────────────────────────────
def ash_cases(planes: Sequence[RoofPlane], load: float = ASH_LOAD_KPA) -> list[SnowCase]:
    """RNC-07 Art. 14 / NSCM 7.3: the ash, uniform on the plan of the roof."""
    _check(planes, 0.0, load)
    return [_uniform("ASH", planes, load)] if load > 0.0 else []


# ─────────────────────────────── ASCE 7-16 ───────────────────────────────
def asce7_flat_roof_load(
    pg: float, ce: float = 1.0, ct: float = 1.0, importance: float = 1.0
) -> float:
    """``pf = 0.7 Ce Ct Is pg`` (Eq. 7.3-1)."""
    if min(ce, ct, importance) <= 0.0:
        raise SnowError("Ce, Ct and Is must be positive.")
    return 0.7 * ce * ct * importance * pg


def asce7_minimum_load(pg_kpa: float, importance: float = 1.0) -> float:
    """7.3.4, kN/m²: ``Is pg`` up to 20 psf of ground snow, ``20 Is`` psf above."""
    return importance * min(pg_kpa, 20.0 * _PSF)


def asce7_slope_factor(angle: float, ct: float = 1.0, slippery: bool = False) -> float:
    """``Cs`` of Fig. 7.4-1 for a roof at ``angle`` degrees.

    ``slippery`` is an unobstructed slippery surface (metal, membrane) that
    lets the snow slide off the eaves. The roof stays fully loaded up to an
    angle that grows with ``Ct`` (5, 10 or 15 degrees when slippery; 30, 37.5
    or 45 otherwise) and is bare at 70.
    """
    if ct <= 1.0:
        full = 5.0 if slippery else 30.0
    elif ct < 1.2:
        full = 10.0 if slippery else 37.5
    else:
        full = 15.0 if slippery else 45.0
    if angle <= full:
        return 1.0
    return max(0.0, (70.0 - angle) / (70.0 - full))


def asce7_drift_height(fetch: float, pg_kpa: float) -> float:
    """``hd`` of Fig. 7.6-1 in metres, for an upwind fetch in metres and pg in kN/m².

    ``hd = 0.43 lu^(1/3) (pg + 10)^(1/4) - 1.5`` in feet and psf, with a fetch
    of at least 20 ft.
    """
    lu = max(fetch / _FT, 20.0)
    feet = 0.43 * math.pow(lu, 1.0 / 3.0) * math.pow(pg_kpa / _PSF + 10.0, 0.25) - 1.5
    return max(0.0, feet) * _FT


def asce7_snow_density(pg_kpa: float) -> float:
    """``gamma = 0.13 pg + 14 <= 30 pcf`` (Eq. 7.7-1), in kN/m³."""
    return min(0.13 * pg_kpa / _PSF + 14.0, 30.0) * _PCF


def asce7_snow_cases(
    planes: Sequence[RoofPlane],
    slope: float,
    pg: float,
    *,
    ce: float = 1.0,
    ct: float = 1.0,
    importance: float = 1.0,
    slippery: bool = False,
    unbalanced: bool = True,
) -> list[SnowCase]:
    """The snow of ASCE 7-16 chapter 7 on a roof, ``pg`` and the result in kN/m².

    ``SNOW`` is the balanced load ``ps = Cs pf``, not less than the minimum of
    7.3.4 where the slope is under 15 degrees. A gable roof whose slope lies
    between 1/2 on 12 and 7 on 12 also gets ``SNOW +X`` and ``SNOW -X`` (7.6.1,
    the drift on the side the wind blows to): ``0.3 ps`` to windward, ``ps`` to
    leeward and a surcharge ``hd gamma / sqrt(S)`` over ``8 hd sqrt(S) / 3``
    from the ridge. Several gables (7.6.3) take ``Cs = 1`` and one unbalanced
    case, from ``0.5 pf`` at the ridges to ``2 pf / Ce`` in the valleys; their
    outer slopes keep ``pf``.
    """
    _check(planes, slope, pg)
    if pg == 0.0:
        return []
    angle = math.degrees(math.atan(slope))
    flat = all(p.rise == 0 for p in planes) or slope == 0.0
    pf = asce7_flat_roof_load(pg, ce, ct, importance)
    valleys = _valleys(planes)
    # 7.4.4: folded plate and sawtooth roofs shed nothing, whatever their slope.
    several = not flat and len(planes) > (2 if _is_gable(planes) else 1)
    cs = 1.0 if several else asce7_slope_factor(0.0 if flat else angle, ct, slippery)
    ps = cs * pf
    balanced = ps
    if (flat or angle < 15.0) and not several:
        balanced = max(ps, asce7_minimum_load(pg, importance))
    cases = [_uniform("SNOW", planes, balanced)]
    if not unbalanced or flat or not _is_gable(planes):
        return cases
    if valleys:
        if slope <= ASCE_VALLEY_SLOPE:
            return cases
        ridge, valley = 0.5 * pf, 2.0 * pf / ce
        pieces = []
        for plane in planes:
            low = plane.x0 if plane.rise == 1 else plane.x1
            if low not in valleys:
                pieces.append((plane.x0, plane.x1, pf, pf))
            elif plane.rise == 1:
                pieces.append((plane.x0, plane.x1, valley, ridge))
            else:
                pieces.append((plane.x0, plane.x1, ridge, valley))
        return [*cases, _case("SNOW VALLEYS", pieces)]
    if not ASCE_UNBALANCED_SLOPES[0] <= slope <= ASCE_UNBALANCED_SLOPES[1]:
        return cases
    first, second = planes
    run = 1.0 / slope  # S: the run for a rise of one
    for name, windward, leeward in (("SNOW +X", first, second), ("SNOW -X", second, first)):
        fetch = windward.x1 - windward.x0
        width = leeward.x1 - leeward.x0
        hd = asce7_drift_height(fetch, pg)
        surcharge = hd * asce7_snow_density(pg) / math.sqrt(run)
        extent = min(8.0 * hd * math.sqrt(run) / 3.0, width)
        light = (windward.x0, windward.x1, 0.3 * ps, 0.3 * ps)
        if leeward is second:
            ridge = leeward.x0
            pieces = [
                light,
                (ridge, ridge + extent, ps + surcharge, ps + surcharge),
                (ridge + extent, leeward.x1, ps, ps),
            ]
        else:
            ridge = leeward.x1
            pieces = [
                (leeward.x0, ridge - extent, ps, ps),
                (ridge - extent, ridge, ps + surcharge, ps + surcharge),
                light,
            ]
        cases.append(_case(name, pieces))
    return cases


# ─────────────────────────────── EN 1991-1-3 ───────────────────────────────
def en1991_mu1(angle: float) -> float:
    """Shape coefficient μ1 of Table 5.2 (snow free to slide off the roof)."""
    if angle <= 30.0:
        return 0.8
    return max(0.0, 0.8 * (60.0 - angle) / 30.0)


def en1991_mu2(angle: float) -> float:
    """Shape coefficient μ2 of Table 5.2, for the valleys of a multi-span roof."""
    if angle <= 30.0:
        return 0.8 + 0.8 * angle / 30.0
    return 1.6 if angle < 60.0 else 0.0


def en1991_snow_cases(
    planes: Sequence[RoofPlane],
    slope: float,
    sk: float,
    *,
    ce: float = 1.0,
    ct: float = 1.0,
    drifted: bool = True,
) -> list[SnowCase]:
    """The snow of EN 1991-1-3 on a roof: ``s = mu Ce Ct sk`` (5.1), in the unit of ``sk``.

    ``SNOW`` is the undrifted arrangement, ``mu1`` everywhere. A duopitch roof
    also gets ``SNOW +X`` and ``SNOW -X`` (5.3.3, cases ii and iii): half of it
    on one slope and all of it on the other, the one named. A multi-span roof
    (5.3.4) gets ``SNOW VALLEYS``: ``mu1`` at the ridges rising to ``mu2`` in
    each valley, its outer slopes at ``mu1``.
    """
    _check(planes, slope, sk)
    if min(ce, ct) <= 0.0:
        raise SnowError("Ce and Ct must be positive.")
    if sk == 0.0:
        return []
    flat = all(p.rise == 0 for p in planes) or slope == 0.0
    angle = 0.0 if flat else math.degrees(math.atan(slope))
    base = ce * ct * sk
    s1 = en1991_mu1(angle) * base
    cases = [_uniform("SNOW", planes, s1)]
    if not drifted or flat or not _is_gable(planes) or s1 == 0.0:
        return cases
    valleys = _valleys(planes)
    if valleys:
        s2 = en1991_mu2(angle) * base
        pieces = []
        for plane in planes:
            low = plane.x0 if plane.rise == 1 else plane.x1
            if low not in valleys:
                pieces.append((plane.x0, plane.x1, s1, s1))
            elif plane.rise == 1:
                pieces.append((plane.x0, plane.x1, s2, s1))
            else:
                pieces.append((plane.x0, plane.x1, s1, s2))
        return [*cases, _case("SNOW VALLEYS", pieces)]
    first, second = planes
    return [
        *cases,
        _case(
            "SNOW +X",
            [(first.x0, first.x1, 0.5 * s1, 0.5 * s1), (second.x0, second.x1, s1, s1)],
        ),
        _case(
            "SNOW -X",
            [(first.x0, first.x1, s1, s1), (second.x0, second.x1, 0.5 * s1, 0.5 * s1)],
        ),
    ]


__all__ = [
    "ASCE_EXPOSURE",
    "ASCE_IMPORTANCE",
    "ASCE_THERMAL",
    "ASCE_UNBALANCED_SLOPES",
    "ASCE_VALLEY_SLOPE",
    "ASH_LOAD_KPA",
    "EN_EXPOSURE",
    "SnowCase",
    "SnowError",
    "asce7_drift_height",
    "asce7_flat_roof_load",
    "asce7_minimum_load",
    "asce7_slope_factor",
    "asce7_snow_cases",
    "asce7_snow_density",
    "ash_cases",
    "en1991_mu1",
    "en1991_mu2",
    "en1991_snow_cases",
    "roof_planes",
]
