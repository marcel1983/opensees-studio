"""Parametric steel warehouse: portal frames, purlins, girts, bracing, loads.

A "bodega" (nave industrial) here is a row of identical portal frames along
global Y, each in an X-Z plane: columns on a grid of nave spans carrying a roof
that is flat, single-pitched or double-pitched (the roof line and the column
heights are :class:`opensees_studio.core.frames.PortalFrameSpec`'s, so the 2D
wizard and this one cannot disagree). Between the frames run the secondary
members:

* **Purlins** on the roof, on lines equally spaced between the eaves, the ridge
  and the interior column lines, never further apart than the spacing asked
  for. The eave and ridge purlins double as the eave strut and the ridge tie.
* **Girts** on the two side walls (the walls along Y), the same way.
* **End wall columns** under the rafter of the first and of the last frame,
  when a spacing is given, with the girts of the end walls between them. An end
  wall column is pinned at both ends, its web along Y to span against the wind,
  and it stands under a purlin line, so its top reaction goes straight into a
  purlin and from there into the roof bracing.
* **X bracing** of the roof and of the side walls in the braced bays (by
  default the first and the last).

The roof of each frame is a rafter or, with ``roof_structure="truss"``, a
**roof truss**: a top chord on the roof line with a panel point under every
purlin line, a bottom chord (level, or parallel to the roof), verticals and
diagonals (Pratt, Howe or Warren with verticals). The chords are continuous
and run into the columns, which go on up to the top chord, so the truss and
its columns work as a frame; the web members are pinned. The bottom chord is
tied from frame to frame at the column lines, at the ridge and at every n-th
panel point asked for, and in the braced bays those tie lines get a vertical X
between the two chords (sway bracing) that takes them to the roof bracing.

The rules that are easy to get wrong, and that the tests pin:

* **Secondary members are pinned.** Purlins, girts and braces release both
  bending moments at both ends (and a purlin or girt its torsion at one end),
  so they carry their own load to the frames and never add bending or
  torsional restraint to them.
* **A purlin does not brace the rafter unless it has a stabilising angle.** A
  purlin sits on the top flange; without a fly brace (the angle from the purlin
  down to the bottom flange) it does not hold the compression flange against
  lateral-torsional buckling. So :func:`member_design_overrides` gives every
  rafter element the unbraced length between *fly-braced* purlins, and the whole
  eave-to-ridge length when there are none; the girts and the side columns
  follow the same rule. Without the overrides ``core.design.members`` would take
  every purlin as a bracing point.
* **A purlin does brace the top chord of a truss**, because it is fixed to the
  chord itself; the bottom chord is braced only at its tie lines, and
  :func:`member_design_overrides` gives it that length.
* **Loads act on the purlins**, as on the real roof: a load per area becomes a
  uniform load per length on each purlin element (its tributary width times the
  pressure), in the element's local axes — a purlin's web stands normal to the
  roof, so gravity has a component along both of them.
* **Wind acts on what the cladding hangs from.** A wind case
  (:mod:`opensees_studio.core.wind`) is a net pressure per surface;
  :func:`wind_loads` turns it into uniform loads on the purlins (roof), on the
  girts and the eave purlin (a wall with girts) or on the columns (a wall
  without), normal to the surface. The lower half of the lowest wall strip goes
  straight into the ground and is not applied.
* **Snow and ash fall on the plan of the roof.** A case of
  :mod:`opensees_studio.core.snow` (volcanic ash by RNC-07 Art. 14 and NSCM
  7.3, snow by ASCE 7-16 chapter 7 or EN 1991-1-3) is a vertical load per area
  of horizontal projection that varies across the building; :func:`snow_loads`
  gives each purlin what falls on the half strip to either neighbour. The
  balanced and the drifted arrangements are alternatives in the combinations.
* **The earthquake is a share of the weight at each joint.**
  :func:`seismic_coefficient` gives ``c = V / W`` on the plateau of the spectrum
  of RNC-07, NSCM or ASCE 7 (the period is not used); the seismic weight is the
  steel, the roof dead load and the part of the roof live load the code counts,
  lumped on the joints, and :func:`seismic_loads` shares ``c W`` between them by
  weight and height. An earthquake case acts both ways in the combinations; a
  wind case never does.

The module is pure (no Qt, no OpenSees): :func:`build_warehouse` returns the
geometry, :func:`plan_warehouse` everything a project needs to become that
warehouse (sections, load cases, loads, combinations, groups, grid, design
overrides) without touching the project, and :meth:`WarehousePlan.apply` writes
it for a script. The desktop inserts the same plan through undoable commands.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from opensees_studio.core.frames import (
    GRID_TOLERANCE,
    PortalFrameError,
    PortalFrameSpec,
    RoofType,
    SupportCondition,
)
from opensees_studio.core.geometry.elements import ElasticBeamColumn
from opensees_studio.core.geometry.frame_options import EndRelease, FrameReleases
from opensees_studio.core.geometry.grid import (
    CoordinateGridSystem,
    CoordinateSystem,
    GridSystem,
    make_grid_lines,
)
from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.geometry.node import Node, Restraint6
from opensees_studio.core.snow import (
    SnowCase,
    SnowError,
    asce7_snow_cases,
    ash_cases,
    en1991_snow_cases,
    roof_planes,
)
from opensees_studio.core.trusses import TrussType
from opensees_studio.core.units import UnitSystem, force_scale, length_scale
from opensees_studio.core.wind import (
    DIRECTIONS,
    OPENINGS,
    BuildingShape,
    WindCase,
    WindError,
    asce7_wind_cases,
    en1991_wind_cases,
    rnc07_wind_cases,
)

if TYPE_CHECKING:
    from opensees_studio.core.project import Project

#: The model a warehouse is built in: a 3D frame model.
WAREHOUSE_NDF: tuple[int, int] = (3, 6)

#: Member groups, in the order they are created and listed, with their names.
GROUPS: dict[str, str] = {
    "columns": "Columns",
    "rafters": "Rafters",
    "purlins": "Purlins",
    "girts": "Girts",
    "roof_bracing": "Roof bracing",
    "wall_bracing": "Wall bracing",
    "end_columns": "End wall columns",
    "top_chords": "Truss top chords",
    "bottom_chords": "Truss bottom chords",
    "truss_webs": "Truss web members",
    "chord_ties": "Bottom chord ties",
    "sway_bracing": "Truss sway bracing",
}

#: Display colour of each group (#rrggbb).
GROUP_COLOURS: dict[str, str] = {
    "columns": "#4363d8",
    "rafters": "#e6194b",
    "purlins": "#3cb44b",
    "girts": "#469990",
    "roof_bracing": "#f58231",
    "wall_bracing": "#911eb4",
    "end_columns": "#9a6324",
    "top_chords": "#c2185b",
    "bottom_chords": "#800000",
    "truss_webs": "#808000",
    "chord_ties": "#000075",
    "sway_bracing": "#f032e6",
}

#: The section each kind of member takes: section key -> the groups it serves.
SECTION_KEYS: dict[str, str] = {
    "column": "Columns",
    "rafter": "Rafters",
    "purlin": "Purlins",
    "girt": "Girts",
    "brace": "Bracing",
    "end_column": "End wall columns",
    "top_chord": "Truss top chords",
    "bottom_chord": "Truss bottom chords",
    "truss_web": "Truss web members",
    "chord_tie": "Bottom chord ties",
}

#: What carries the roof of each frame.
ROOF_STRUCTURES: tuple[str, ...] = ("rafter", "truss")

#: The web patterns of a roof truss (all with a vertical under every purlin line).
ROOF_TRUSS_TYPES: tuple[TrussType, ...] = (
    TrussType.PRATT,
    TrussType.HOWE,
    TrussType.WARREN_VERTICALS,
)

#: The bottom chord of a roof truss: level, or parallel to the roof.
TRUSS_BOTTOMS: tuple[str, ...] = ("horizontal", "parallel")

#: The section keys only a roof truss needs.
TRUSS_SECTION_KEYS: tuple[str, ...] = ("top_chord", "bottom_chord", "truss_web", "chord_tie")

#: AISC shape created for a section key when the caller chooses none.
DEFAULT_AISC_SHAPES: dict[str, str] = {
    "column": "W14X48",
    "rafter": "W16X40",
    "brace": "L3X3X1_4",
    "end_column": "W8X31",
    "top_chord": "HSS6X6X1_4",
    "bottom_chord": "HSS6X6X1_4",
    "truss_web": "HSS3X3X3_16",
    "chord_tie": "HSS4X4X3_16",
}

#: Default purlin and girt: a lipped channel 150 x 50 x 15 x 2.38 mm (a 2" x 6"
#: "perlín" of 3/32"), a size every local supplier lists. Dimensions in mm.
DEFAULT_PURLIN_MM: dict[str, float] = {"d": 150.0, "bf": 50.0, "lip": 15.0, "t": 2.38, "r": 2.38}

_PINNED = EndRelease(released=("M2", "M3"))
_PINNED_FREE_TORSION = EndRelease(released=("T", "M2", "M3"))
#: A brace: no moments at either end, torsion kept so it cannot spin.
BRACE_RELEASES = FrameReleases(i=_PINNED, j=_PINNED)
#: A purlin or girt: simply supported, torsion held at one end only.
SECONDARY_RELEASES = FrameReleases(i=_PINNED, j=_PINNED_FREE_TORSION)
#: The top of an end wall column: it leans on the rafter, it does not frame into it.
POST_TOP_RELEASES = FrameReleases(j=_PINNED)

#: Linear solver of the load cases the wizard creates. A warehouse is a 3D model
#: of many pinned members, each with its own released rotations: the band solver
#: a new case has by default takes tens of seconds per case on it, a sparse one
#: a fraction of a second, for the same result.
CASE_SYSTEM = "UmfPack"
_DEFAULT_SYSTEM = "BandGeneral"
#: From this many nodes the plan says so when a case of the project keeps the band solver.
SLOW_SOLVER_NODES = 150

#: Significant digits of the derived numbers a plan writes (the angle of a
#: purlin, loads, unbraced lengths, the properties of the default purlin).
#: They come out of square roots, sines and dot products, whose last digit
#: depends on the processor and on the C library: unrounded, the same
#: warehouse saves different bytes on two machines.
PORTABLE_DIGITS = 12
#: A component of a load this many times smaller than its largest one is the
#: round-off of a projection onto the member's axes, not a load.
NEGLIGIBLE_COMPONENT = 1e-9

#: The groups only a roof truss has.
TRUSS_GROUPS: tuple[str, ...] = (
    "top_chords",
    "bottom_chords",
    "truss_webs",
    "chord_ties",
    "sway_bracing",
)

#: The groups that are X bracing.
BRACING_GROUPS: tuple[str, ...] = ("roof_bracing", "wall_bracing", "sway_bracing")

#: A girt line of an end wall stays this share of the girt spacing below the rafter.
END_GIRT_CLEARANCE = 0.25


class WarehouseError(ValueError):
    """The numbers do not describe a warehouse."""


@dataclass(frozen=True)
class WarehouseSpec:
    """A warehouse in project units: frames in X-Z planes, repeated along Y."""

    span: float
    """Width of one nave: the distance between column lines across the building."""
    eave_height: float
    frame_spacing: float
    """Distance between consecutive portal frames (the bay length along Y)."""
    n_frames: int = 5
    n_naves: int = 1
    roof: RoofType = RoofType.GABLE
    slope: float = 0.10
    support: SupportCondition = SupportCondition.PINNED
    purlin_spacing: float = 1.5
    """Largest distance between purlin lines, along the roof surface."""
    girt_spacing: float = 0.0
    """Largest distance between girt lines on the side walls; 0 = no girts."""
    rafter_fly_brace_every: int = 0
    """Every n-th purlin has a stabilising angle to the rafter's bottom flange; 0 = none."""
    column_fly_brace_every: int = 0
    """Every n-th girt has a stabilising angle to the column's inner flange; 0 = none."""
    roof_bracing: bool = True
    wall_bracing: bool = True
    braced_bays: tuple[int, ...] | None = None
    """Bays (0-based, between frame ``b`` and ``b + 1``) with X bracing; None = first and last."""
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    end_wall_column_spacing: float = 0.0
    """Largest distance between the columns of an end wall; 0 = no end wall columns.

    With end wall columns the end walls also get girts, at the girt spacing.
    """
    roof_structure: str = "rafter"
    """``"rafter"`` or ``"truss"`` (:data:`ROOF_STRUCTURES`)."""
    truss_type: TrussType = TrussType.PRATT
    """Web pattern of the roof truss, one of :data:`ROOF_TRUSS_TYPES`."""
    truss_bottom: str = "horizontal"
    """``"horizontal"``: a level bottom chord; ``"parallel"``: parallel to the roof."""
    truss_depth: float = 0.0
    """Depth of the truss, measured plumb: at the eave for a level bottom chord,
    everywhere for a parallel one. The eave height stays the top of the roof line,
    so the clear height under the truss is the eave height less this depth."""
    bottom_chord_tie_every: int = 0
    """Every n-th panel point of the bottom chord is tied to the next frame; the
    column lines and the ridge always are. 0 = only those."""

    def __post_init__(self) -> None:
        if self.span <= 0.0:
            raise WarehouseError("The nave span must be positive.")
        if self.eave_height <= 0.0:
            raise WarehouseError("The eave height must be positive.")
        if self.frame_spacing <= 0.0:
            raise WarehouseError("The distance between frames must be positive.")
        if self.n_frames < 2:
            raise WarehouseError("A warehouse needs at least two frames.")
        if self.n_naves < 1:
            raise WarehouseError("A warehouse needs at least one nave.")
        if not 0.0 <= self.slope < 1.0:
            raise WarehouseError("The roof slope must be between 0 and 100 %.")
        if self.purlin_spacing <= 0.0:
            raise WarehouseError("The purlin spacing must be positive.")
        if self.girt_spacing < 0.0:
            raise WarehouseError("The girt spacing cannot be negative.")
        if self.end_wall_column_spacing < 0.0:
            raise WarehouseError("The end wall column spacing cannot be negative.")
        if self.rafter_fly_brace_every < 0 or self.column_fly_brace_every < 0:
            raise WarehouseError("A stabilising angle interval cannot be negative.")
        if len(self.origin) != 3:
            raise WarehouseError("The origin needs three coordinates.")
        if self.roof_structure not in ROOF_STRUCTURES:
            raise WarehouseError(f"Unknown roof structure {self.roof_structure!r}.")
        if self.has_truss:
            if self.truss_type not in ROOF_TRUSS_TYPES:
                raise WarehouseError(
                    "A roof truss is Pratt, Howe or Warren with verticals: it needs a "
                    "vertical under every purlin line."
                )
            if self.truss_bottom not in TRUSS_BOTTOMS:
                raise WarehouseError(f"Unknown bottom chord {self.truss_bottom!r}.")
            if self.truss_depth <= 0.0:
                raise WarehouseError("The truss depth must be positive.")
            if self.truss_depth >= self.eave_height:
                raise WarehouseError("The truss depth must be less than the eave height.")
            if self.bottom_chord_tie_every < 0:
                raise WarehouseError("The bottom chord tie interval cannot be negative.")
        for bay in self.braced_bays or ():
            if not 0 <= bay < self.n_frames - 1:
                raise WarehouseError(
                    f"Braced bay {bay + 1} does not exist: there are {self.n_frames - 1} bay(s)."
                )

    # ── derived ─────────────────────────────────────────────────────
    @property
    def width(self) -> float:
        """Total width across the naves."""
        return self.span * self.n_naves

    @property
    def length(self) -> float:
        """Total length along the frames."""
        return self.frame_spacing * (self.n_frames - 1)

    @property
    def n_bays(self) -> int:
        return self.n_frames - 1

    @property
    def profile(self) -> PortalFrameSpec:
        """The roof line and column heights, shared with the 2D portal frame."""
        try:
            return PortalFrameSpec(
                bay_width=self.span,
                eave_height=self.eave_height,
                column_section_id=1,
                rafter_section_id=1,
                roof=self.roof,
                slope=self.slope,
                n_bays=self.n_naves,
                support=self.support,
                restrain_out_of_plane=False,
            )
        except PortalFrameError as exc:  # pragma: no cover - same checks as above
            raise WarehouseError(str(exc)) from exc

    @property
    def ridge_height(self) -> float:
        return self.profile.ridge_height

    @property
    def has_truss(self) -> bool:
        """The roof of each frame is a truss, not a rafter."""
        return self.roof_structure == "truss"

    def bottom_chord_height(self, x: float) -> float:
        """Elevation of the bottom chord of the roof truss ``x`` across the building."""
        if self.truss_bottom == "parallel":
            return self.profile.roof_height(x) - self.truss_depth
        return self.eave_height - self.truss_depth

    def section_keys(self) -> list[str]:
        """The keys of :data:`SECTION_KEYS` this warehouse has members for."""
        skip: set[str] = {"rafter"} if self.has_truss else set(TRUSS_SECTION_KEYS)
        if self.end_wall_column_spacing <= 0.0:
            skip.add("end_column")
        return [key for key in SECTION_KEYS if key not in skip]

    def bracing_bays(self) -> tuple[int, ...]:
        """The braced bays, sorted; the first and the last when none were chosen."""
        if self.braced_bays is None:
            return tuple(sorted({0, self.n_bays - 1}))
        return tuple(sorted(set(self.braced_bays)))

    def column_lines(self) -> list[float]:
        """X of every column line, from the left eave."""
        return [i * self.span for i in range(self.n_naves + 1)]

    def roof_breaks(self) -> list[float]:
        """X where the rafter is held or changes direction: column lines and the ridge."""
        xs = self.column_lines()
        if self.roof is RoofType.GABLE:
            xs.append(self.width / 2.0)
        return _distinct(xs)

    def girt_heights(self) -> list[float]:
        """Elevation of each girt line above the base (none at the base or the eave)."""
        if self.girt_spacing <= 0.0:
            return []
        n = max(1, math.ceil(self.eave_height / self.girt_spacing - 1e-9))
        return [k * self.eave_height / n for k in range(1, n)]

    def end_wall_levels(self) -> list[float]:
        """Elevation of each girt line of an end wall: the side wall's, carried up to the ridge."""
        if self.girt_spacing <= 0.0 or self.end_wall_column_spacing <= 0.0:
            return []
        n = max(1, math.ceil(self.eave_height / self.girt_spacing - 1e-9))
        step = self.eave_height / n
        count = math.floor(self.ridge_height / step + 1e-9)
        levels = [k * self.eave_height / n for k in range(1, count + 1)]
        return [z for z in levels if z < self.ridge_height - END_GIRT_CLEARANCE * step]


