"""Equivalent lateral force (ELF) seismic loads: base shear and its storey distribution.

The codes are the ones of :mod:`opensees_studio.core.seismic_codes`, one module
each (ASCE/SEI 7-16 §12.8, TBDY 2018 §4.7, RNC-07 Art. 32, NSCM Managua 8.2.1):
a code gives the base shear, shares it between the storeys, and says which
period and height it accepts. This module does what no code changes.

The storey weights are the masses the solver gets (``effective_nodal_masses``:
typed masses, the mass source and diaphragm lumping) times g, gathered at the
storey levels (the project's storeys, or every elevation above the base that
carries mass). Heights are measured from the base (the lowest node).

Each storey force goes to the floor: to a horizontal diaphragm's retained node
when that is where the mass is, else shared between the floor's joints in
proportion to their mass. **Accidental eccentricity** (3D) moves it by
``±e = ±ratio × L`` across the load, ``L`` the floor's extent in that
direction: a torque ``F e`` at the retained node, or the mass-proportional
shares tilted so their resultant acts ``e`` off the centre of mass.

The code coefficients (R, Ie / I, D, Ct, the period) are the engineer's: the
generator applies the formulas, it does not pick the structural system.

This module is part of ``core``: no Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from opensees_studio.core.mass_source import effective_nodal_masses
from opensees_studio.core.plane import VERTICAL_AXIS
from opensees_studio.core.seismic_codes import (
    SEISMIC_CODES,
    ElfError,
    ElfParameters,
    seismic_code,
)
from opensees_studio.core.seismic_codes.asce7_16 import ASCE_PERIOD_SYSTEMS, asce7_cs, asce7_k
from opensees_studio.core.seismic_codes.nscm2021 import nscm_cs
from opensees_studio.core.seismic_codes.rnc07 import rnc07_coefficient
from opensees_studio.core.seismic_codes.tbdy2018 import TBDY_PERIOD_SYSTEMS, tbdy_sar
from opensees_studio.core.storeys import (
    base_elevation,
    elevation_tolerance,
    nodes_at_elevation,
    storey_levels,
)
from opensees_studio.core.units import UnitSystem, gravity, length_scale

if TYPE_CHECKING:
    from opensees_studio.core.project import Project

CODE_LABELS: dict[str, str] = {key: code.label for key, code in SEISMIC_CODES.items()}
#: Codes whose hazard is a0 and a soil class rather than SDS and SD1.
NICARAGUA_CODES: frozenset[str] = frozenset(
    key for key, code in SEISMIC_CODES.items() if code.hazard == "a0"
)


@dataclass(frozen=True)
class ElfLevel:
    """One storey of the distribution."""

    name: str
    elevation: float
    height: float
    """Above the base."""
    weight: float
    force: float
    nodes: tuple[int, ...]


@dataclass
class ElfResult:
    """Base shear, its distribution, and what the code formulas gave."""

    code: str
    direction: int
    """Global axis of the loads: 0 = X, 1 = Y."""
    period: float
    total_weight: float
    coefficient: float
    """ASCE Cs, or TBDY Vt / W."""
    base_shear: float
    levels: list[ElfLevel]
    notes: list[str] = field(default_factory=list)
    """The governing limit and anything left out, for the dialog."""

    def table(self) -> list[tuple[str, float, float, float]]:
        """``(storey, height, weight, force)`` rows, top first."""
        return [(lv.name, lv.height, lv.weight, lv.force) for lv in reversed(self.levels)]


# ─────────────────────────── periods ───────────────────────────
def approximate_period(code: str, system: str, height: float, length_to_m: float) -> float:
    """The code's empirical period for a building ``height`` tall (model length units)."""
    h_m = height * length_to_m
    if h_m <= 0.0:
        raise ElfError("The building has no height above its base.")
    return seismic_code(code).approximate_period(system, h_m)


# ─────────────────────────── the levels ───────────────────────────
@dataclass(frozen=True)
class _Level:
    name: str
    elevation: float
    nodes: tuple[int, ...]


