"""Wind pressures on a closed rectangular building: RNC-07 and ASCE 7-16.

The building is a box with a flat, single-pitched or double-pitched roof: X
runs across the ridge (``width``), Y along it (``length``), Z is up. Everything
here is SI (metres, metres per second, N/m²) whatever the project's units; the
caller converts.

A :class:`WindCase` is one wind direction: the **net** pressure on each of the
four walls as a function of the height, and on each roof plane as a function of
one plan coordinate. A positive pressure pushes on the surface from outside (an
"empuje"), a negative one pulls it outwards (a suction); internal pressure is
already taken off (``net = external - internal``), so a load is ``-p * area``
along the outward normal.

**RNC-07, Título IV** (Reglamento Nacional de la Construcción, Nicaragua, MTI
2007), static method for Type 1 structures. Transcribed from the regulation:

* Art. 49, Ec. 28: design velocity ``VD = FTR Fα VR``.
* Art. 50, Tabla 5: regional velocity ``VR`` per wind zone (Figura 7), 50 years
  for Group B and 200 years for Group A.
* Art. 51, Ec. 29 and Tabla 6: ``Fα = 1`` up to 10 m, ``(z/10)^α`` up to the
  gradient height δ, ``(δ/10)^α`` above, with α and δ per terrain roughness
  R1 to R4.
* Art. 52, Tabla 7: ``FTR`` per topography T1 to T5 and roughness; 1 on R1.
* Art. 53, Ec. 30: ``pz = 0.0479 Cp VD²`` kg/m².
* Art. 54, Tabla 8 (closed constructions): windward wall 0.8, leeward wall
  -0.4 (constant, at the building's mid height), side walls -0.8, flat roofs
  -0.8, leeward slope -0.7, windward slope ``0.04 θ - 1.6`` kept between -0.8
  and 1.8 (θ in degrees).
* Art. 55: internal pressure when the openings of a wall exceed 30 % of it:
  0.75 with the openings to windward, -0.6 to leeward, -0.5 on the walls
  parallel to the wind, -0.3 spread over the four walls.

Tabla 8 has no row for the wind blowing along the ridge. The roof is then a
surface parallel to the flow, and it takes -0.8 here, the value of the side
walls and of a flat roof.

**ASCE/SEI 7-16**, chapter 26 and the directional procedure of chapter 27
(main wind force resisting system, enclosed and partially enclosed buildings of
all heights):

* Table 26.10-1 and 26.11-1: ``Kz = 2.01 (z/zg)^(2/α)``, z not below 15 ft
  (4.572 m), with α and zg per exposure B, C, D.
* Eq. 26.10-1 (SI): ``qz = 0.613 Kz Kzt Kd Ke V²`` N/m².
* Eq. 27.3-1: ``p = q G Cp - qi (GCpi)``, with q = qz on the windward wall and
  qh (at the mean roof height) everywhere else, qi = qh and G = 0.85.
* Figure 27.3-1: wall and roof Cp. The windward slope has two values per angle
  and the flat-roof zones a second value of -0.18; both sets are returned.
* Table 26.13-1: GCpi = ±0.18 enclosed, ±0.55 partially enclosed.

Each ASCE 7 direction gives two cases: **A** takes the most negative roof
coefficients with positive internal pressure (the largest uplift and the
largest suction on the leeward and side walls), **B** the other roof
coefficients with negative internal pressure (the largest downward load and
the largest push on the windward wall).

Not covered: components and cladding (ASCE 7 chapter 30, RNC-07 Art. 58), the
envelope procedure of chapter 28, open buildings, the minimum design wind load
of 27.1.5, torsional load cases and parapets.
"""

from __future__ import annotations

import bisect
import itertools
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

#: Newtons in one kilogram-force.
KGF = 9.80665

#: The four wind directions: the wind blows *towards* the named axis direction.
DIRECTIONS: tuple[str, ...] = ("+X", "-X", "+Y", "-Y")

#: The four walls: at the smallest and largest X, and the smallest and largest Y.
WALLS: tuple[str, ...] = ("x0", "x1", "y0", "y1")

#: Where the building has openings: none, spread over the four walls, or mainly in one wall.
OPENINGS: tuple[str, ...] = ("closed", "uniform", *WALLS)