def portable(value: float) -> float:
    """``value`` to :data:`PORTABLE_DIGITS` significant digits (and never ``-0.0``).

    In two steps. A product of round inputs is often exactly half way between
    two rounded values (294.4254031875), and its last bit would decide the side
    it falls to: the first rounding, two digits further, takes the round-off
    away and leaves that number exact, so it always falls to the same side.
    """
    exact = float(f"{value:.{PORTABLE_DIGITS + 2}g}")
    return float(f"{exact:.{PORTABLE_DIGITS}g}") + 0.0


def _portable_model(model: Any) -> Any:
    """``model`` (a load, a section) with its numbers rounded by :func:`portable`."""
    update: dict[str, Any] = {}
    for name, value in model:
        if isinstance(value, float):
            rounded: Any = portable(value)
        elif isinstance(value, tuple) and value and all(isinstance(v, float) for v in value):
            rounded = tuple(portable(v) for v in value)
        else:
            continue
        if repr(rounded) != repr(value):
            update[name] = rounded
    return model.model_copy(update=update) if update else model


def _components(vector: Iterable[float]) -> tuple[float, ...]:
    """The components of a load, without the round-off of its projection."""
    values = [float(v) for v in vector]
    floor = NEGLIGIBLE_COMPONENT * max(abs(v) for v in values)
    return tuple(0.0 if abs(v) <= floor else v for v in values)


def _distinct(values: Iterable[float]) -> list[float]:
    out: list[float] = []
    for value in sorted(values):
        if not out or abs(value - out[-1]) > GRID_TOLERANCE:
            out.append(value)
    return out


def _fly_braced(count: int, every: int) -> list[bool]:
    """Which of ``count + 1`` points along a segment are bracing points.

    The two ends always are (a column, the ridge, the base); an interior point
    ``k`` only when it carries a stabilising angle, every ``every``-th one.
    """
    return [k in (0, count) or (every > 0 and k % every == 0) for k in range(count + 1)]


def _unbraced_lengths(stations: list[float], braced: list[bool]) -> list[float]:
    """Per interval between consecutive ``stations``: the bracing-point distance around it."""
    out: list[float] = []
    for k in range(len(stations) - 1):
        start = max(i for i in range(k + 1) if braced[i])
        end = min(i for i in range(k + 1, len(stations)) if braced[i])
        out.append(stations[end] - stations[start])
    return out


def bottom_chord_ties(spec: WarehouseSpec, stations: list[RoofStation]) -> list[bool]:
    """Per roof station: the bottom chord under it is tied to the next frame.

    The column lines and the ridge always are; between them every
    ``bottom_chord_tie_every``-th panel point.
    """
    index = [
        next(k for k, s in enumerate(stations) if abs(s.x - x) <= GRID_TOLERANCE)
        for x in spec.roof_breaks()
    ]
    flags = [False] * len(stations)
    for first, last in itertools.pairwise(index):
        for j, tied in enumerate(_fly_braced(last - first, spec.bottom_chord_tie_every)):
            flags[first + j] = flags[first + j] or tied
    return flags


@dataclass(frozen=True)
class RoofStation:
    """One purlin line: where it is on the roof and what it carries."""

    x: float
    z: float
    tributary_slope: float
    """Roof surface width the purlin carries (half way to each neighbour)."""
    tributary_plan: float
    """The same width in plan, for loads given on the horizontal projection."""
    angle: float
    """``local_axis_angle`` that stands the purlin's web normal to the roof, degrees."""
    fly_braced: bool
    """A bracing point of the rafter: a segment end, or a purlin with a stabilising angle."""


@dataclass
class Warehouse:
    """The built warehouse: models ready to insert, and what each element is."""

    spec: WarehouseSpec
    nodes: list[Node]
    elements: list[ElasticBeamColumn]
    members: dict[str, list[int]]
    """Group key (see :data:`GROUPS`) -> element ids."""
    stations: list[RoofStation]
    purlin_station: dict[int, int] = field(default_factory=dict)
    """Purlin element id -> index of its roof station."""
    rafter_elements: list[list[int]] = field(default_factory=list)
    """Per frame: the rafter element ids from the left eave, one per station interval
    (the top chord elements when the roof is a truss)."""
    bottom_chord_elements: list[list[int]] = field(default_factory=list)
    """Per frame: the bottom chord element ids of the roof truss, as ``rafter_elements``."""
    unbraced: dict[int, float] = field(default_factory=dict)
    """Rafter, column and bottom chord element id -> unbraced length of its compression flange."""
    base_node_ids: list[int] = field(default_factory=list)
    wall_girts: dict[int, tuple[str, int, float]] = field(default_factory=dict)
    """Girt element id -> ``(wall, panel, level)``; also the bottom chord elements of
    an end truss where the chord lies on a girt line of the end wall.

    ``wall`` is a key of :data:`opensees_studio.core.wind.WALLS`; ``panel`` is
    the bay on a side wall and the left vertical on an end wall.
    """
    wall_columns: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    """Wall -> ``(column element id, vertical)``: the frame on a side wall, the
    vertical of :func:`end_wall_layout` on an end wall. A corner column is in two walls."""

    def summary(self) -> str:
        """One line for the log: what was created."""
        spec = self.spec
        roof = {RoofType.MONO_PITCH: "1 slope", RoofType.GABLE: "2 slopes"}[spec.roof]
        if spec.has_truss:
            return (
                f"Warehouse {spec.width:g} x {spec.length:g}: {spec.n_frames} trussed frames at "
                f"{spec.frame_spacing:g}, {spec.n_naves} nave(s) of {spec.span:g}, eave "
                f"{spec.eave_height:g}, ridge {spec.ridge_height:g} ({roof}, "
                f"{spec.slope * 100:g} %), truss depth {spec.truss_depth:g} - "
                f"{len(self.members['columns'])} column, "
                f"{len(self.members['top_chords']) + len(self.members['bottom_chords'])} chord, "
                f"{len(self.members['truss_webs'])} web, "
                f"{len(self.members['purlins'])} purlin, {len(self.members['girts'])} girt, "
                f"{len(self.members['chord_ties'])} tie, "
                f"{len(self.members['end_columns'])} end wall column and "
                f"{sum(len(self.members[g]) for g in BRACING_GROUPS)} bracing "
                f"elements, {len(self.nodes)} nodes."
            )
        return (
            f"Warehouse {spec.width:g} x {spec.length:g}: {spec.n_frames} frames at "
            f"{spec.frame_spacing:g}, {spec.n_naves} nave(s) of {spec.span:g}, eave "
            f"{spec.eave_height:g}, ridge {spec.ridge_height:g} ({roof}, "
            f"{spec.slope * 100:g} %) - {len(self.members['columns'])} column, "
            f"{len(self.members['rafters'])} rafter, {len(self.members['purlins'])} purlin, "
            f"{len(self.members['girts'])} girt, "
            f"{len(self.members['end_columns'])} end wall column and "
            f"{len(self.members['roof_bracing']) + len(self.members['wall_bracing'])} bracing "
            f"elements, {len(self.nodes)} nodes."
        )