def _levels(project: Project, masses: dict[int, np.ndarray], direction: int) -> list[_Level]:
    """The project's storeys, else every elevation above the base that carries mass."""
    levels = storey_levels(project)
    if levels:
        return [
            _Level(lv.storey.name or f"Storey {k}", lv.storey.elevation, lv.nodes)
            for k, lv in enumerate(levels, start=1)
        ]
    base = base_elevation(project)
    tol = elevation_tolerance(project)
    coords = {n.id: n.coords for n in project.nodes}
    elevations: list[float] = []
    for nid, mass in masses.items():
        z = float(coords[nid][VERTICAL_AXIS])
        if mass[direction] > 0.0 and z > base + tol and all(abs(z - e) > tol for e in elevations):
            elevations.append(z)
    return [
        _Level(f"Level {k}", z, tuple(nodes_at_elevation(project, z)))
        for k, z in enumerate(sorted(elevations), start=1)
    ]


# ─────────────────────────── the generator ───────────────────────────
def equivalent_lateral_forces(
    project: Project,
    direction: int,
    p: ElfParameters,
    *,
    masses: dict[int, np.ndarray] | None = None,
) -> ElfResult:
    """Base shear and storey forces of ``project`` for loads along global axis ``direction``.

    ``masses`` is ``effective_nodal_masses(project)``, for a caller that asks
    for more than one direction of the same model.
    """
    if project.ndm == 2 and direction != 0:
        raise ElfError("A 2D model takes lateral loads along X only (it lives in the X-Z plane).")
    if p.period <= 0.0:
        raise ElfError("The period T must be positive.")
    code = seismic_code(p.code)
    code.check_hazard(p)
    units = project.meta.units
    g = gravity(units)
    if masses is None:
        masses = effective_nodal_masses(project)
    levels = _levels(project, masses, direction)
    if not levels:
        raise ElfError(
            "No storey carries mass: define storeys (Define → Storeys) and masses "
            "(Assign → Joint → Masses, or Define → Mass Source)."
        )
    base = base_elevation(project)
    weights = [
        g * sum(float(masses[n][direction]) for n in lv.nodes if n in masses) for lv in levels
    ]
    total = float(sum(weights))
    if total <= 0.0:
        raise ElfError("The storeys carry no mass in that direction.")
    heights = [lv.elevation - base for lv in levels]
    notes: list[str] = []
    on_levels = {n for lv in levels for n in lv.nodes}
    off = g * sum(
        float(m[direction])
        for nid, m in masses.items()
        if nid not in on_levels
        and float(project.node(nid).coords[VERTICAL_AXIS]) > base + elevation_tolerance(project)
    )
    if off > 1e-9 * total:
        notes.append(
            f"{off / (off + total):.1%} of the weight above the base lies off the storey "
            "levels and is not in W."
        )

    found = code.base_shear(p, weights, heights)
    shear, forces = found.shear, found.forces
    notes.insert(0, found.note)
    limit = static_height_limit(p)
    if limit is not None:
        height_m = max(heights) * length_in_metres(project)
        if height_m > limit[0]:
            notes.append(
                f"Height {height_m:.3g} m exceeds the {limit[0]:g} m the static method allows "
                f"here ({limit[1]}): use the modal spectral analysis."
            )
    result_levels = [
        ElfLevel(lv.name, lv.elevation, h, w, float(f), lv.nodes)
        for lv, h, w, f in zip(levels, heights, weights, forces, strict=True)
    ]
    return ElfResult(
        code=p.code,
        direction=direction,
        period=p.period,
        total_weight=total,
        coefficient=found.coefficient,
        base_shear=float(shear),
        levels=result_levels,
        notes=notes,
    )


def static_height_limit(p: ElfParameters) -> tuple[float, str] | None:
    """Largest height (m) the code allows the static method for, and the clause."""
    return seismic_code(p.code).height_limit(p)


def building_height(project: Project) -> float:
    """Highest node above the lowest one, in model length units."""
    if not project.nodes:
        return 0.0
    zs = [float(n.coords[VERTICAL_AXIS]) for n in project.nodes]
    return max(zs) - min(zs)