ROOF_SHAPES: tuple[str, ...] = ("flat", "mono", "gable")


class WindError(ValueError):
    """The numbers do not describe a wind load."""


# ───────────────────────────── profiles ─────────────────────────────
_GAUSS = ((-math.sqrt(0.6), 5.0 / 9.0), (0.0, 8.0 / 9.0), (math.sqrt(0.6), 5.0 / 9.0))


@dataclass(frozen=True)
class Profile:
    """A pressure along one coordinate, smooth between its ``breaks``."""

    fn: Callable[[float], float]
    breaks: tuple[float, ...] = ()

    def at(self, s: float) -> float:
        return float(self.fn(s))

    def mean(self, a: float, b: float) -> float:
        """Average over ``[a, b]``: exact for steps, three Gauss points per smooth piece."""
        if b < a:
            a, b = b, a
        if b - a < 1e-12:
            return self.at(0.5 * (a + b))
        cuts = [a, *[c for c in sorted(self.breaks) if a < c < b], b]
        total = 0.0
        for lo, hi in itertools.pairwise(cuts):
            half, mid = 0.5 * (hi - lo), 0.5 * (hi + lo)
            total += half * sum(w * self.fn(mid + half * t) for t, w in _GAUSS)
        return total / (b - a)

    def scaled(self, factor: float, offset: float = 0.0) -> Profile:
        """``factor * self + offset``."""
        fn = self.fn
        return Profile(lambda s: factor * fn(s) + offset, self.breaks)


def constant(value: float) -> Profile:
    """The same pressure everywhere."""
    return Profile(lambda _s: value)


def steps(edges: Sequence[float], values: Sequence[float]) -> Profile:
    """``values[i]`` from ``edges[i]`` up to ``edges[i + 1]``; the end values beyond the edges."""
    if len(edges) != len(values) + 1:
        raise WindError("A stepped profile needs one more edge than values.")
    inner = tuple(edges[1:-1])
    data = tuple(values)

    def fn(s: float) -> float:
        return data[min(bisect.bisect_right(inner, s), len(data) - 1)]

    return Profile(fn, inner)