def roof_stations(spec: WarehouseSpec) -> list[RoofStation]:
    """The purlin lines of ``spec``, from the left eave to the right one.

    Each stretch of roof between two breaks (column lines, the ridge) is divided
    into equal parts no longer than the purlin spacing, measured on the slope.
    """
    profile = spec.profile
    breaks = spec.roof_breaks()
    xs: list[float] = [breaks[0]]
    braced: list[bool] = [True]
    for a, b in itertools.pairwise(breaks):
        length = math.hypot(b - a, profile.roof_height(b) - profile.roof_height(a))
        count = max(1, math.ceil(length / spec.purlin_spacing - 1e-9))
        flags = _fly_braced(count, spec.rafter_fly_brace_every)
        for k in range(1, count + 1):
            xs.append(b if k == count else a + k * (b - a) / count)
            braced.append(flags[k])
    zs = [profile.roof_height(x) for x in xs]

    stations: list[RoofStation] = []
    last = len(xs) - 1
    for k, (x, z) in enumerate(zip(xs, zs, strict=True)):
        slope_width = plan_width = 0.0
        normal = np.zeros(3)
        for other in (k - 1, k + 1):
            if not 0 <= other <= last:
                continue
            dx, dz = xs[other] - x, zs[other] - z
            run = math.hypot(dx, dz)
            slope_width += run / 2.0
            plan_width += abs(dx) / 2.0
            # Upward normal of this stretch of roof (the roof line lies in X-Z).
            normal += np.array([-dz, 0.0, dx]) / run * (1.0 if dx > 0.0 else -1.0)
        # A purlin runs along +Y, so its local z is Z turned about Y by the
        # element angle: (sin a, 0, cos a). At the ridge the two normals average
        # to the vertical and the web stands plumb.
        angle = portable(math.degrees(math.atan2(normal[0], normal[2])))
        stations.append(
            RoofStation(
                x=x,
                z=z,
                tributary_slope=slope_width,
                tributary_plan=plan_width,
                angle=0.0 if abs(angle) < 1e-9 else angle,
                fly_braced=braced[k],
            )
        )
    return stations


@dataclass(frozen=True)
class EndWall:
    """The verticals of an end wall, left to right, and the girt lines each carries."""

    xs: tuple[float, ...]
    tops: tuple[float, ...]
    posts: dict[int, int]
    """Vertical index -> roof station index, for the end wall columns (not the frame's own)."""
    levels: tuple[tuple[float, ...], ...]
    """Per vertical: the elevation of each girt line that reaches it."""

    def panel_levels(self, vertical: int) -> list[float]:
        """Girt lines of the panel between ``vertical`` and the next one."""
        return [z for z in self.levels[vertical] if z in self.levels[vertical + 1]]

    def roof_area(self, a: float, b: float, profile: PortalFrameSpec) -> float:
        """Wall area between ``a`` and ``b``, from the base to the roof line."""
        cuts = [a, *[x for x in self.xs if a < x < b], b]
        ridge = profile.span / 2.0
        if profile.roof is RoofType.GABLE and a < ridge < b:
            cuts = sorted({*cuts, ridge})
        return sum(
            (x1 - x0) * 0.5 * (profile.roof_height(x0) + profile.roof_height(x1))
            for x0, x1 in itertools.pairwise(cuts)
        )


def end_wall_layout(spec: WarehouseSpec, stations: list[RoofStation] | None = None) -> EndWall:
    """Where the verticals of an end wall stand and which girt lines reach them.

    The frame's own columns always are verticals. Each nave is divided into
    equal parts no longer than the end wall column spacing, and each end wall
    column goes under the purlin line nearest to its place. A girt line exists
    between two verticals when both reach it with some clearance below the
    rafter.
    """
    stations = roof_stations(spec) if stations is None else stations
    profile = spec.profile
    column_xs = spec.column_lines()
    post_station: dict[float, int] = {}
    if spec.end_wall_column_spacing > 0.0:
        for a, b in itertools.pairwise(column_xs):
            count = max(1, math.ceil((b - a) / spec.end_wall_column_spacing - 1e-9))
            inside = [
                k for k, s in enumerate(stations) if a + GRID_TOLERANCE < s.x < b - GRID_TOLERANCE
            ]
            for j in range(1, count):
                if not inside:
                    break
                ideal = a + j * (b - a) / count
                centre = (a + b) / 2.0
                # Nearest purlin line; of two as near, the one towards mid-nave,
                # so a symmetric nave gets symmetric columns.
                k = min(
                    inside,
                    key=lambda i: (
                        round(abs(stations[i].x - ideal), 9),
                        abs(stations[i].x - centre),
                    ),
                )
                post_station[stations[k].x] = k
    xs = _distinct([*column_xs, *post_station])
    tops = [profile.roof_height(x) for x in xs]
    posts = {
        v: k
        for v, x in enumerate(xs)
        for px, k in post_station.items()
        if abs(px - x) <= GRID_TOLERANCE
    }
    all_levels = spec.end_wall_levels()
    side = spec.girt_heights()
    clearance = END_GIRT_CLEARANCE * (side[0] if side else spec.eave_height)
    last = len(xs) - 1

    def reaches(v: int, z: float) -> bool:
        return 0 <= v <= last and z <= tops[v] - clearance + 1e-9

    levels: list[tuple[float, ...]] = []
    for v in range(len(xs)):
        if not all_levels:
            levels.append(())
        elif v in (0, last):
            # A corner column carries the side wall's girt lines, all of them.
            levels.append(tuple(side))
        else:
            levels.append(
                tuple(
                    z
                    for z in all_levels
                    if reaches(v, z) and (reaches(v - 1, z) or reaches(v + 1, z))
                )
            )
    return EndWall(xs=tuple(xs), tops=tuple(tops), posts=posts, levels=tuple(levels))


def _base_restraint(support: SupportCondition) -> Restraint6:
    fixed = support is SupportCondition.FIXED
    return (True, True, True, fixed, fixed, fixed)


_FREE: Restraint6 = (False, False, False, False, False, False)