def length_in_metres(project: Project) -> float:
    """Metres per model length unit."""
    return length_scale(project.meta.units, UnitSystem.SI_M_N)


# ─────────────────────────── nodal loads ───────────────────────────
def _retained_with_mass(
    project: Project, level_nodes: Sequence[int], masses: dict[int, np.ndarray], direction: int
) -> int | None:
    """A horizontal diaphragm's retained node on this floor that holds its mass, if any."""
    floor = set(level_nodes)
    for diaphragm in project.diaphragms:
        if diaphragm.perp_dirn != 3:
            continue
        node = diaphragm.retained_node
        on_floor = node in floor or _on_same_level(project, node, level_nodes)
        if node in masses and on_floor and float(masses[node][direction]) > 0.0:
            return node
    return None


def _on_same_level(project: Project, node: int, level_nodes: Sequence[int]) -> bool:
    if not level_nodes:
        return False
    tol = elevation_tolerance(project)
    z = float(project.node(node).coords[VERTICAL_AXIS])
    return abs(z - float(project.node(level_nodes[0]).coords[VERTICAL_AXIS])) <= tol


def nodal_forces(
    project: Project,
    result: ElfResult,
    eccentricity_sign: int = 0,
    ratio: float = 0.05,
    *,
    masses: dict[int, np.ndarray] | None = None,
) -> dict[int, tuple[float, float, float, float, float, float]]:
    """The storey forces as global nodal loads, with ``±ratio`` accidental eccentricity.

    ``eccentricity_sign`` is -1, 0 or +1; it is ignored in 2D. ``masses`` is
    ``effective_nodal_masses(project)``, as in :func:`equivalent_lateral_forces`.
    """
    if masses is None:
        masses = effective_nodal_masses(project)
    d = result.direction
    across = 1 - d  # the horizontal axis perpendicular to the load (3D)
    coords = {n.id: np.asarray(n.coords, dtype=float) for n in project.nodes}
    out: dict[int, np.ndarray] = {}

    def add(nid: int, slot: int, value: float) -> None:
        out.setdefault(nid, np.zeros(6))[slot] += value

    for level in result.levels:
        force = level.force
        floor = [n for n in level.nodes if n in coords]
        if not floor or force == 0.0:
            continue
        extent = 0.0
        if project.ndm == 3 and eccentricity_sign:
            values = [coords[n][across] for n in floor]
            extent = max(values) - min(values)
        e = eccentricity_sign * ratio * extent if project.ndm == 3 else 0.0
        retained = _retained_with_mass(project, floor, masses, d)
        if retained is not None:
            add(retained, d, force)
            if e:
                # The torque of F acting e across the load: r x F about +Z is
                # -F e for a load along X (e along Y), +F e along Y (e along X).
                add(retained, 5, force * e * (1.0 if d == 1 else -1.0))
            continue
        m = np.array([float(masses.get(n, np.zeros(6))[d]) for n in floor])
        if m.sum() <= 0.0:
            m = np.ones(len(floor))
        total = m.sum()
        shares = force * m / total
        if e and project.ndm == 3:
            r = np.array([coords[n][across] for n in floor])
            centre = float(m @ r) / total
            r = r - centre
            inertia = float(m @ r**2)
            if inertia > 0.0:
                shares = force * m / total * (1.0 + e * total * r / inertia)
        for nid, value in zip(floor, shares, strict=True):
            add(nid, d, float(value))
    return {nid: tuple(float(v) for v in vec) for nid, vec in out.items()}  # type: ignore[misc]


__all__ = [
    "ASCE_PERIOD_SYSTEMS",
    "CODE_LABELS",
    "NICARAGUA_CODES",
    "TBDY_PERIOD_SYSTEMS",
    "ElfError",
    "ElfLevel",
    "ElfParameters",
    "ElfResult",
    "approximate_period",
    "asce7_cs",
    "asce7_k",
    "building_height",
    "equivalent_lateral_forces",
    "length_in_metres",
    "nodal_forces",
    "nscm_cs",
    "rnc07_coefficient",
    "static_height_limit",
    "tbdy_sar",
]