def _interpolate(x: float, points: Sequence[tuple[float, float]]) -> float:
    """Straight-line interpolation in ``points``, constant beyond the ends."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in itertools.pairwise(points):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


# ───────────────────────────── the building ─────────────────────────────
@dataclass(frozen=True)
class RoofPlane:
    """One plane of the roof, between ``x0`` and ``x1``."""

    x0: float
    x1: float
    rise: int
    """+1 when the roof climbs with X, -1 when it falls, 0 when it is flat."""


@dataclass(frozen=True)
class BuildingShape:
    """A rectangular building, in metres. A single-pitched roof climbs with X."""

    width: float
    length: float
    eave_height: float
    roof: str = "gable"
    slope: float = 0.0
    """Rise over run of the roof."""

    def __post_init__(self) -> None:
        if min(self.width, self.length, self.eave_height) <= 0.0:
            raise WindError("The building needs a positive width, length and eave height.")
        if self.roof not in ROOF_SHAPES:
            raise WindError(f"Unknown roof shape {self.roof!r}.")
        if self.slope < 0.0:
            raise WindError("The roof slope cannot be negative.")

    @property
    def is_flat(self) -> bool:
        return self.roof == "flat" or self.slope == 0.0

    @property
    def ridge_height(self) -> float:
        return self.roof_height(self.width / 2.0 if self.roof == "gable" else self.width)

    @property
    def mean_roof_height(self) -> float:
        return 0.5 * (self.eave_height + self.ridge_height)

    @property
    def roof_angle(self) -> float:
        """Angle of the roof with the horizontal, degrees."""
        return 0.0 if self.is_flat else math.degrees(math.atan(self.slope))

    def roof_height(self, x: float) -> float:
        if self.is_flat:
            return self.eave_height
        x = min(max(x, 0.0), self.width)
        run = x if self.roof == "mono" else min(x, self.width - x)
        return self.eave_height + self.slope * run

    def planes(self) -> tuple[RoofPlane, ...]:
        if self.is_flat:
            return (RoofPlane(0.0, self.width, 0),)
        if self.roof == "mono":
            return (RoofPlane(0.0, self.width, 1),)
        half = self.width / 2.0
        return (RoofPlane(0.0, half, 1), RoofPlane(half, self.width, -1))


@dataclass(frozen=True)
class RoofLoad:
    """The net pressure on one roof plane."""

    plane: RoofPlane
    axis: str
    """``"x"`` or ``"y"``: the plan coordinate ``profile`` runs along."""
    profile: Profile


@dataclass(frozen=True)
class WindCase:
    """One wind direction: net pressures on the walls and on the roof, N/m²."""

    name: str
    direction: str
    walls: dict[str, Profile]
    """Wall (:data:`WALLS`) -> net pressure against the height above the base."""
    roof: tuple[RoofLoad, ...]
    coefficients: dict[str, float]
    """The coefficients used, for the log: surface -> Cp (or GCpi, ``internal``)."""

    def roof_load_at(self, x: float) -> RoofLoad:
        """The load of the roof plane ``x`` lies on."""
        for load in self.roof:
            if load.plane.x0 - 1e-9 <= x <= load.plane.x1 + 1e-9:
                return load
        return self.roof[-1]


def _sides(direction: str) -> tuple[str, str, tuple[str, str]]:
    """``(windward wall, leeward wall, side walls)`` for a wind direction."""
    if direction not in DIRECTIONS:
        raise WindError(f"Unknown wind direction {direction!r}.")
    axis = direction[1].lower()
    other = "y" if axis == "x" else "x"
    windward, leeward = (
        (f"{axis}0", f"{axis}1") if direction[0] == "+" else (f"{axis}1", f"{axis}0")
    )
    return windward, leeward, (f"{other}0", f"{other}1")


def _distance(shape: BuildingShape, direction: str) -> Callable[[float], float]:
    """Plan coordinate along the wind -> distance from the windward edge."""
    extent = shape.width if direction[1] == "X" else shape.length
    if direction[0] == "+":
        return lambda s: s
    return lambda s: extent - s


def _faces_wind(plane: RoofPlane, direction: str) -> bool:
    """A slope climbing away from the wind is the windward slope."""
    return direction[1] == "X" and plane.rise == (1 if direction[0] == "+" else -1)


def _check(openings: str, directions: Sequence[str]) -> None:
    if openings not in OPENINGS:
        raise WindError(f"Unknown openings {openings!r}.")
    for direction in directions:
        _sides(direction)


# ───────────────────────────── RNC-07 ─────────────────────────────
#: Art. 50, Tabla 5: wind zone -> regional velocity (50 years, 200 years), m/s.
RNC07_REGIONAL_SPEEDS: dict[int, tuple[float, float]] = {
    1: (30.0, 36.0),
    2: (45.0, 60.0),
    3: (56.0, 70.0),
}

#: Art. 51, Tabla 6: terrain roughness -> (α, δ in metres).
RNC07_ROUGHNESS: dict[str, tuple[float, float]] = {
    "R1": (0.099, 245.0),
    "R2": (0.128, 315.0),
    "R3": (0.156, 390.0),
    "R4": (0.170, 455.0),
}

#: Art. 52, Tabla 7: topography -> FTR on terrain R2, R3, R4 (R1 is always 1).
RNC07_TOPOGRAPHY: dict[str, tuple[float, float, float]] = {
    "T1": (0.8, 0.7, 0.66),
    "T2": (0.9, 0.79, 0.74),
    "T3": (1.0, 0.88, 0.82),
    "T4": (1.1, 0.97, 0.9),
    "T5": (1.2, 1.06, 0.98),
}

#: Art. 54, Tabla 8: closed constructions.
RNC07_CP: dict[str, float] = {
    "windward_wall": 0.8,
    "leeward_wall": -0.4,
    "side_wall": -0.8,
    "flat_roof": -0.8,
    "leeward_roof": -0.7,
}

#: Art. 55: internal pressure, by where the openings are relative to the wind.
RNC07_INTERNAL_CP: dict[str, float] = {
    "windward": 0.75,
    "leeward": -0.6,
    "side": -0.5,
    "uniform": -0.3,
}


def rnc07_regional_speed(zone: int, group: str = "B") -> float:
    """VR of Tabla 5, m/s: 50 years for Group B, 200 years for Group A."""
    if zone not in RNC07_REGIONAL_SPEEDS:
        raise WindError(f"RNC-07 has wind zones 1, 2 and 3, not {zone!r}.")
    if group not in ("A", "B"):
        raise WindError("Tabla 5 gives the regional velocity of Groups A and B.")
    return RNC07_REGIONAL_SPEEDS[zone][1 if group == "A" else 0]


def rnc07_height_factor(z: float, roughness: str = "R2") -> float:
    """Fα of Ec. 29 at ``z`` metres above the ground."""
    if roughness not in RNC07_ROUGHNESS:
        raise WindError(f"Unknown terrain roughness {roughness!r}.")
    alpha, delta = RNC07_ROUGHNESS[roughness]
    if z <= 10.0:
        return 1.0
    return float((min(z, delta) / 10.0) ** alpha)


def rnc07_topography_factor(topography: str = "T3", roughness: str = "R2") -> float:
    """FTR of Tabla 7."""
    if topography not in RNC07_TOPOGRAPHY:
        raise WindError(f"Unknown topography {topography!r}.")
    if roughness not in RNC07_ROUGHNESS:
        raise WindError(f"Unknown terrain roughness {roughness!r}.")
    if roughness == "R1":
        return 1.0
    return RNC07_TOPOGRAPHY[topography][("R2", "R3", "R4").index(roughness)]


def rnc07_design_speed(
    regional_speed: float, z: float, roughness: str = "R2", topography: str = "T3"
) -> float:
    """VD of Ec. 28 at height ``z``, m/s."""
    return (
        rnc07_topography_factor(topography, roughness)
        * rnc07_height_factor(z, roughness)
        * regional_speed
    )


def rnc07_pressure(cp: float, design_speed: float) -> float:
    """pz of Ec. 30 in N/m² (the regulation gives kg/m²)."""
    return 0.0479 * cp * design_speed**2 * KGF


def rnc07_windward_roof_cp(angle: float) -> float:
    """Tabla 8, windward slope: ``0.04 θ - 1.6`` kept between -0.8 and 1.8."""
    return min(1.8, max(-0.8, 0.04 * angle - 1.6))


def rnc07_internal_cp(openings: str, direction: str) -> float:
    """Art. 55 for one wind direction; 0 for a closed building."""
    _check(openings, (direction,))
    if openings == "closed":
        return 0.0
    if openings == "uniform":
        return RNC07_INTERNAL_CP["uniform"]
    windward, leeward, _side = _sides(direction)
    if openings == windward:
        return RNC07_INTERNAL_CP["windward"]
    if openings == leeward:
        return RNC07_INTERNAL_CP["leeward"]
    return RNC07_INTERNAL_CP["side"]


def rnc07_wind_cases(
    shape: BuildingShape,
    *,
    regional_speed: float,
    roughness: str = "R2",
    topography: str = "T3",
    openings: str = "closed",
    directions: Sequence[str] = DIRECTIONS,
) -> list[WindCase]:
    """One case per direction, by the static method of RNC-07 Título IV."""
    if regional_speed <= 0.0:
        raise WindError("The regional velocity must be positive.")
    _check(openings, directions)
    rnc07_topography_factor(topography, roughness)  # validates both names
    kinks = (10.0, RNC07_ROUGHNESS[roughness][1])

    def unit(z: float) -> float:
        """Pressure of Cp = 1 at height ``z``."""
        return rnc07_pressure(1.0, rnc07_design_speed(regional_speed, z, roughness, topography))

    def over_height(cp: float, internal: float) -> Profile:
        def fn(z: float) -> float:
            return cp * unit(z) - internal

        return Profile(fn, kinks)

    def over_roof(cp: float, internal: float) -> Profile:
        """The pressure follows the height of the roof line, which depends on X."""

        def fn(x: float) -> float:
            return cp * unit(shape.roof_height(x)) - internal

        return Profile(fn)

    cases: list[WindCase] = []
    for direction in directions:
        windward, leeward, sides = _sides(direction)
        cpi = rnc07_internal_cp(openings, direction)
        internal = cpi * unit(shape.mean_roof_height)
        walls = {
            windward: over_height(RNC07_CP["windward_wall"], internal),
            # Tabla 8: constant over the height, at the building's mid height.
            leeward: constant(RNC07_CP["leeward_wall"] * unit(shape.ridge_height / 2.0) - internal),
            **{side: over_height(RNC07_CP["side_wall"], internal) for side in sides},
        }
        coefficients = {
            "windward_wall": RNC07_CP["windward_wall"],
            "leeward_wall": RNC07_CP["leeward_wall"],
            "side_wall": RNC07_CP["side_wall"],
            "internal": cpi,
        }
        roof: list[RoofLoad] = []
        for plane in shape.planes():
            if shape.is_flat or direction[1] == "Y":
                cp, key = RNC07_CP["flat_roof"], "roof"
            elif _faces_wind(plane, direction):
                cp, key = rnc07_windward_roof_cp(shape.roof_angle), "windward_roof"
            else:
                cp, key = RNC07_CP["leeward_roof"], "leeward_roof"
            coefficients[key] = cp
            roof.append(RoofLoad(plane, "x", over_roof(cp, internal)))
        cases.append(WindCase(f"WIND {direction}", direction, walls, tuple(roof), coefficients))
    return cases


# ───────────────────────────── ASCE 7-16 ─────────────────────────────
#: Table 26.11-1: exposure -> (α, zg in metres).
ASCE7_EXPOSURES: dict[str, tuple[float, float]] = {
    "B": (7.0, 365.76),
    "C": (9.5, 274.32),
    "D": (11.5, 213.36),
}

#: Table 26.13-1: enclosure -> GCpi (both signs act).
ASCE7_GCPI: dict[str, float] = {"enclosed": 0.18, "partially_enclosed": 0.55}

#: 26.11.1: gust-effect factor of a rigid building.
ASCE7_GUST = 0.85

#: Table 26.6-1: directionality factor of the main system of a building.
ASCE7_KD = 0.85

_MIN_HEIGHT = 4.572  # 15 ft

# Figure 27.3-1, wind normal to the ridge, θ >= 10°: windward slope.
_ROOF_ANGLES = (10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 45.0, 60.0)
_WINDWARD_MIN: dict[float, tuple[float, ...]] = {
    0.25: (-0.7, -0.5, -0.3, -0.2, -0.2, 0.0, 0.4, 0.6),
    0.5: (-0.9, -0.7, -0.4, -0.3, -0.2, -0.2, 0.0, 0.6),
    1.0: (-1.3, -1.0, -0.7, -0.5, -0.3, -0.2, 0.0, 0.6),
}
_WINDWARD_MAX: dict[float, tuple[float, ...]] = {
    0.25: (-0.18, 0.0, 0.2, 0.3, 0.3, 0.4, 0.4, 0.6),
    0.5: (-0.18, -0.18, 0.0, 0.2, 0.2, 0.3, 0.4, 0.6),
    1.0: (-0.18, -0.18, -0.18, 0.0, 0.2, 0.2, 0.3, 0.6),
}
_LEEWARD: dict[float, tuple[tuple[float, float], ...]] = {
    0.25: ((10.0, -0.3), (15.0, -0.5), (20.0, -0.6)),
    0.5: ((10.0, -0.5), (15.0, -0.5), (20.0, -0.6)),
    1.0: ((10.0, -0.7), (15.0, -0.6), (20.0, -0.6)),
}
#: The second coefficient of the flat-roof zones and of the low windward slopes.
ASCE7_ROOF_CP_MAX = -0.18


def asce7_kz(z: float, exposure: str = "C") -> float:
    """Velocity pressure exposure coefficient of Table 26.10-1 at ``z`` metres."""
    if exposure not in ASCE7_EXPOSURES:
        raise WindError(f"Unknown exposure category {exposure!r}.")
    alpha, zg = ASCE7_EXPOSURES[exposure]
    return float(2.01 * (min(max(z, _MIN_HEIGHT), zg) / zg) ** (2.0 / alpha))


def asce7_ground_elevation_factor(elevation: float) -> float:
    """Ke of Table 26.9-1 for a site ``elevation`` metres above sea level."""
    return math.exp(-0.000119 * elevation)


def asce7_velocity_pressure(
    z: float,
    speed: float,
    exposure: str = "C",
    *,
    kzt: float = 1.0,
    kd: float = ASCE7_KD,
    ke: float = 1.0,
) -> float:
    """qz of Eq. 26.10-1 in N/m², for the basic wind speed in m/s."""
    return 0.613 * asce7_kz(z, exposure) * kzt * kd * ke * speed**2


def asce7_leeward_wall_cp(ratio: float) -> float:
    """Figure 27.3-1: leeward wall, by L/B (along the wind over across it)."""
    return _interpolate(ratio, ((1.0, -0.5), (2.0, -0.3), (4.0, -0.2)))


def asce7_area_reduction(area: float) -> float:
    """Figure 27.3-1: reduction of the -1.3 coefficient with its area in m²."""
    return _interpolate(area, ((9.29, 1.0), (23.23, 0.9), (92.9, 0.8)))


def _by_ratio(ratio: float, values: dict[float, float]) -> float:
    return _interpolate(ratio, sorted(values.items()))


def asce7_windward_roof_cp(
    angle: float, h_over_l: float, *, area: float | None = None
) -> tuple[float, float]:
    """Figure 27.3-1: the two Cp of a windward slope of ``angle`` >= 10 degrees.

    ``area`` (m², the slope) reduces the -1.3 of a steep building (h/L >= 1).
    """
    if angle < 10.0:
        raise WindError("Below 10 degrees the roof takes the flat-roof zones.")
    reduction = asce7_area_reduction(area) if area is not None else 1.0
    out = []
    for table in (_WINDWARD_MIN, _WINDWARD_MAX):
        per_ratio = {}
        for ratio, row in table.items():
            points = [
                (a, v * reduction if v == -1.3 else v)
                for a, v in zip(_ROOF_ANGLES, row, strict=True)
            ]
            # Beyond 60 degrees the coefficient is 0.01 θ, up to a wall's 0.8.
            per_ratio[ratio] = (
                min(0.8, 0.01 * angle) if angle >= 60.0 else _interpolate(angle, points)
            )
        out.append(_by_ratio(h_over_l, per_ratio))
    return out[0], out[1]


def asce7_leeward_roof_cp(angle: float, h_over_l: float) -> float:
    """Figure 27.3-1: Cp of a leeward slope of ``angle`` >= 10 degrees."""
    return _by_ratio(h_over_l, {r: _interpolate(angle, pts) for r, pts in _LEEWARD.items()})


def asce7_roof_zones(height: float, along: float, across: float) -> Profile:
    """Figure 27.3-1: Cp against the distance from the windward edge.

    For a roof below 10 degrees, or any roof with the wind along the ridge.
    ``height`` is h, ``along`` the plan dimension parallel to the wind (L) and
    ``across`` the other one (B). These are the first (most negative) values;
    the second one is :data:`ASCE7_ROOF_CP_MAX` everywhere.
    """
    h = height
    low = steps((0.0, h, 2.0 * h, math.inf), (-0.9, -0.5, -0.3))
    reduced = -1.3 * asce7_area_reduction(across * min(h / 2.0, along))
    high = steps((0.0, h / 2.0, math.inf), (reduced, -0.7))
    ratio = h / along

    def fn(d: float) -> float:
        return _by_ratio(ratio, {0.5: low.at(d), 1.0: high.at(d)})

    return Profile(fn, (h / 2.0, h, 2.0 * h))


def asce7_wind_cases(
    shape: BuildingShape,
    *,
    speed: float,
    exposure: str = "C",
    kzt: float = 1.0,
    kd: float = ASCE7_KD,
    ke: float = 1.0,
    gust: float = ASCE7_GUST,
    openings: str = "closed",
    directions: Sequence[str] = DIRECTIONS,
) -> list[WindCase]:
    """Two cases per direction (A and B), by ASCE 7-16 chapter 27, part 1.

    A dominant opening in one wall (``openings`` names it) makes the building
    partially enclosed; closed, or with openings spread over the four walls, it
    takes the internal pressure of an enclosed building.
    """
    if speed <= 0.0:
        raise WindError("The basic wind speed must be positive.")
    if min(kzt, kd, ke, gust) <= 0.0:
        raise WindError("The wind factors must be positive.")
    _check(openings, directions)
    asce7_kz(1.0, exposure)  # validates the exposure
    gcpi = ASCE7_GCPI["partially_enclosed" if openings in WALLS else "enclosed"]

    def q(z: float) -> float:
        return asce7_velocity_pressure(z, speed, exposure, kzt=kzt, kd=kd, ke=ke)

    def windward(internal: float) -> Profile:
        def fn(z: float) -> float:
            return q(z) * gust * 0.8 - internal

        return Profile(fn, (_MIN_HEIGHT, zg))

    def zoned_roof(internal: float, zones: Profile, distance: Callable[[float], float]) -> Profile:
        def fn(s: float) -> float:
            return qh * gust * zones.at(distance(s)) - internal

        return Profile(fn, tuple(sorted(distance(b) for b in zones.breaks)))

    h = shape.mean_roof_height
    qh = q(h)
    angle = shape.roof_angle
    zg = ASCE7_EXPOSURES[exposure][1]
    cases: list[WindCase] = []
    for direction in directions:
        windward_wall, leeward, sides = _sides(direction)
        across_ridge = direction[1] == "X"
        along, across = (shape.width, shape.length) if across_ridge else (shape.length, shape.width)
        ratio = h / along
        distance = _distance(shape, direction)
        leeward_cp = asce7_leeward_wall_cp(along / across)
        zoned = (not across_ridge) or angle < 10.0
        zones = asce7_roof_zones(h, along, across)

        for label, pick, sign in (("A", 0, 1.0), ("B", 1, -1.0)):
            internal = sign * gcpi * qh
            walls = {
                windward_wall: windward(internal),
                leeward: constant(qh * gust * leeward_cp - internal),
                **{side: constant(qh * gust * -0.7 - internal) for side in sides},
            }
            coefficients = {
                "windward_wall": 0.8,
                "leeward_wall": leeward_cp,
                "side_wall": -0.7,
                "internal": sign * gcpi,
            }
            roof: list[RoofLoad] = []
            for plane in shape.planes():
                if zoned:
                    if pick == 0:
                        profile = zoned_roof(internal, zones, distance)
                        coefficients["roof"] = zones.at(0.0)
                    else:
                        profile = constant(qh * gust * ASCE7_ROOF_CP_MAX - internal)
                        coefficients["roof"] = ASCE7_ROOF_CP_MAX
                    roof.append(RoofLoad(plane, "x" if across_ridge else "y", profile))
                    continue
                if _faces_wind(plane, direction):
                    slope_area = (
                        math.hypot(plane.x1 - plane.x0, shape.ridge_height - shape.eave_height)
                        * shape.length
                    )
                    cp = asce7_windward_roof_cp(angle, ratio, area=slope_area)[pick]
                    coefficients["windward_roof"] = cp
                else:
                    cp = asce7_leeward_roof_cp(angle, ratio)
                    coefficients["leeward_roof"] = cp
                roof.append(RoofLoad(plane, "x", constant(qh * gust * cp - internal)))
            cases.append(
                WindCase(f"WIND {direction} {label}", direction, walls, tuple(roof), coefficients)
            )
    return cases


__all__ = [
    "ASCE7_EXPOSURES",
    "ASCE7_GCPI",
    "ASCE7_GUST",
    "ASCE7_KD",
    "ASCE7_ROOF_CP_MAX",
    "DIRECTIONS",
    "KGF",
    "OPENINGS",
    "RNC07_CP",
    "RNC07_INTERNAL_CP",
    "RNC07_REGIONAL_SPEEDS",
    "RNC07_ROUGHNESS",
    "RNC07_TOPOGRAPHY",
    "ROOF_SHAPES",
    "WALLS",
    "BuildingShape",
    "Profile",
    "RoofLoad",
    "RoofPlane",
    "WindCase",
    "WindError",
    "asce7_area_reduction",
    "asce7_ground_elevation_factor",
    "asce7_kz",
    "asce7_leeward_roof_cp",
    "asce7_leeward_wall_cp",
    "asce7_roof_zones",
    "asce7_velocity_pressure",
    "asce7_wind_cases",
    "asce7_windward_roof_cp",
    "constant",
    "rnc07_design_speed",
    "rnc07_height_factor",
    "rnc07_internal_cp",
    "rnc07_pressure",
    "rnc07_regional_speed",
    "rnc07_topography_factor",
    "rnc07_wind_cases",
    "rnc07_windward_roof_cp",
    "steps",
]