def build_warehouse(
    spec: WarehouseSpec,
    sections: Mapping[str, int],
    *,
    first_node_id: int,
    first_element_id: int,
) -> Warehouse:
    """Build the nodes and elements of ``spec``.

    ``sections`` maps every key of :data:`SECTION_KEYS` to a section id. Ids are
    allocated from ``first_node_id`` / ``first_element_id`` upwards.
    """
    missing = [key for key in spec.section_keys() if int(sections.get(key, 0) or 0) < 1]
    if missing:
        raise WarehouseError("No section for: " + ", ".join(missing) + ".")
    ox, oy, oz = spec.origin
    stations = roof_stations(spec)
    column_xs = spec.column_lines()
    girt_zs = spec.girt_heights()
    side_lines = (0, len(column_xs) - 1)

    nodes: list[Node] = []
    elements: list[ElasticBeamColumn] = []
    members: dict[str, list[int]] = {key: [] for key in GROUPS}
    counters = {"node": first_node_id, "element": first_element_id}

    def add_node(x: float, y: float, z: float, restraint: Restraint6 = _FREE) -> int:
        node_id = counters["node"]
        counters["node"] += 1
        nodes.append(Node(id=node_id, coords=(ox + x, oy + y, oz + z), restraint=restraint))
        return node_id

    def add_element(
        group: str,
        i: int,
        j: int,
        section: str,
        *,
        releases: FrameReleases | None = None,
        angle: float = 0.0,
    ) -> int:
        element_id = counters["element"]
        counters["element"] += 1
        extra: dict[str, Any] = {}
        if releases is not None:
            extra["releases"] = releases
        if angle:
            extra["local_axis_angle"] = angle
        elements.append(
            ElasticBeamColumn(
                id=element_id, nodes=(i, j), section_id=int(sections[section]), **extra
            )
        )
        members[group].append(element_id)
        return element_id

    def station_at(x: float) -> int:
        return next(k for k, s in enumerate(stations) if abs(s.x - x) <= GRID_TOLERANCE)

    warehouse = Warehouse(
        spec=spec, nodes=nodes, elements=elements, members=members, stations=stations
    )

    truss = spec.has_truss
    roof_nodes: list[list[int]] = []  # [frame][station]
    chord_nodes: list[list[int]] = []  # [frame][station], the bottom chord of a truss
    chord_zs = [spec.bottom_chord_height(s.x) for s in stations] if truss else []
    wall_nodes: list[dict[int, list[int]]] = []  # [frame][side line] -> base, girts..., eave
    rafter_lengths = _unbraced_lengths(
        _cumulative([(s.x, s.z) for s in stations]), [s.fly_braced for s in stations]
    )
    end_wall = end_wall_layout(spec, stations)
    end_frames = (0, spec.n_frames - 1)
    end_vertical = {
        line: next(v for v, ex in enumerate(end_wall.xs) if abs(ex - x) <= GRID_TOLERANCE)
        for line, x in enumerate(column_xs)
    }
    end_chains: dict[tuple[int, int], list[int]] = {}  # (frame, vertical) -> base, girts..., top
    for wall in ("x0", "x1", "y0", "y1"):
        warehouse.wall_columns[wall] = []

    def add_vertical(
        group: str,
        section: str,
        place: tuple[float, float],
        levels: Sequence[float],
        top: tuple[int, float],
        restraint: Restraint6,
        *,
        chord: tuple[float, int | None] | None = None,
        angle: float = 0.0,
        top_releases: FrameReleases | None = None,
    ) -> tuple[list[int], list[int], int | None]:
        """A column from the base at ``place`` to the roof node ``top`` (node, elevation).

        ``levels`` are the girt lines it carries; ``chord`` is the elevation at
        which the bottom chord of a truss meets it, and the chord's node when it
        exists already. Returns the element ids, the nodes ``base, girt
        lines..., top`` and the chord node. A girt braces the column only with
        a stabilising angle; the bottom chord, tied from frame to frame, does.
        """
        x, y = place
        base = add_node(x, y, 0.0, restraint)
        warehouse.base_node_ids.append(base)
        fly = _fly_braced(len(levels) + 1, spec.column_fly_brace_every)
        points: list[tuple[float, int, bool]] = [(0.0, base, True)]
        girt_chain = [base]
        chord_node: int | None = None
        waiting = chord

        def meet_chord() -> int:
            assert waiting is not None
            return waiting[1] if waiting[1] is not None else add_node(x, y, waiting[0])

        for k, z in enumerate(levels, start=1):
            if waiting is not None and waiting[0] < z - GRID_TOLERANCE:
                chord_node = meet_chord()
                points.append((waiting[0], chord_node, True))
                waiting = None
            if waiting is not None and abs(waiting[0] - z) <= GRID_TOLERANCE:
                chord_node = node = meet_chord()
                points.append((z, node, True))
                waiting = None
            else:
                node = add_node(x, y, z)
                points.append((z, node, fly[k]))
            girt_chain.append(node)
        if waiting is not None:
            chord_node = meet_chord()
            points.append((waiting[0], chord_node, True))
        points.append((top[1], top[0], True))
        girt_chain.append(top[0])
        lengths = _unbraced_lengths([p[0] for p in points], [p[2] for p in points])
        ids: list[int] = []
        for k, (a, b) in enumerate(itertools.pairwise(points)):
            releases = top_releases if k == len(points) - 2 else None
            element_id = add_element(group, a[1], b[1], section, releases=releases, angle=angle)
            if levels or chord is not None:
                warehouse.unbraced[element_id] = lengths[k]
            ids.append(element_id)
        return ids, girt_chain, chord_node

    post_stations = set(end_wall.posts.values())
    for frame in range(spec.n_frames):
        y = frame * spec.frame_spacing
        tops = [add_node(s.x, y, s.z) for s in stations]
        roof_nodes.append(tops)
        walls: dict[int, list[int]] = {}
        under: dict[int, int] = {}  # station -> bottom chord node
        for line, x in enumerate(column_xs):
            at = station_at(x)
            levels: Sequence[float] = ()
            if line in side_lines:
                levels = girt_zs
            elif frame in end_frames:
                levels = end_wall.levels[end_vertical[line]]
            ids, chain, chord_node = add_vertical(
                "columns",
                "column",
                (x, y),
                levels,
                (tops[at], stations[at].z),
                _base_restraint(spec.support),
                chord=(chord_zs[at], None) if truss else None,
            )
            if chord_node is not None:
                under[at] = chord_node
            if line in side_lines:
                walls[line] = chain
                wall = "x0" if line == side_lines[0] else "x1"
                warehouse.wall_columns[wall] += [(i, frame) for i in ids]
            if frame in end_frames:
                end_chains[(frame, end_vertical[line])] = chain
                wall = "y0" if frame == 0 else "y1"
                warehouse.wall_columns[wall] += [(i, end_vertical[line]) for i in ids]
        wall_nodes.append(walls)
        if not truss:
            rafters: list[int] = []
            for k, (a, b) in enumerate(itertools.pairwise(tops)):
                element_id = add_element("rafters", a, b, "rafter")
                warehouse.unbraced[element_id] = rafter_lengths[k]
                rafters.append(element_id)
            warehouse.rafter_elements.append(rafters)
            continue
        bottoms = [
            under[k] if k in under else add_node(s.x, y, chord_zs[k])
            for k, s in enumerate(stations)
        ]
        chord_nodes.append(bottoms)
        warehouse.rafter_elements.append(
            [add_element("top_chords", a, b, "top_chord") for a, b in itertools.pairwise(tops)]
        )
        warehouse.bottom_chord_elements.append(
            [
                add_element("bottom_chords", a, b, "bottom_chord")
                for a, b in itertools.pairwise(bottoms)
            ]
        )
        for k in range(len(stations)):
            # A column is the vertical at its line, and so is an end wall column.
            if k in under or (frame in end_frames and k in post_stations):
                continue
            add_element("truss_webs", bottoms[k], tops[k], "truss_web", releases=BRACE_RELEASES)
        for k, rising in enumerate(_truss_diagonals(spec, stations)):
            a, b = (bottoms[k], tops[k + 1]) if rising else (tops[k], bottoms[k + 1])
            add_element("truss_webs", a, b, "truss_web", releases=BRACE_RELEASES)

    for bay in range(spec.n_bays):
        near, far = roof_nodes[bay], roof_nodes[bay + 1]
        for k, station in enumerate(stations):
            element_id = add_element(
                "purlins", near[k], far[k], "purlin",
                releases=SECONDARY_RELEASES, angle=station.angle,
            )  # fmt: skip
            warehouse.purlin_station[element_id] = k
        for side, line in enumerate(side_lines):
            # A girt's web lies flat, to span the wall against the wind.
            angle = 90.0 if side == 0 else -90.0
            for level in range(1, len(girt_zs) + 1):
                element_id = add_element(
                    "girts",
                    wall_nodes[bay][line][level],
                    wall_nodes[bay + 1][line][level],
                    "girt",
                    releases=SECONDARY_RELEASES,
                    angle=angle,
                )
                warehouse.wall_girts[element_id] = (
                    "x0" if side == 0 else "x1", bay, girt_zs[level - 1]
                )  # fmt: skip

    for bay in spec.bracing_bays():
        if spec.roof_bracing:
            for a, b in _bracing_panels(spec, stations):
                near, far = roof_nodes[bay], roof_nodes[bay + 1]
                add_element("roof_bracing", near[a], far[b], "brace", releases=BRACE_RELEASES)
                add_element("roof_bracing", near[b], far[a], "brace", releases=BRACE_RELEASES)
        if spec.wall_bracing:
            for line in dict.fromkeys(side_lines):
                near_wall, far_wall = wall_nodes[bay][line], wall_nodes[bay + 1][line]
                add_element(
                    "wall_bracing", near_wall[0], far_wall[-1], "brace", releases=BRACE_RELEASES
                )
                add_element(
                    "wall_bracing", near_wall[-1], far_wall[0], "brace", releases=BRACE_RELEASES
                )

    if truss:
        tied = bottom_chord_ties(spec, stations)
        along = _cumulative(list(zip([s.x for s in stations], chord_zs, strict=True)))
        for frame_chord in warehouse.bottom_chord_elements:
            for element_id, length in zip(frame_chord, _unbraced_lengths(along, tied), strict=True):
                warehouse.unbraced[element_id] = length
        tie_lines = [k for k, flag in enumerate(tied) if flag]
        side_stations = {station_at(column_xs[line]) for line in side_lines}
        # A girt line at the level of the bottom chord is the tie of that wall.
        girt_ties = {
            k for k in side_stations if any(abs(z - chord_zs[k]) <= GRID_TOLERANCE for z in girt_zs)
        }
        for bay in range(spec.n_bays):
            for k in tie_lines:
                if k in girt_ties:
                    continue
                add_element(
                    "chord_ties",
                    chord_nodes[bay][k],
                    chord_nodes[bay + 1][k],
                    "chord_tie",
                    releases=SECONDARY_RELEASES,
                )
        # In the braced bays a vertical X takes each tie line up to the roof
        # bracing; at the side walls the wall bracing does that.
        for bay in spec.bracing_bays() if spec.roof_bracing else ():
            for k in tie_lines:
                if k in side_stations:
                    continue
                for a, b in (
                    (chord_nodes[bay][k], roof_nodes[bay + 1][k]),
                    (roof_nodes[bay][k], chord_nodes[bay + 1][k]),
                ):
                    add_element("sway_bracing", a, b, "brace", releases=BRACE_RELEASES)

    # End walls last, so a warehouse without them keeps the ids it always had.
    pinned_base: Restraint6 = (True, True, True, False, False, False)
    for frame in dict.fromkeys(end_frames):
        y = frame * spec.frame_spacing
        wall = "y0" if frame == 0 else "y1"
        for vertical, station_index in end_wall.posts.items():
            # The web along Y, to span the wall against the wind. Under a truss
            # the column passes through the bottom chord and is its vertical.
            ids, chain, _chord = add_vertical(
                "end_columns",
                "end_column",
                (end_wall.xs[vertical], y),
                end_wall.levels[vertical],
                (roof_nodes[frame][station_index], end_wall.tops[vertical]),
                pinned_base,
                chord=(chord_zs[station_index], chord_nodes[frame][station_index])
                if truss
                else None,
                angle=90.0,
                top_releases=POST_TOP_RELEASES,
            )
            end_chains[(frame, vertical)] = chain
            warehouse.wall_columns[wall] += [(i, vertical) for i in ids]
        for vertical in range(len(end_wall.xs) - 1):
            first, last = (station_at(end_wall.xs[v]) for v in (vertical, vertical + 1))
            for z in end_wall.panel_levels(vertical):
                if truss and all(
                    abs(chord_zs[k] - z) <= GRID_TOLERANCE for k in range(first, last + 1)
                ):
                    # The bottom chord lies on this girt line: it carries the cladding.
                    for element_id in warehouse.bottom_chord_elements[frame][first:last]:
                        warehouse.wall_girts[element_id] = (wall, vertical, z)
                    continue
                left = end_chains[(frame, vertical)][end_wall.levels[vertical].index(z) + 1]
                right = end_chains[(frame, vertical + 1)][
                    end_wall.levels[vertical + 1].index(z) + 1
                ]
                element_id = add_element(
                    "girts", left, right, "girt", releases=SECONDARY_RELEASES, angle=90.0
                )
                warehouse.wall_girts[element_id] = (wall, vertical, z)
    return warehouse


def _truss_diagonals(spec: WarehouseSpec, stations: list[RoofStation]) -> list[bool]:
    """Per truss panel (between consecutive stations): the diagonal rises to the right.

    A Pratt diagonal runs down towards the middle of its nave, a Howe diagonal
    up towards it; a Warren web alternates from each column line.
    """
    rising: list[bool] = []
    count = 0
    nave = -1
    for a, b in itertools.pairwise(stations):
        centre = (a.x + b.x) / 2.0
        here = min(spec.n_naves - 1, int(centre // spec.span))
        if here != nave:
            nave, count = here, 0
        left_half = centre <= (nave + 0.5) * spec.span + GRID_TOLERANCE
        if spec.truss_type is TrussType.PRATT:
            rising.append(not left_half)
        elif spec.truss_type is TrussType.HOWE:
            rising.append(left_half)
        else:
            rising.append(count % 2 == 1)
        count += 1
    return rising


def _cumulative(points: list[tuple[float, float]]) -> list[float]:
    """Distance of each point from the first along the polyline."""
    out = [0.0]
    for (x0, z0), (x1, z1) in itertools.pairwise(points):
        out.append(out[-1] + math.hypot(x1 - x0, z1 - z0))
    return out


def _bracing_panels(spec: WarehouseSpec, stations: list[RoofStation]) -> list[tuple[int, int]]:
    """Station index pairs ``(a, b)`` of each roof bracing panel.

    Each stretch of roof between two breaks is cut into panels about as long as
    the bay, on purlin lines, so the diagonals stay near 45 degrees.
    """
    breaks = spec.roof_breaks()
    index = {
        b: next(k for k, s in enumerate(stations) if abs(s.x - b) <= GRID_TOLERANCE) for b in breaks
    }
    along = _cumulative([(s.x, s.z) for s in stations])
    panels: list[tuple[int, int]] = []
    for a, b in itertools.pairwise(breaks):
        first, last = index[a], index[b]
        count = last - first
        wanted = max(1, min(count, round((along[last] - along[first]) / spec.frame_spacing)))
        cuts = sorted({first + round(j * count / wanted) for j in range(wanted + 1)})
        panels += list(itertools.pairwise(cuts))
    return panels


# ─────────────────────────── grid and groups ───────────────────────────
def warehouse_grid(spec: WarehouseSpec, *, name: str = "Warehouse") -> CoordinateGridSystem:
    """A grid on the column lines, the frames, and the base, eave and ridge levels."""
    xs = spec.roof_breaks()
    ys = [k * spec.frame_spacing for k in range(spec.n_frames)]
    zs = _distinct([0.0, spec.eave_height, spec.ridge_height, *spec.profile.column_heights()])
    return CoordinateGridSystem(
        name=name,
        coord=CoordinateSystem(origin=spec.origin),
        grid=GridSystem(
            x_grid_lines=make_grid_lines("X", xs),
            y_grid_lines=make_grid_lines("Y", ys),
            z_grid_lines=make_grid_lines("Z", zs),
        ),
    )


# ─────────────────────────────── loads ───────────────────────────────
def _gravity_components(nodes: Mapping[int, Node], element: ElasticBeamColumn) -> np.ndarray:
    """Local ``(x, y, z)`` components of a unit downward (-Z) load on ``element``."""
    axes = frame_local_axes(
        3,
        nodes[element.nodes[0]].coords,
        nodes[element.nodes[1]].coords,
        element.local_axis_angle,
    )
    assert axes is not None  # a warehouse has no zero-length member
    return np.array([-float(axis[2]) for axis in axes])


def roof_pressure_loads(warehouse: Warehouse, pressure: float, *, projected: bool) -> list[Any]:
    """A downward load per roof area as uniform loads on the purlins.

    ``projected`` reads ``pressure`` per area of horizontal projection (a live
    load); otherwise per area of roof surface (the weight of the cladding).
    """
    from opensees_studio.core.loads import UniformElementLoad

    if pressure == 0.0:
        return []
    nodes = {n.id: n for n in warehouse.nodes}
    purlins = {e.id: e for e in warehouse.elements if e.id in warehouse.purlin_station}
    loads: list[Any] = []
    for element_id, k in warehouse.purlin_station.items():
        station = warehouse.stations[k]
        width = station.tributary_plan if projected else station.tributary_slope
        _wx, wy, wz = _components(
            _gravity_components(nodes, purlins[element_id]) * pressure * width
        )
        loads.append(UniformElementLoad(element_id=element_id, wy=wy, wz=wz))
    return loads


def midspan_point_loads(warehouse: Warehouse, force: float) -> tuple[list[Any], list[Any]]:
    """A downward force at mid-span of every nave of every frame.

    Returns ``(nodal loads, point element loads)``: the force goes on the node
    when a purlin line falls at mid-span (the ridge of a single-nave gable) and
    inside the rafter element otherwise.
    """
    from opensees_studio.core.loads import NodalLoad, PointElementLoad

    if force == 0.0:
        return [], []
    spec = warehouse.spec
    stations = warehouse.stations
    nodes = {n.id: n for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    nodal: list[Any] = []
    inside: list[Any] = []
    for rafters in warehouse.rafter_elements:
        for nave in range(spec.n_naves):
            x = (nave + 0.5) * spec.span
            at = next((k for k, s in enumerate(stations) if abs(s.x - x) <= GRID_TOLERANCE), None)
            if at is not None:
                # Either element at the station shares the node: its end there.
                element = elements[rafters[min(at, len(rafters) - 1)]]
                node_id = element.nodes[0] if at < len(rafters) else element.nodes[1]
                nodal.append(NodalLoad(node_id=node_id, forces=(0.0, 0.0, -force, 0.0, 0.0, 0.0)))
                continue
            k = max(i for i, s in enumerate(stations) if s.x < x)
            element = elements[rafters[k]]
            px, py, pz = _components(_gravity_components(nodes, element) * force)
            inside.append(
                PointElementLoad(
                    element_id=element.id,
                    px=px,
                    py=py,
                    pz=pz,
                    x=(x - stations[k].x) / (stations[k + 1].x - stations[k].x),
                )
            )
    return nodal, inside


# ─────────────────────────────── wind ───────────────────────────────
#: The wind procedures the wizard offers.
WIND_METHODS: dict[str, str] = {
    "rnc07": "RNC-07 Título IV",
    "asce7": "ASCE 7-16 chapter 27",
    "en1991": "EN 1991-1-4",
}


@dataclass(frozen=True)
class WarehouseWind:
    """The wind on the warehouse. Speeds are in m/s whatever the project's units."""

    method: str = "rnc07"
    speed: float = 45.0
    """RNC-07: the regional velocity VR. ASCE 7: the basic wind speed V. EN 1991-1-4:
    the basic wind velocity vb."""
    exposure: str = "R2"
    """RNC-07: terrain roughness R1 to R4. ASCE 7: exposure category B, C or D.
    EN 1991-1-4: terrain category 0, I, II, III or IV."""
    topography: str = "T3"
    """RNC-07 only: T1 to T5."""
    topographic_factor: float = 1.0
    """Kzt of ASCE 7, or the orography factor co of EN 1991-1-4."""
    openings: str = "closed"
    """``closed``, ``uniform`` (spread over the four walls) or the wall with the openings."""
    directions: tuple[str, ...] = DIRECTIONS

    def __post_init__(self) -> None:
        if self.method not in WIND_METHODS:
            raise WarehouseError(f"Unknown wind procedure {self.method!r}.")
        if self.speed <= 0.0:
            raise WarehouseError("The wind speed must be positive.")
        if self.topographic_factor <= 0.0:
            raise WarehouseError("The topographic factor must be positive.")
        if self.openings not in OPENINGS:
            raise WarehouseError(f"Unknown openings {self.openings!r}.")
        if not self.directions or any(d not in DIRECTIONS for d in self.directions):
            raise WarehouseError("Choose at least one wind direction: +X, -X, +Y or -Y.")


def building_shape(spec: WarehouseSpec, units: UnitSystem) -> BuildingShape:
    """``spec`` as the box the wind sees, in metres."""
    metres = length_scale(units, UnitSystem.SI_M_N)
    roof = {RoofType.MONO_PITCH: "mono", RoofType.GABLE: "gable"}.get(spec.roof, "flat")
    return BuildingShape(
        width=spec.width * metres,
        length=spec.length * metres,
        eave_height=spec.eave_height * metres,
        roof=roof,
        slope=spec.slope,
    )


def warehouse_wind_cases(
    spec: WarehouseSpec, wind: WarehouseWind, units: UnitSystem
) -> list[WindCase]:
    """The wind cases of ``wind`` on ``spec``: net pressures in N/m² against metres."""
    shape = building_shape(spec, units)
    directions = [d for d in DIRECTIONS if d in wind.directions]
    try:
        if wind.method == "asce7":
            return asce7_wind_cases(
                shape,
                speed=wind.speed,
                exposure=wind.exposure,
                kzt=wind.topographic_factor,
                openings=wind.openings,
                directions=directions,
            )
        if wind.method == "en1991":
            return en1991_wind_cases(
                shape,
                speed=wind.speed,
                terrain=wind.exposure,
                orography=wind.topographic_factor,
                openings=wind.openings,
                directions=directions,
            )
        return rnc07_wind_cases(
            shape,
            regional_speed=wind.speed,
            roughness=wind.exposure,
            topography=wind.topography,
            openings=wind.openings,
            directions=directions,
        )
    except WindError as exc:
        raise WarehouseError(str(exc)) from exc


def wind_loads(warehouse: Warehouse, case: WindCase, units: UnitSystem) -> list[Any]:
    """One wind case as uniform loads on the members the cladding hangs from.

    * Roof: each purlin takes half the strip to each neighbour, normal to that
      strip of roof.
    * A wall with girts: each girt takes half the strip to the line below and
      above; the top half strip goes to the eave purlin (side walls) or to the
      rafter (end walls), the bottom half strip into the ground.
    * A wall without girts: each column takes the wall half way to its
      neighbours, over its whole height.

    A positive pressure of ``case`` pushes the surface inwards. The loads are in
    each element's local axes and in the project's units; an element loaded
    from two surfaces (a corner column, the ridge purlin) gets one load.
    """
    from opensees_studio.core.loads import UniformElementLoad

    spec = warehouse.spec
    stations = warehouse.stations
    profile = spec.profile
    metres = length_scale(units, UnitSystem.SI_M_N)
    pascal = pressure_from_kpa(1e-3, units)
    origin = np.array(spec.origin, dtype=float)
    nodes = {n.id: n for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    forces: dict[int, np.ndarray] = {}

    def local(node_id: int) -> np.ndarray:
        out: np.ndarray = np.array(nodes[node_id].coords, dtype=float) - origin
        return out

    def add(element_id: int, pressure: float, width: float, outward: np.ndarray) -> None:
        """``pressure`` (N/m²) over ``width`` of surface per length of the element."""
        forces[element_id] = forces.get(element_id, np.zeros(3)) - (
            pressure * pascal * width * outward
        )

    def mean(pressure: Any, a: float, b: float) -> float:
        return float(pressure.mean(a * metres, b * metres))

    def on_wall(wall: str, a: float, b: float, lo: float, hi: float) -> float:
        """Mean pressure on ``wall`` from ``a`` to ``b`` along it, ``lo`` to ``hi`` in height."""
        zones = case.wall_zones.get(wall)
        if zones is None:
            return mean(case.walls[wall], lo, hi)
        return float(zones.mean(a * metres, b * metres, lo * metres, hi * metres))

    # Roof: half strips either side of each purlin line.
    last = len(stations) - 1
    for element_id, k in warehouse.purlin_station.items():
        here = stations[k]
        ya, yb = (local(n)[1] for n in elements[element_id].nodes)
        for other in (k - 1, k + 1):
            if not 0 <= other <= last:
                continue
            dx, dz = stations[other].x - here.x, stations[other].z - here.z
            run = math.hypot(dx, dz)
            outward = np.array([-dz, 0.0, dx]) / run * (1.0 if dx > 0.0 else -1.0)
            middle = here.x + dx / 2.0
            load = case.roof_load_at((here.x + middle) / 2.0 * metres)
            if load.zones is not None:
                value = float(
                    load.zones.mean(here.x * metres, middle * metres, ya * metres, yb * metres)
                )
            elif load.axis == "x":
                value = mean(load.profile, here.x, middle)
            else:
                value = mean(load.profile, ya, yb)
            add(element_id, value, run / 2.0, outward)

    # Side walls.
    girt_zs = spec.girt_heights()
    for wall, station, outward in (
        ("x0", 0, np.array([-1.0, 0.0, 0.0])),
        ("x1", last, np.array([1.0, 0.0, 0.0])),
    ):
        levels = [0.0, *girt_zs, stations[station].z]
        if girt_zs:
            for element_id, (girt_wall, _bay, z) in warehouse.wall_girts.items():
                if girt_wall != wall:
                    continue
                k = levels.index(z)
                lo, hi = (levels[k - 1] + z) / 2.0, (z + levels[k + 1]) / 2.0
                ya, yb = (local(n)[1] for n in elements[element_id].nodes)
                add(element_id, on_wall(wall, ya, yb, lo, hi), hi - lo, outward)
            lo, hi = (levels[-2] + levels[-1]) / 2.0, levels[-1]
            for element_id, k in warehouse.purlin_station.items():
                if k == station:
                    ya, yb = (local(n)[1] for n in elements[element_id].nodes)
                    add(element_id, on_wall(wall, ya, yb, lo, hi), hi - lo, outward)
        else:
            for element_id, frame in warehouse.wall_columns[wall]:
                y = frame * spec.frame_spacing
                ya = max(0.0, y - spec.frame_spacing / 2.0)
                yb = min(spec.length, y + spec.frame_spacing / 2.0)
                za, zb = (local(n)[2] for n in elements[element_id].nodes)
                add(element_id, on_wall(wall, ya, yb, za, zb), yb - ya, outward)

    # End walls.
    end_wall = end_wall_layout(spec, stations)
    framed = any(end_wall.levels)
    for wall, frame, outward in (
        ("y0", 0, np.array([0.0, -1.0, 0.0])),
        ("y1", spec.n_frames - 1, np.array([0.0, 1.0, 0.0])),
    ):
        if not framed:
            for element_id, vertical in warehouse.wall_columns[wall]:
                x = end_wall.xs[vertical]
                left = (end_wall.xs[vertical - 1] + x) / 2.0 if vertical else x
                right = (
                    (x + end_wall.xs[vertical + 1]) / 2.0 if vertical < len(end_wall.xs) - 1 else x
                )
                # The wall up to the roof line, spread over the column's height.
                width = end_wall.roof_area(left, right, profile) / end_wall.tops[vertical]
                za, zb = (local(n)[2] for n in elements[element_id].nodes)
                add(element_id, on_wall(wall, left, right, za, zb), width, outward)
            continue
        top_girt: dict[int, float] = {}
        for vertical in range(len(end_wall.xs) - 1):
            a, b = end_wall.xs[vertical], end_wall.xs[vertical + 1]
            roof = end_wall.roof_area(a, b, profile) / (b - a)
            levels = [0.0, *end_wall.panel_levels(vertical), roof]
            top_girt[vertical] = levels[-2]
            for element_id, (girt_wall, panel, z) in warehouse.wall_girts.items():
                if girt_wall != wall or panel != vertical:
                    continue
                k = levels.index(z)
                lo, hi = (levels[k - 1] + z) / 2.0, (z + levels[k + 1]) / 2.0
                add(element_id, on_wall(wall, a, b, lo, hi), hi - lo, outward)
        # The strip under the roof line hangs from the rafter of the end frame.
        for k, element_id in enumerate(warehouse.rafter_elements[frame]):
            s0, s1 = stations[k], stations[k + 1]
            middle = (s0.x + s1.x) / 2.0
            vertical = max(v for v, x in enumerate(end_wall.xs[:-1]) if x <= middle)
            roof = (s0.z + s1.z) / 2.0
            height = (roof - top_girt[vertical]) / 2.0
            width = height * abs(s1.x - s0.x) / math.hypot(s1.x - s0.x, s1.z - s0.z)
            add(element_id, on_wall(wall, s0.x, s1.x, roof - height, roof), width, outward)

    loads: list[Any] = []
    for element_id in sorted(forces):
        element = elements[element_id]
        axes = frame_local_axes(
            3,
            nodes[element.nodes[0]].coords,
            nodes[element.nodes[1]].coords,
            element.local_axis_angle,
        )
        assert axes is not None  # a warehouse has no zero-length member
        if not forces[element_id].any():
            continue
        wx, wy, wz = _components(axis @ forces[element_id] for axis in axes)
        loads.append(UniformElementLoad(element_id=element_id, wx=wx, wy=wy, wz=wz))
    return loads


# ─────────────────────────── design lengths ───────────────────────────
def member_design_overrides(warehouse: Warehouse) -> list[Any]:
    """Unbraced lengths of the rafters and side columns for the steel check.

    Minor-axis buckling and lateral-torsional buckling take the distance
    between bracing points: a purlin (or a girt) counts only where it has a
    stabilising angle. Major-axis buckling stays as modelled.
    """
    from opensees_studio.core.design.settings import SteelMemberDesign

    return [
        SteelMemberDesign(
            element_id=element_id, length_minor=portable(length), length_ltb=portable(length)
        )
        for element_id, length in sorted(warehouse.unbraced.items())
    ]


# ───────────────────────────── earthquake ─────────────────────────────
#: The static methods the wizard offers.
SEISMIC_METHODS: dict[str, str] = {
    "rnc07": "RNC-07 Art. 32",
    "nscm": "NSCM Managua 8.2.1",
    "asce7": "ASCE 7-16 12.8",
    "en1998": "EN 1998-1 4.3.3.2",
}

#: The directions an earthquake case can act in.
SEISMIC_DIRECTIONS: tuple[str, ...] = ("X", "Y")
#: Design codes whose combinations take each earthquake direction with 30 % of
#: the other: RNC-07 Art. 32 f (Efectos bidireccionales), NSCM and EN 1998-1
#: 4.3.3.5.1 (3).
ORTHOGONAL_RULE_CODES: tuple[str, ...] = ("rnc07", "nscm", "en1990")

#: EN 1998-1 Table 3.2: soil factor S of the Type 1 spectrum per ground type.
EN1998_SOIL_FACTORS: dict[str, float] = {"A": 1.0, "B": 1.2, "C": 1.15, "D": 1.35, "E": 1.4}
#: EN 1998-1 4.2.5 (5), Note: recommended importance factor per importance class.
EN1998_IMPORTANCE: dict[str, float] = {"I": 0.8, "II": 1.0, "III": 1.2, "IV": 1.4}


@dataclass(frozen=True)
class WarehouseSeismic:
    """The earthquake on a warehouse by the static method of a code.

    The coefficient is that of the plateau of the design spectrum: the period
    of the building is not used, which is on the safe side and what a
    single-storey building of this height takes anyway.
    """

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
    """Q of RNC-07, Ro of NSCM, R of ASCE 7 or the behaviour factor q of EN 1998-1."""
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

    def __post_init__(self) -> None:
        if self.method not in SEISMIC_METHODS:
            raise WarehouseError(f"Unknown seismic method {self.method!r}.")
        if self.reduction <= 0.0:
            raise WarehouseError("The seismic reduction factor must be positive.")
        if self.roof_live < 0.0:
            raise WarehouseError("Loads are entered as positive, downward values.")
        if not self.directions:
            raise WarehouseError("Choose at least one earthquake direction.")
        for direction in self.directions:
            if direction not in SEISMIC_DIRECTIONS:
                raise WarehouseError(f"Unknown earthquake direction {direction!r}.")


def seismic_coefficient(seismic: WarehouseSeismic) -> tuple[float, str]:
    """``c = V / W`` of the static method, and the clause it comes from.

    Raises:
        WarehouseError: when the code refuses the values (a soil that needs a
            site study, an Ro below 1, ...).
    """
    from opensees_studio.core import nscm
    from opensees_studio.core.equivalent_lateral import (
        ElfError,
        ElfParameters,
        asce7_cs,
        rnc07_coefficient,
    )

    try:
        if seismic.method == "rnc07":
            found = rnc07_coefficient(
                ElfParameters(
                    code="rnc07",
                    period=0.0,
                    sds=0.0,
                    sd1=0.0,
                    r=seismic.reduction,
                    a0=seismic.a0,
                    soil=seismic.soil,
                    importance_class=seismic.importance_class,
                    regularity=seismic.regularity,
                )
            )
            return found.c, f"RNC-07 {found.why}"
        if seismic.method == "nscm":
            site = nscm.NscmSite(
                a0=seismic.a0,
                site_class=seismic.soil,
                risk_category=seismic.importance_class or "II",
                r0=seismic.reduction,
            )
            _tb, tc, _td = site.corner_periods()
            cs, why = site.seismic_coefficient(tc)
            return cs, f"NSCM {why}"
        if seismic.method == "en1998":
            # Expression (3.14), the plateau of the design spectrum, with λ = 1
            # (4.3.3.2.2: a building of one storey) and ag = γI agR.
            if seismic.soil not in EN1998_SOIL_FACTORS:
                raise WarehouseError(
                    f"EN 1998-1 has ground types A to E, not {seismic.soil!r}: S1 and S2 "
                    "need a special study."
                )
            gamma = EN1998_IMPORTANCE[seismic.importance_class or "II"]
            soil_factor = EN1998_SOIL_FACTORS[seismic.soil]
            ag = gamma * seismic.a0
            return 2.5 * ag * soil_factor / seismic.reduction, (
                f"EN 1998-1 (3.14): Sd = 2.5 ag S / q, ag = {ag:.4g} g, S = {soil_factor:g}, "
                f"q = {seismic.reduction:g}"
            )
        if seismic.sds <= 0.0:
            raise WarehouseError("SDS must be positive.")
        cs, why = asce7_cs(
            ElfParameters(
                code="asce7_16",
                period=0.0,
                sds=seismic.sds,
                sd1=0.0,
                r=seismic.reduction,
                importance=seismic.importance,
            )
        )
        return cs, f"ASCE 7-16 {why}"
    except (ElfError, nscm.NscmError, KeyError) as exc:
        raise WarehouseError(str(exc)) from exc


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
        raise WarehouseError(str(exc)) from exc


def roof_weights(warehouse: Warehouse, pressure: float, *, projected: bool) -> dict[int, float]:
    """Node id -> weight of a roof load per area, half of each purlin's strip per end."""
    if pressure == 0.0:
        return {}
    nodes = {n.id: np.asarray(n.coords, dtype=float) for n in warehouse.nodes}
    elements = {e.id: e for e in warehouse.elements}
    out: dict[int, float] = {}
    for element_id, k in warehouse.purlin_station.items():
        station = warehouse.stations[k]
        width = station.tributary_plan if projected else station.tributary_slope
        i, j = elements[element_id].nodes
        half = 0.5 * pressure * width * float(np.linalg.norm(nodes[j] - nodes[i]))
        out[i] = out.get(i, 0.0) + half
        out[j] = out.get(j, 0.0) + half
    return out


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


# ───────────────────────────── snow and ash ─────────────────────────────
#: What can settle on the roof, by the rule that gives its load.
SNOW_METHODS: dict[str, str] = {
    "ash": "Volcanic ash (RNC-07 Art. 14, NSCM 7.3)",
    "asce7": "ASCE 7-16 chapter 7",
    "en1991": "EN 1991-1-3",
}


@dataclass(frozen=True)
class WarehouseSnow:
    """Snow or volcanic ash on the roof of a warehouse."""

    method: str = "ash"
    """Key of :data:`SNOW_METHODS`."""
    ground: float = 0.0
    """A load per area of plan, in project units: the ash itself, the ground
    snow load ``pg`` of ASCE 7 or the characteristic ``sk`` of EN 1991-1-3."""
    exposure: float = 1.0
    """Exposure factor Ce (ASCE 7 Table 7.3-1, EN 1991-1-3 Table 5.1)."""
    thermal: float = 1.0
    """Thermal factor Ct."""
    importance: float = 1.0
    """ASCE 7: snow importance factor Is."""
    slippery: bool = False
    """ASCE 7: an unobstructed slippery roof, which sheds snow at a lower slope."""
    unbalanced: bool = True
    """Also the drifted arrangements the code asks for on this roof."""

    def __post_init__(self) -> None:
        if self.method not in SNOW_METHODS:
            raise WarehouseError(f"Unknown snow method {self.method!r}.")
        if self.ground < 0.0:
            raise WarehouseError("Loads are entered as positive, downward values.")
        if min(self.exposure, self.thermal, self.importance) <= 0.0:
            raise WarehouseError("The snow factors Ce, Ct and Is must be positive.")


def warehouse_snow_cases(
    spec: WarehouseSpec, snow: WarehouseSnow, units: UnitSystem
) -> list[SnowCase]:
    """The snow or ash cases of ``snow`` on ``spec``, positions and pressures in project units."""
    metres = length_scale(units, UnitSystem.SI_M_N)
    unit = pressure_from_kpa(1.0, units)  # one kN/m² in project units
    roof = {RoofType.MONO_PITCH: "mono", RoofType.GABLE: "gable"}.get(spec.roof, "flat")
    ground = snow.ground / unit
    try:
        # Naves stand under one roof: a single ridge (or slope) over the whole width.
        planes = roof_planes(spec.width * metres, 1, roof)
        if snow.method == "ash":
            cases = ash_cases(planes, ground)
        elif snow.method == "asce7":
            cases = asce7_snow_cases(
                planes,
                spec.slope,
                ground,
                ce=snow.exposure,
                ct=snow.thermal,
                importance=snow.importance,
                slippery=snow.slippery,
                unbalanced=snow.unbalanced,
            )
        else:
            cases = en1991_snow_cases(
                planes,
                spec.slope,
                ground,
                ce=snow.exposure,
                ct=snow.thermal,
                drifted=snow.unbalanced,
            )
    except SnowError as exc:
        raise WarehouseError(str(exc)) from exc
    return [
        SnowCase(case.name, tuple((x / metres, p * unit) for x, p in case.points)) for case in cases
    ]


def snow_loads(warehouse: Warehouse, case: SnowCase) -> list[Any]:
    """A snow or ash case as uniform loads on the purlins.

    Each purlin takes what falls on the half strip of plan to either
    neighbour: the case's mean pressure over it times its width, downwards.
    """
    from opensees_studio.core.loads import UniformElementLoad

    nodes = {n.id: n for n in warehouse.nodes}
    purlins = {e.id: e for e in warehouse.elements if e.id in warehouse.purlin_station}
    stations = warehouse.stations
    last = len(stations) - 1
    loads: list[Any] = []
    for element_id, k in warehouse.purlin_station.items():
        here = stations[k]
        per_length = 0.0
        for other in (k - 1, k + 1):
            if not 0 <= other <= last:
                continue
            middle = 0.5 * (here.x + stations[other].x)
            per_length += case.mean(here.x, middle) * abs(middle - here.x)
        if per_length == 0.0:
            continue
        _wx, wy, wz = _components(_gravity_components(nodes, purlins[element_id]) * per_length)
        loads.append(UniformElementLoad(element_id=element_id, wy=wy, wz=wz))
    return loads


# ───────────────────────── code presets and defaults ─────────────────────────
@dataclass(frozen=True)
class CodePreset:
    """What a design code fixes for a warehouse's gravity loads and combinations."""

    key: str
    """Key of :data:`opensees_studio.core.code_combinations.CODES`."""
    roof_live_role: str
    """Load role of the roof live case: the code's combinations use this one."""
    roof_live_case: str
    roof_live_kpa: float
    """Default uniform roof live load, kN/m² of horizontal projection."""
    midspan_point_kn: float
    """Default concentrated roof live load at mid-span of each frame, kN."""
    design_method: str
    source: str
    """Where the two defaults come from, for the wizard's tool tip."""
    wind_method: str = "rnc07"
    """Key of :data:`WIND_METHODS`: the wind procedure that goes with the code."""
    wind_speed: float = 45.0
    """Default wind speed, m/s (see :class:`WarehouseWind`)."""
    seismic_method: str = "rnc07"
    """Key of :data:`SEISMIC_METHODS`: the static method that goes with the code."""
    seismic_live_kpa: float = 0.0
    """Roof live load that counts as seismic weight, kN/m² of horizontal projection."""
    seismic_reduction: float = 2.0
    """Default Q, Ro or R of a steel warehouse of limited ductility."""
    snow_method: str = "ash"
    """Key of :data:`SNOW_METHODS`: what settles on a roof under this code."""


_KGF = 9.80665e-3  # one kilogram-force in kN

#: The codes the wizard offers, in order. RNC-07 Art. 11 a (light roofs): main
#: members carry 10 kg/m² plus 200 kg at mid-span; NSCM is the seismic code of
#: Managua and keeps RNC-07's gravity loads. ASCE 7-16 Table 4.3-1: 20 psf.
#: Wind: NSCM 7.2 sends the wind loads to RNC-07 Título IV, whose regional
#: velocity is a 50-year one (45 m/s in zone 2); the basic wind speed of ASCE
#: 7-16 is an ultimate one, about sqrt(1.6) times that, hence 57 m/s.
#: Earthquake: RNC-07 Art. 11 a counts 10 kg/m² of the roof live load as seismic
#: weight (CVR); NSCM 9.6 b counts 0.3 CV in warehouses (W = CM + 0.3 CV), 3 kg/m²
#: of that roof; ASCE 7-16 12.7.2 counts no roof live load.
#: EN 1990: the roof is category H of EN 1991-1-1 (recommended qk = 0.4 kN/m²;
#: the concentrated Qk = 1 kN does not act with it); ψ2 = 0 for it, so no roof
#: load counts as seismic mass (EN 1998-1 3.2.4); q = 1.5 is the upper limit of
#: low dissipative behaviour (EN 1998-1 Table 6.1). The basic wind velocity is
#: the National Annex's: 26 m/s is only a starting value.
CODE_PRESETS: dict[str, CodePreset] = {
    preset.key: preset
    for preset in (
        CodePreset(
            "rnc07", "L", "LIVE", 10 * _KGF, 200 * _KGF, "LRFD",
            "RNC-07 Art. 11 a: light roofs, 10 kg/m² plus 200 kg at mid-span of the main members.",
            seismic_live_kpa=10 * _KGF,
        ),
        CodePreset(
            "nscm", "Lr", "ROOF LIVE", 10 * _KGF, 200 * _KGF, "LRFD",
            "RNC-07 Art. 11 a: light roofs, 10 kg/m² plus 200 kg at mid-span of the main members.",
            seismic_method="nscm", seismic_live_kpa=0.3 * 10 * _KGF,
        ),
        CodePreset(
            "asce7_lrfd", "Lr", "ROOF LIVE", 0.9576, 0.0, "LRFD",
            "ASCE 7-16 Table 4.3-1: ordinary roofs, 20 psf (before any reduction).",
            "asce7", 57.0, seismic_method="asce7", seismic_reduction=3.0,
            snow_method="asce7",
        ),
        CodePreset(
            "asce7_asd", "Lr", "ROOF LIVE", 0.9576, 0.0, "ASD",
            "ASCE 7-16 Table 4.3-1: ordinary roofs, 20 psf (before any reduction).",
            "asce7", 57.0, seismic_method="asce7", seismic_reduction=3.0,
            snow_method="asce7",
        ),
        CodePreset(
            "en1990", "Lr", "ROOF LIVE", 0.4, 0.0, "LRFD",
            "EN 1991-1-1 Table 6.10: roofs of category H, 0.4 kN/m² (the 1 kN load Qk is a "
            "separate, local check).",
            "en1991", 26.0, seismic_method="en1998", seismic_reduction=1.5,
            snow_method="en1991",
        ),
    )
}  # fmt: skip

#: Default superimposed roof dead load (cladding and fixings), kN/m² of roof.
DEFAULT_ROOF_DEAD_KPA = 0.10


def pressure_from_kpa(value: float, units: UnitSystem) -> float:
    """``value`` kN/m² in the force / length² of ``units``."""
    return (
        value * 1e3 * force_scale(UnitSystem.SI_M_N, units)
        / length_scale(UnitSystem.SI_M_N, units) ** 2
    )  # fmt: skip


def force_from_kn(value: float, units: UnitSystem) -> float:
    """``value`` kN in the force of ``units``."""
    return value * 1e3 * force_scale(UnitSystem.SI_M_N, units)


def length_from_m(value: float, units: UnitSystem) -> float:
    """``value`` metres in the length of ``units``."""
    return value * length_scale(UnitSystem.SI_M_N, units)


@dataclass(frozen=True)
class WarehouseLoads:
    """The gravity loads of the roof, in project units, and what to derive from them."""

    code: str = "rnc07"
    roof_dead: float = 0.0
    """Superimposed dead load per area of roof surface (the self weight is separate)."""
    roof_live: float = 0.0
    """Live load per area of horizontal projection."""
    midspan_point: float = 0.0
    """Concentrated live load at mid-span of each nave of each frame."""
    combinations: bool = True
    design_lengths: bool = True
    wind: WarehouseWind | None = None
    """Wind cases to create, one or two per direction; None for no wind."""
    seismic: WarehouseSeismic | None = None
    """Earthquake cases to create, one per direction; None for no earthquake."""
    snow: WarehouseSnow | None = None
    """Snow or ash cases to create; None for neither."""

    def __post_init__(self) -> None:
        if self.code not in CODE_PRESETS:
            raise WarehouseError(f"Unknown design code {self.code!r}.")
        if min(self.roof_dead, self.roof_live, self.midspan_point) < 0.0:
            raise WarehouseError("Loads are entered as positive, downward values.")


def default_section(key: str, project: Project, section_id: int) -> Any:
    """The section a warehouse member takes when the user chooses none.

    Columns, rafters and braces come from the AISC library, purlins and girts
    are a lipped cold-formed channel; each is made of the project's default
    steel when it has it.
    """
    from opensees_studio.core.aisc import get_shape, shape_to_elastic_section
    from opensees_studio.core.cold_formed_sections import (
        cold_formed_section,
        default_cold_formed_material,
    )
    from opensees_studio.core.default_materials import find_default_material
    from opensees_studio.core.section_materials import linked
    from opensees_studio.core.sections.cold_formed import ColdFormedShape
    from opensees_studio.core.units import stress_scale

    units = project.meta.units
    e = 200e9 * stress_scale(UnitSystem.SI_M_N, units)
    g = e / 2.6
    if key in ("purlin", "girt"):
        mm = length_scale(UnitSystem.SI_MM_N, units)
        size = DEFAULT_PURLIN_MM
        shape = ColdFormedShape(
            profile="CS",
            d=size["d"] * mm,
            bf=size["bf"] * mm,
            lip=size["lip"] * mm,
            t=size["t"] * mm,
            r=size["r"] * mm,
        )
        # Its properties come out of the arcs of the corners (sines, tangents).
        return _portable_model(
            cold_formed_section(
                shape,
                section_id=section_id,
                ndm=project.ndm,
                name="C150X50X15X2.38",
                material=default_cold_formed_material(project),
                units=units,
                elastic_modulus=e,
                shear_modulus=g,
            )
        )
    section = shape_to_elastic_section(
        get_shape(DEFAULT_AISC_SHAPES[key]),
        elastic_modulus=e,
        shear_modulus=g,
        section_id=section_id,
        units=units,
        ndm=project.ndm,
        with_shear_areas=True,
    )
    material = find_default_material(project)
    return linked(section, material, units) if material is not None else section


def default_section_name(key: str) -> str:
    """Name of the section :func:`default_section` creates for ``key``."""
    return "C150X50X15X2.38" if key in ("purlin", "girt") else DEFAULT_AISC_SHAPES[key]


# ─────────────────────────────── the plan ───────────────────────────────
@dataclass
class WarehousePlan:
    """Everything a project gains to become the warehouse; nothing is applied yet."""

    warehouse: Warehouse
    sections: list[Any] = field(default_factory=list)
    """New sections, created because a member kind had none chosen."""
    groups: list[Any] = field(default_factory=list)
    grid: CoordinateGridSystem | None = None
    time_series: list[Any] = field(default_factory=list)
    patterns: list[Any] = field(default_factory=list)
    cases: list[Any] = field(default_factory=list)
    pattern_loads: list[tuple[int, str, list[Any]]] = field(default_factory=list)
    """``(pattern id, PlainLoadPattern list name, loads)`` to append."""
    combinations: list[Any] = field(default_factory=list)
    design: Any = None
    """The project's design settings with the unbraced lengths, or None to leave them."""
    notes: list[str] = field(default_factory=list)

    def apply(self, project: Project) -> None:
        """Write the plan into ``project`` (headless: scripts and tests, no undo)."""
        project.sections.extend(self.sections)
        project.nodes.extend(self.warehouse.nodes)
        project.elements.extend(self.warehouse.elements)
        project.groups.extend(self.groups)
        if self.grid is not None:
            project.coord_systems.append(self.grid)
        project.time_series.extend(self.time_series)
        project.load_patterns.extend(self.patterns)
        project.analyses.extend(self.cases)
        patterns = {p.id: p for p in project.load_patterns}
        for pattern_id, list_name, loads in self.pattern_loads:
            getattr(patterns[pattern_id], list_name).extend(loads)
        project.combinations.extend(self.combinations)
        if self.design is not None:
            project.design = self.design


def envelope_name(group: str) -> str:
    """Name of the envelope over the combinations of ``group``."""
    return f"{group} envelope"


def plan_warehouse(
    project: Project,
    spec: WarehouseSpec,
    *,
    sections: Mapping[str, int | None] | None = None,
    loads: WarehouseLoads | None = None,
    with_grid: bool = True,
    group_names: Mapping[str, str] | None = None,
) -> WarehousePlan:
    """Plan the warehouse ``spec`` for ``project`` without changing the project.

    ``sections`` gives the section id of each member kind (:data:`SECTION_KEYS`);
    a missing or None entry gets :func:`default_section`. ``loads`` adds the roof
    loads to the dead case and to a roof live case (created when the project has
    none of that name), the combinations of its code, and the unbraced lengths
    of the steel check. ``group_names`` renames the groups (a translation).

    Raises:
        WarehouseError: when the project is not a 3D frame model, or the numbers
            do not describe a warehouse.
    """
    from opensees_studio.core.groups import Group

    if (project.ndm, project.ndf) != WAREHOUSE_NDF:
        raise WarehouseError(
            "A warehouse needs a 3D frame model (ndm = 3, ndf = 6); this project is "
            f"ndm = {project.ndm}, ndf = {project.ndf}."
        )
    # Ids come from a scratch copy that receives each piece as it is planned,
    # so two things planned together never get the same id.
    scratch = project.model_copy(deep=True)
    chosen = dict(sections or {})
    existing = {s.id for s in project.sections}
    section_ids: dict[str, int] = {}
    new_sections: list[Any] = []
    created: dict[str, int] = {}
    for key in spec.section_keys():
        section_id = chosen.get(key)
        if section_id is not None:
            if section_id not in existing:
                raise WarehouseError(f"Section {section_id} ({key}) is not in the project.")
            section_ids[key] = int(section_id)
            continue
        name = default_section_name(key)
        if name not in created:
            section = default_section(key, scratch, scratch.next_section_id())
            scratch.sections.append(section)
            new_sections.append(section)
            created[name] = section.id
        section_ids[key] = created[name]

    warehouse = build_warehouse(
        spec,
        section_ids,
        first_node_id=project.next_node_id(),
        first_element_id=project.next_element_id(),
    )
    plan = WarehousePlan(warehouse=warehouse, sections=new_sections)
    scratch.nodes.extend(warehouse.nodes)
    scratch.elements.extend(warehouse.elements)

    names = {**GROUPS, **(group_names or {})}
    taken = {g.name for g in project.groups}
    for key in GROUPS:
        ids = warehouse.members[key]
        if not ids:
            continue
        name, n = names[key], 2
        while name in taken:
            name, n = f"{names[key]} {n}", n + 1
        taken.add(name)
        group = Group(
            id=scratch.next_group_id(), name=name, element_ids=ids, colour=GROUP_COLOURS[key]
        )
        scratch.groups.append(group)
        plan.groups.append(group)
    if with_grid:
        grid_name, n = "Warehouse", 2
        while any(c.name == grid_name for c in project.coord_systems):
            grid_name, n = f"Warehouse {n}", n + 1
        plan.grid = warehouse_grid(spec, name=grid_name)

    if loads is not None:
        _plan_loads(plan, project, scratch, loads)
        plan.pattern_loads[:] = [
            (pattern_id, list_name, [_portable_model(item) for item in items])
            for pattern_id, list_name, items in plan.pattern_loads
        ]
    return plan


def _static_cases_of(project: Project, pattern_id: int) -> list[int]:
    return [
        c.id
        for c in project.analyses
        if c.type == "Static" and pattern_id in getattr(c, "pattern_ids", ())
    ]


def _plan_loads(
    plan: WarehousePlan, project: Project, scratch: Project, loads: WarehouseLoads
) -> None:
    """The load cases, the roof loads, the combinations and the design lengths."""
    from opensees_studio.core.code_combinations import (
        ALTERNATIVE_ROLES,
        CODES,
        envelope_groups,
        generate_for_code,
    )
    from opensees_studio.core.combinations import CombinationTerm, LoadCombination
    from opensees_studio.core.defaults import make_dead_load_case, make_load_cases
    from opensees_studio.core.design.settings import DesignSettings
    from opensees_studio.core.loads import PlainLoadPattern
    from opensees_studio.core.mass_source import self_weight_per_node

    preset = CODE_PRESETS[loads.code]
    warehouse = plan.warehouse

    def add_case(series: Any, pattern: Any, case: Any) -> None:
        if getattr(case, "system", CASE_SYSTEM) == _DEFAULT_SYSTEM:
            case = case.model_copy(update={"system": CASE_SYSTEM})
        for target, planned, item in (
            (scratch.time_series, plan.time_series, series),
            (scratch.load_patterns, plan.patterns, pattern),
            (scratch.analyses, plan.cases, case),
        ):
            target.append(item)
            planned.append(item)

    dead = next(
        (p for p in project.load_patterns if isinstance(p, PlainLoadPattern) and p.self_weight),
        None,
    )
    if dead is None:
        add_case(*make_dead_load_case(scratch))
        dead = plan.patterns[-1]
    slow = [
        c.name or str(c.id)
        for c in project.analyses
        if c.id in _static_cases_of(project, dead.id)
        and getattr(c, "system", "") == _DEFAULT_SYSTEM
    ]
    if slow and len(warehouse.nodes) >= SLOW_SOLVER_NODES:
        plan.notes.append(
            f"Case {', '.join(slow)} keeps its {_DEFAULT_SYSTEM} solver, which is slow on a "
            f"model with this many pinned members: {CASE_SYSTEM} (Define > Load Cases) gives "
            "the same result many times faster."
        )
    live = next(
        (
            p
            for p in project.load_patterns
            if isinstance(p, PlainLoadPattern)
            and p.name == preset.roof_live_case
            and _static_cases_of(project, p.id)
        ),
        None,
    )
    if live is None and (loads.roof_live or loads.midspan_point):
        series, patterns, cases = make_load_cases(scratch, [preset.roof_live_case])
        add_case(series[0], patterns[0], cases[0])
        live = patterns[0]

    dead_loads = roof_pressure_loads(warehouse, loads.roof_dead, projected=False)
    if dead_loads:
        plan.pattern_loads.append((dead.id, "element_loads", dead_loads))
    if live is not None:
        live_loads = roof_pressure_loads(warehouse, loads.roof_live, projected=True)
        nodal, inside = midspan_point_loads(warehouse, loads.midspan_point)
        for list_name, items in (
            ("element_loads", live_loads),
            ("nodal_loads", nodal),
            ("point_loads", inside),
        ):
            if items:
                plan.pattern_loads.append((live.id, list_name, items))

    wind_case_ids: list[int] = []
    if loads.wind is not None:
        units = project.meta.units
        wind_cases = warehouse_wind_cases(warehouse.spec, loads.wind, units)
        taken = {p.name for p in project.load_patterns} | {c.name for c in project.analyses}
        names: list[str] = []
        for wind_case in wind_cases:
            name, n = wind_case.name, 2
            while name in taken:
                name, n = f"{wind_case.name} ({n})", n + 1
            taken.add(name)
            names.append(name)
        series, patterns, cases = make_load_cases(scratch, names)
        for wind_case, one_series, pattern, case in zip(
            wind_cases, series, patterns, cases, strict=True
        ):
            add_case(one_series, pattern, case)
            wind_case_ids.append(case.id)
            plan.pattern_loads.append(
                (pattern.id, "element_loads", wind_loads(warehouse, wind_case, units))
            )
        plan.notes.append(
            f"{len(wind_cases)} wind case(s) by {WIND_METHODS[loads.wind.method]}: the pressures "
            "of the main structure. Purlins, girts and cladding also need the local "
            "pressures of the code."
        )

    snow_case_ids: list[int] = []
    # A code without a snow role (RNC-07) takes the ash with the live load,
    # "adicional a la carga viva" (Art. 14).
    snow_role = "S" if "S" in CODES[loads.code].roles else "L"
    if loads.snow is not None:
        snow_cases = warehouse_snow_cases(warehouse.spec, loads.snow, project.meta.units)
        if snow_role != "S" and len(snow_cases) > 1:
            plan.notes.append(
                f"{CODES[loads.code].label} has no snow load in its combinations: only the "
                f"balanced case {snow_cases[0].name} was created, as a live load."
            )
            snow_cases = snow_cases[:1]
        taken = {p.name for p in scratch.load_patterns} | {c.name for c in scratch.analyses}
        names = []
        for snow_case in snow_cases:
            name, n = snow_case.name, 2
            while name in taken:
                name, n = f"{snow_case.name} ({n})", n + 1
            taken.add(name)
            names.append(name)
        series, patterns, cases = make_load_cases(scratch, names)
        for snow_case, one_series, pattern, case in zip(
            snow_cases, series, patterns, cases, strict=True
        ):
            add_case(one_series, pattern, case)
            snow_case_ids.append(plan.cases[-1].id)
            plan.pattern_loads.append(
                (pattern.id, "element_loads", snow_loads(warehouse, snow_case))
            )
        if snow_cases:
            peak = max(c.peak for c in snow_cases)
            plan.notes.append(
                f"{len(snow_cases)} case(s) by {SNOW_METHODS[loads.snow.method]}: "
                f"{snow_cases[0].points[0][1]:.6g} per area of plan on the whole roof"
                + (f", up to {peak:.6g} where it drifts" if len(snow_cases) > 1 else "")
                + ". Build-up against parapets, taller walls and in gutters is not included."
            )

    seismic_case_ids: list[int] = []
    if loads.seismic is not None:
        seismic = loads.seismic
        coefficient, clause = seismic_coefficient(seismic)
        own = {n.id for n in warehouse.nodes}
        weights = {
            n: w for n, w in self_weight_per_node(scratch, dead.self_weight).items() if n in own
        }
        for extra in (
            roof_weights(warehouse, loads.roof_dead, projected=False),
            roof_weights(warehouse, seismic.roof_live, projected=True),
        ):
            for node_id, weight in extra.items():
                weights[node_id] = weights.get(node_id, 0.0) + weight
        taken = {p.name for p in scratch.load_patterns} | {c.name for c in scratch.analyses}
        names = []
        for direction in seismic.directions:
            name, n = f"EQ {direction}", 2
            while name in taken:
                name, n = f"EQ {direction} ({n})", n + 1
            taken.add(name)
            names.append(name)
        series, patterns, cases = make_load_cases(scratch, names)
        for direction, one_series, pattern, case in zip(
            seismic.directions, series, patterns, cases, strict=True
        ):
            add_case(one_series, pattern, case)
            seismic_case_ids.append(plan.cases[-1].id)
            plan.pattern_loads.append(
                (
                    pattern.id,
                    "nodal_loads",
                    seismic_loads(warehouse, weights, coefficient, direction),
                )
            )
        total = sum(weights.values())
        plan.notes.append(
            f"{len(names)} earthquake case(s) by {SEISMIC_METHODS[seismic.method]}: "
            f"c = {coefficient:.4g} ({clause}), seismic weight {total:.6g}, base shear "
            f"{coefficient * total:.6g}. The period is not used, and the accidental torsion "
            "is not included."
        )

    if loads.combinations:
        roles: dict[str, list[int]] = {"D": _static_cases_of(scratch, dead.id)}
        if live is not None:
            roles[preset.roof_live_role] = _static_cases_of(scratch, live.id)
        if wind_case_ids:
            roles["W"] = wind_case_ids
        if seismic_case_ids:
            roles["E"] = seismic_case_ids
        if snow_case_ids:
            roles[snow_role] = [*roles.get(snow_role, []), *snow_case_ids]
        case_names = {c.id: c.name or str(c.id) for c in scratch.analyses}
        # A wind case has its direction and its suctions in it: reversing it is
        # not another wind, so each one enters the combinations with one sign.
        # An earthquake acts both ways, and by RNC-07 Art. 32 f and by NSCM each
        # direction goes with 30 % of the other. ASCE 7-16 12.5 asks for that
        # only in some seismic design categories: its generator has the option.
        # NSCM also folds the vertical component Ev = 0.2 a0 Fas CM (Ec. 7.8-4)
        # into the dead load factor: with the site of the earthquake page.
        options: dict[str, Any] = {}
        if snow_role == "S" and len(snow_case_ids) > 1:
            # The balanced and the drifted snow never lie on the roof together.
            options[ALTERNATIVE_ROLES] = ("S",)
        if loads.code in ORTHOGONAL_RULE_CODES and len(seismic_case_ids) > 1:
            options["orthogonal"] = True
        if loads.code == "en1990":
            # EN 1991-1-1 3.3.2 (1): nobody maintains a roof under snow or in a storm.
            options["roof_imposed_alone"] = True
            if wind_case_ids:
                # The wind lifts a light roof: the permanent action then relieves it.
                options["favourable_permanent"] = True
        if (
            loads.code == "nscm"
            and loads.seismic is not None
            and loads.seismic.method == "nscm"
            and seismic_case_ids
        ):
            options["a0_fas"] = round(nscm_a0_fas(loads.seismic), 4)
        generated = generate_for_code(
            loads.code,
            roles,
            case_names=case_names,
            peak_cases=wind_case_ids,
            options=options or None,
        )
        used = {c.name for c in project.combinations}
        fresh = [g for g in generated if g.name not in used]
        if len(fresh) < len(generated):
            plan.notes.append(
                f"{len(generated) - len(fresh)} {CODES[loads.code].label} combination(s) "
                "already existed and were kept."
            )
        next_id = scratch.next_combination_id()
        ids_by_group: dict[str, list[int]] = {g: [] for g in envelope_groups(fresh)}
        for combo in fresh:
            combination = LoadCombination(
                id=next_id + len(plan.combinations), name=combo.name, terms=combo.terms
            )
            plan.combinations.append(combination)
            ids_by_group[combo.group].append(combination.id)
        for group, ids in ids_by_group.items():
            if len(ids) > 1 and envelope_name(group) not in used:
                plan.combinations.append(
                    LoadCombination(
                        id=next_id + len(plan.combinations),
                        name=envelope_name(group),
                        combination_type="Envelope",
                        terms=[CombinationTerm(source="combination", ref_id=i) for i in ids],
                    )
                )

    if loads.design_lengths:
        overrides = member_design_overrides(warehouse)
        if overrides:
            base = project.design
            if base is None:
                base = DesignSettings(method=preset.design_method)  # type: ignore[arg-type]
            plan.design = base.model_copy(update={"members": [*base.members, *overrides]})


__all__ = [
    "BRACE_RELEASES",
    "BRACING_GROUPS",
    "CASE_SYSTEM",
    "CODE_PRESETS",
    "DEFAULT_AISC_SHAPES",
    "DEFAULT_ROOF_DEAD_KPA",
    "EN1998_IMPORTANCE",
    "EN1998_SOIL_FACTORS",
    "GROUPS",
    "GROUP_COLOURS",
    "ORTHOGONAL_RULE_CODES",
    "ROOF_STRUCTURES",
    "ROOF_TRUSS_TYPES",
    "SECONDARY_RELEASES",
    "SECTION_KEYS",
    "SEISMIC_DIRECTIONS",
    "SEISMIC_METHODS",
    "SNOW_METHODS",
    "TRUSS_BOTTOMS",
    "TRUSS_GROUPS",
    "TRUSS_SECTION_KEYS",
    "WAREHOUSE_NDF",
    "WIND_METHODS",
    "CodePreset",
    "EndWall",
    "RoofStation",
    "Warehouse",
    "WarehouseError",
    "WarehouseLoads",
    "WarehousePlan",
    "WarehouseSeismic",
    "WarehouseSnow",
    "WarehouseSpec",
    "WarehouseWind",
    "bottom_chord_ties",
    "build_warehouse",
    "building_shape",
    "default_section",
    "default_section_name",
    "end_wall_layout",
    "envelope_name",
    "force_from_kn",
    "length_from_m",
    "member_design_overrides",
    "midspan_point_loads",
    "nscm_a0_fas",
    "plan_warehouse",
    "portable",
    "pressure_from_kpa",
    "roof_pressure_loads",
    "roof_stations",
    "roof_weights",
    "seismic_coefficient",
    "seismic_loads",
    "snow_loads",
    "warehouse_grid",
    "warehouse_snow_cases",
    "warehouse_wind_cases",
    "wind_loads",
]
