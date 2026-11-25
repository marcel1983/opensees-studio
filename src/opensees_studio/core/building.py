"""Parametric multi-storey building: a 3D frame, its floors, its loads and its earthquake.

A building here is a regular space frame on a rectangular grid: bays along X
and Y (each with its own width), storeys along Z (each with its own height),
a column at every grid intersection and beams both ways at every floor. What
makes it a *building* rather than a frame is what goes with the members:

* **Storeys** — one :class:`~opensees_studio.core.storeys.Storey` per floor, so
  the drifts, the storey shears and the lateral forces have their levels.
* **Rigid diaphragms** — every floor is tied in its own plane to a retained
  node at the centre of the floor's mass, which is where a lateral force and
  an accidental torque are applied.
* **Slab loads as floor panels** — the slab is not modelled. Its weight and
  the live load are :class:`~opensees_studio.core.loads.FloorLoad` panels, one
  per bay and floor, that hand their load to the beams around them (two-way,
  or one-way along X or Y).
* **Mass source** — the mass is the weight of the dead case (self weight, slab
  and finishes) plus the part of the live load the code counts for the
  earthquake, lumped at the diaphragms.
* **Earthquake** — the equivalent lateral force of RNC-07 Art. 32, NSCM
  8.2.1 or ASCE 7-16 12.8 (:mod:`opensees_studio.core.equivalent_lateral`), one
  case per direction, or two with the accidental eccentricity to each side.

The module is pure (no Qt, no OpenSees): :func:`build_building` returns the
joints and the members, and :func:`plan_building` everything a project gains
(a :class:`BuildingPlan`) without touching the project.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from opensees_studio.core.frames import SupportCondition
from opensees_studio.core.geometry.elements import ElasticBeamColumn
from opensees_studio.core.geometry.grid import (
    CoordinateGridSystem,
    CoordinateSystem,
    GridSystem,
    make_grid_lines,
)
from opensees_studio.core.geometry.node import Node, Restraint6
from opensees_studio.core.units import UnitSystem, force_scale, length_scale
from opensees_studio.core.warehouse import (
    CASE_SYSTEM,
    CODE_PRESETS,
    ORTHOGONAL_RULE_CODES,
    SEISMIC_DIRECTIONS,
    SEISMIC_METHODS,
    envelope_name,
    portable,
)

if TYPE_CHECKING:
    from opensees_studio.core.equivalent_lateral import ElfParameters, ElfResult
    from opensees_studio.core.project import Project

BUILDING_NDF = (3, 6)
"""``(ndm, ndf)`` a building needs: a 3D frame model."""

#: The member kinds a building has, each with its own section.
SECTION_KEYS: tuple[str, ...] = ("column", "beam_x", "beam_y")
#: Group key -> name of the group the plan creates.
GROUPS: dict[str, str] = {
    "columns": "Building columns",
    "beams_x": "Beams along X",
    "beams_y": "Beams along Y",
}
GROUP_COLOURS: dict[str, str] = {
    "columns": "#4363d8",
    "beams_x": "#e6194b",
    "beams_y": "#f58231",
}

#: What the frame is made of: it sets the default sections and the empirical period.
FRAME_MATERIALS: tuple[str, ...] = ("steel", "concrete")
#: AISC shapes of a steel frame when no section is chosen.
DEFAULT_STEEL_SHAPES: dict[str, str] = {
    "column": "W14X90",
    "beam_x": "W18X50",
    "beam_y": "W18X50",
}
#: ``(width, depth)`` in mm of a concrete frame's sections when none is chosen.
DEFAULT_CONCRETE_MM: dict[str, tuple[float, float]] = {
    "column": (500.0, 500.0),
    "beam_x": (300.0, 600.0),
    "beam_y": (300.0, 600.0),
}
#: Name of the default concrete of a project (``core.default_materials``).
DEFAULT_CONCRETE = "4000Psi"

#: How a slab hands its load to the beams: both ways, or spanning along one axis.
SLAB_SPANS: tuple[str, ...] = ("two_way", "one_way_x", "one_way_y")
#: Slab span -> ``FloorLoad.distribution`` for a panel whose edge 1-2 runs along X.
_DISTRIBUTION: dict[str, str] = {
    "two_way": "two_way",
    "one_way_x": "one_way_12",
    "one_way_y": "one_way_23",
}

FLOOR_LIVE_CASE = "LIVE"
ROOF_LIVE_CASE = "ROOF LIVE"

#: Accidental eccentricity as a fraction of the floor's dimension across the
#: earthquake: RNC-07 Art. 32 d (0.1 b), NSCM 9.8 (5 %), ASCE 7-16 12.8.4.2 (5 %).
ACCIDENTAL_ECCENTRICITY: dict[str, float] = {"rnc07": 0.1, "nscm": 0.05, "asce7": 0.05}

#: Seismic method -> code key of :mod:`opensees_studio.core.equivalent_lateral`.
_ELF_CODE: dict[str, str] = {"rnc07": "rnc07", "nscm": "nscm2021", "asce7": "asce7_16"}

_KGF = 9.80665e-3  # one kilogram-force in kN

#: Uniform live loads by use, kN/m²: ``(live, the part that counts as seismic weight)``.
#: RNC-07 Tabla 1 gives the maximum CV and the reduced CVR that goes with the
#: earthquake (Art. 10). NSCM Tabla 7.1.1 has the same CV and counts 0.15 CV in
#: the seismic weight (9.6 a; 0.3 CV in warehouses and storage, 9.6 b). ASCE 7-16
#: Table 4.3-1, in psf (40, 40, 40, 50, 100; ordinary roofs 20); 12.7.2 counts no
#: live load outside storage.
OCCUPANCY_LIVE_KPA: dict[str, dict[str, tuple[float, float]]] = {
    "rnc07": {
        "residential": (200 * _KGF, 80 * _KGF),
        "classrooms": (250 * _KGF, 150 * _KGF),
        "hospital": (200 * _KGF, 100 * _KGF),
        "office": (250 * _KGF, 100 * _KGF),
        "assembly": (400 * _KGF, 250 * _KGF),
        "roof": (100 * _KGF, 40 * _KGF),
    },
    "nscm": {
        "residential": (200 * _KGF, 0.15 * 200 * _KGF),
        "classrooms": (250 * _KGF, 0.15 * 250 * _KGF),
        "hospital": (200 * _KGF, 0.15 * 200 * _KGF),
        "office": (250 * _KGF, 0.15 * 250 * _KGF),
        "assembly": (400 * _KGF, 0.15 * 400 * _KGF),
        "roof": (100 * _KGF, 0.15 * 100 * _KGF),
    },
    "asce7": {
        "residential": (1.9152, 0.0),
        "classrooms": (1.9152, 0.0),
        "hospital": (1.9152, 0.0),
        "office": (2.394, 0.0),
        "assembly": (4.788, 0.0),
        "roof": (0.9576, 0.0),
    },
}
#: The uses a floor can have (``"roof"`` is the roof slab, not a use).
OCCUPANCIES: tuple[str, ...] = ("residential", "classrooms", "hospital", "office", "assembly")

#: The design codes a building can be loaded by, of ``CODE_PRESETS``: the ones
#: with a table of live loads by use.
BUILDING_CODES: tuple[str, ...] = tuple(
    key
    for key in CODE_PRESETS
    if ("asce7" if key.startswith("asce7") else key) in OCCUPANCY_LIVE_KPA
)
#: The seismic methods a building can take, of ``SEISMIC_METHODS``: the ones
#: with an equivalent lateral force over the height (key -> clause).
BUILDING_SEISMIC_METHODS: dict[str, str] = {key: SEISMIC_METHODS[key] for key in _ELF_CODE}


class BuildingError(ValueError):
    """The numbers do not describe a building, or the project cannot take one."""


def live_load_family(code: str) -> str:
    """Key of :data:`OCCUPANCY_LIVE_KPA` for a design code of ``CODE_PRESETS``."""
    if code not in CODE_PRESETS:
        raise BuildingError(f"Unknown design code {code!r}.")
    return "asce7" if code.startswith("asce7") else code


# ───────────────────────────── the geometry ─────────────────────────────
@dataclass(frozen=True)
class BuildingSpec:
    """A regular building: bay widths along X and Y, storey heights, how it is built."""

    spans_x: tuple[float, ...]
    """Width of each bay along X, from the first column line."""
    spans_y: tuple[float, ...]
    """Width of each bay along Y."""
    storey_heights: tuple[float, ...]
    """Height of each storey, from the base upwards."""
    base: SupportCondition = SupportCondition.FIXED
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Where the first column's base stands."""
    frame: str = "steel"
    """Key of :data:`FRAME_MATERIALS`."""
    slab: str = "two_way"
    """Key of :data:`SLAB_SPANS`: how each floor panel loads its beams."""
    diaphragms: bool = True
    """Tie every floor in its plane to a retained node at its centre of mass."""
    column_angle: float = 0.0
    """Local axis angle of the columns, degrees: at 0 the web (the depth of the
    section) lies along X, so the frames along X bend the columns about their
    strong axis; 90 turns it along Y."""

    def __post_init__(self) -> None:
        for name in ("spans_x", "spans_y", "storey_heights"):
            object.__setattr__(self, name, tuple(float(v) for v in getattr(self, name)))
        object.__setattr__(self, "origin", tuple(float(v) for v in self.origin))
        if not self.spans_x or not self.spans_y:
            raise BuildingError("A building needs at least one bay each way.")
        if not self.storey_heights:
            raise BuildingError("A building needs at least one storey.")
        if min(self.spans_x) <= 0.0 or min(self.spans_y) <= 0.0:
            raise BuildingError("Bay widths must be positive.")
        if min(self.storey_heights) <= 0.0:
            raise BuildingError("Storey heights must be positive.")
        if self.frame not in FRAME_MATERIALS:
            raise BuildingError(f"Unknown frame material {self.frame!r}.")
        if self.slab not in SLAB_SPANS:
            raise BuildingError(f"Unknown slab span {self.slab!r}.")
        if len(self.origin) != 3:
            raise BuildingError("The origin is a point (x, y, z).")

    @classmethod
    def regular(
        cls,
        *,
        bays_x: int,
        bay_x: float,
        bays_y: int,
        bay_y: float,
        storeys: int,
        storey_height: float,
        first_storey_height: float | None = None,
        **fields: Any,
    ) -> BuildingSpec:
        """Equal bays each way and equal storeys, the first one optionally taller."""
        if min(bays_x, bays_y) < 1:
            raise BuildingError("A building needs at least one bay each way.")
        if storeys < 1:
            raise BuildingError("A building needs at least one storey.")
        heights = [storey_height] * storeys
        if first_storey_height is not None:
            heights[0] = first_storey_height
        return cls(
            spans_x=(bay_x,) * bays_x,
            spans_y=(bay_y,) * bays_y,
            storey_heights=tuple(heights),
            **fields,
        )

    @staticmethod
    def _lines(spans: tuple[float, ...]) -> list[float]:
        lines = [0.0]
        for span in spans:
            lines.append(lines[-1] + span)
        return lines

    @property
    def xs(self) -> list[float]:
        """Column lines along X, from 0."""
        return self._lines(self.spans_x)

    @property
    def ys(self) -> list[float]:
        """Column lines along Y, from 0."""
        return self._lines(self.spans_y)

    @property
    def zs(self) -> list[float]:
        """Levels from the base (0) to the roof."""
        return self._lines(self.storey_heights)

    @property
    def n_storeys(self) -> int:
        return len(self.storey_heights)

    @property
    def width(self) -> float:
        """Plan dimension along X."""
        return sum(self.spans_x)

    @property
    def depth(self) -> float:
        """Plan dimension along Y."""
        return sum(self.spans_y)

    @property
    def height(self) -> float:
        return sum(self.storey_heights)

    @property
    def floor_area(self) -> float:
        """Plan area of one floor."""
        return self.width * self.depth


@dataclass
class Building:
    """The joints and members of a building, and where each one is."""

    spec: BuildingSpec
    nodes: list[Node]
    elements: list[ElasticBeamColumn]
    members: dict[str, list[int]]
    """Group key (:data:`GROUPS`) -> element ids."""
    joints: dict[tuple[int, int, int], int]
    """``(i, j, k)`` -> node id: column line ``i`` along X, ``j`` along Y, level
    ``k`` (0 is the base)."""
    panels: dict[int, list[tuple[int, int, int, int]]] = field(default_factory=dict)
    """Level ``k`` (1 is the first floor) -> the corners of each bay, in order
    round the panel, the first edge along X."""

    def floor_nodes(self, level: int) -> list[int]:
        """The joints of level ``level`` (0 is the base)."""
        return sorted(n for (_i, _j, k), n in self.joints.items() if k == level)

    def summary(self) -> str:
        spec = self.spec
        return (
            f"Building {spec.width:g} x {spec.depth:g}, {spec.n_storeys} storey(s), "
            f"{spec.height:g} high: {len(spec.spans_x)} x {len(spec.spans_y)} bay(s) - "
            f"{len(self.members['columns'])} column, {len(self.members['beams_x'])} X beam and "
            f"{len(self.members['beams_y'])} Y beam elements, {len(self.nodes)} nodes."
        )


def _base_restraint(support: SupportCondition) -> Restraint6:
    fixed = support is SupportCondition.FIXED
    return (True, True, True, fixed, fixed, fixed)


_FREE: Restraint6 = (False, False, False, False, False, False)


def build_building(
    spec: BuildingSpec,
    sections: Mapping[str, int],
    *,
    first_node_id: int = 1,
    first_element_id: int = 1,
) -> Building:
    """The joints and the members of ``spec``, numbered from the given ids.

    Joints go level by level from the base, each level row by row along X.
    Members go storey by storey: its columns, then the X beams and the Y beams
    of the floor above them, so the ids read bottom to top.
    """
    missing = [key for key in SECTION_KEYS if key not in sections]
    if missing:
        raise BuildingError(f"No section given for: {', '.join(missing)}.")
    ox, oy, oz = spec.origin
    xs, ys, zs = spec.xs, spec.ys, spec.zs
    base = _base_restraint(spec.base)
    joints: dict[tuple[int, int, int], int] = {}
    nodes: list[Node] = []
    for k, z in enumerate(zs):
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                node_id = first_node_id + len(nodes)
                joints[i, j, k] = node_id
                nodes.append(
                    Node(
                        id=node_id,
                        coords=(ox + x, oy + y, oz + z),
                        restraint=base if k == 0 else _FREE,
                    )
                )

    elements: list[ElasticBeamColumn] = []
    members: dict[str, list[int]] = {key: [] for key in GROUPS}

    def member(group: str, section: str, a: int, b: int, angle: float = 0.0) -> None:
        element_id = first_element_id + len(elements)
        extra: dict[str, Any] = {"local_axis_angle": angle} if angle else {}
        elements.append(
            ElasticBeamColumn(
                id=element_id, nodes=(a, b), section_id=int(sections[section]), **extra
            )
        )
        members[group].append(element_id)

    panels: dict[int, list[tuple[int, int, int, int]]] = {}
    nx, ny = len(spec.spans_x), len(spec.spans_y)
    for k in range(1, spec.n_storeys + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                member("columns", "column", joints[i, j, k - 1], joints[i, j, k], spec.column_angle)
        for j in range(ny + 1):
            for i in range(nx):
                member("beams_x", "beam_x", joints[i, j, k], joints[i + 1, j, k])
        for i in range(nx + 1):
            for j in range(ny):
                member("beams_y", "beam_y", joints[i, j, k], joints[i, j + 1, k])
        panels[k] = [
            (joints[i, j, k], joints[i + 1, j, k], joints[i + 1, j + 1, k], joints[i, j + 1, k])
            for j in range(ny)
            for i in range(nx)
        ]
    return Building(
        spec=spec, nodes=nodes, elements=elements, members=members, joints=joints, panels=panels
    )


def building_grid(spec: BuildingSpec, *, name: str = "Building") -> CoordinateGridSystem:
    """A grid on the column lines and the floor levels."""
    return CoordinateGridSystem(
        name=name,
        coord=CoordinateSystem(origin=spec.origin),
        grid=GridSystem(
            x_grid_lines=make_grid_lines("X", spec.xs),
            y_grid_lines=make_grid_lines("Y", spec.ys),
            z_grid_lines=make_grid_lines("Z", spec.zs),
        ),
    )


# ──────────────────────────────── sections ────────────────────────────────
def default_section_name(key: str, frame: str) -> str:
    """Name of the section :func:`default_section` creates for ``key``."""
    if frame == "steel":
        return DEFAULT_STEEL_SHAPES[key]
    width, depth = DEFAULT_CONCRETE_MM[key]
    return f"{'COL' if key == 'column' else 'BEAM'} {width:g}x{depth:g}"


def rectangle_torsion_constant(width: float, depth: float) -> float:
    """Saint-Venant torsion constant of a solid rectangle (Roark's series, within 0.5 %)."""
    a, b = max(width, depth), min(width, depth)
    return a * b**3 * (1.0 / 3.0 - 0.21 * (b / a) * (1.0 - b**4 / (12.0 * a**4)))


def default_section(key: str, frame: str, project: Project, section_id: int) -> Any:
    """The section a building member takes when the user chooses none.

    A steel frame takes shapes of the AISC library, of the project's default
    steel; a concrete one solid rectangles of its default concrete, with the
    gross (uncracked) stiffness. Neither has shear areas: a beam under a floor
    panel's trapezoidal load is analysed as an Euler-Bernoulli member anyway.
    """
    from opensees_studio.core.section_materials import linked
    from opensees_studio.core.units import stress_scale

    units = project.meta.units
    if frame == "steel":
        from opensees_studio.core.aisc import get_shape, shape_to_elastic_section
        from opensees_studio.core.default_materials import find_default_material

        e = 200e9 * stress_scale(UnitSystem.SI_M_N, units)
        section = shape_to_elastic_section(
            get_shape(DEFAULT_STEEL_SHAPES[key]),
            elastic_modulus=e,
            shear_modulus=e / 2.6,
            section_id=section_id,
            units=units,
            ndm=project.ndm,
        )
        steel = find_default_material(project)
        return linked(section, steel, units) if steel is not None else section

    from opensees_studio.core.sections import ElasticSection, RectShape

    mm = length_scale(UnitSystem.SI_MM_N, units)
    width, depth = (v * mm for v in DEFAULT_CONCRETE_MM[key])
    # f'c = 28 MPa: Ec = 4700 sqrt(f'c) MPa (ACI 318), 24 kN/m³ with its steel.
    e = 24.87e9 * stress_scale(UnitSystem.SI_M_N, units)
    weight = (
        24_000.0
        * force_scale(UnitSystem.SI_M_N, units)
        / length_scale(UnitSystem.SI_M_N, units) ** 3
    )
    section = ElasticSection(
        id=section_id,
        name=default_section_name(key, frame),
        E=e,
        G=e / 2.4,
        A=width * depth,
        # The depth stands along local z: bending about local y is the strong one.
        Iy=width * depth**3 / 12.0,
        Iz=depth * width**3 / 12.0,
        J=rectangle_torsion_constant(width, depth),
        shape=RectShape(d=depth, b=width),
        unit_weight=weight,
    )
    concrete = next(
        (m for m in project.materials if getattr(m, "name", "") == DEFAULT_CONCRETE), None
    )
    return linked(section, concrete, units) if concrete is not None else section


# ───────────────────────────────── loads ─────────────────────────────────
@dataclass(frozen=True)
class BuildingSeismic:
    """The earthquake on a building by the equivalent lateral force of a code."""

    method: str = "rnc07"
    """Key of ``core.warehouse.SEISMIC_METHODS``."""
    a0: float = 0.3
    """RNC-07 and NSCM: peak ground acceleration, in g."""
    soil: str = "II"
    """RNC-07 soil type I to III, or NSCM site class A to D."""
    importance_class: str = ""
    """RNC-07 group A to C or NSCM risk category I to IV; "" = Group B / category II."""
    reduction: float = 2.0
    """Q of RNC-07, Ro of NSCM or R of ASCE 7."""
    regularity: str = "regular"
    """RNC-07 Art. 23 regularity, for Q'."""
    sds: float = 1.0
    """ASCE 7: design spectral acceleration at short periods, g."""
    sd1: float = 0.6
    """ASCE 7: design spectral acceleration at 1 s, g."""
    importance: float = 1.0
    """ASCE 7: importance factor Ie."""
    period_x: float = 0.0
    """Fundamental period for the earthquake along X, s; 0 takes the code's
    empirical period (ASCE 7 and NSCM) or the plateau of the spectrum (RNC-07,
    which has no empirical period)."""
    period_y: float = 0.0
    system: str = ""
    """Key of ``equivalent_lateral.ASCE_PERIOD_SYSTEMS`` for the empirical
    period; "" takes the moment frame of the building's material."""
    eccentricity: float | None = None
    """Accidental eccentricity as a fraction of the floor's dimension across
    the earthquake; None takes the code's (:data:`ACCIDENTAL_ECCENTRICITY`),
    0 leaves the torsion out."""
    directions: tuple[str, ...] = SEISMIC_DIRECTIONS

    def __post_init__(self) -> None:
        if self.method not in SEISMIC_METHODS:
            raise BuildingError(f"Unknown seismic method {self.method!r}.")
        if self.method not in _ELF_CODE:
            raise BuildingError(
                f"{SEISMIC_METHODS[self.method]} has no equivalent lateral force for a "
                "building here; choose one of " + ", ".join(BUILDING_SEISMIC_METHODS.values()) + "."
            )
        if self.reduction <= 0.0:
            raise BuildingError("The seismic reduction factor must be positive.")
        if self.period_x < 0.0 or self.period_y < 0.0:
            raise BuildingError("A period cannot be negative.")
        if self.eccentricity is not None and not 0.0 <= self.eccentricity <= 0.5:
            raise BuildingError("The accidental eccentricity is a fraction between 0 and 0.5.")
        if not self.directions:
            raise BuildingError("Choose at least one earthquake direction.")
        for direction in self.directions:
            if direction not in SEISMIC_DIRECTIONS:
                raise BuildingError(f"Unknown earthquake direction {direction!r}.")

    @property
    def eccentricity_ratio(self) -> float:
        """The accidental eccentricity in use."""
        if self.eccentricity is not None:
            return self.eccentricity
        return ACCIDENTAL_ECCENTRICITY[self.method]


def elf_parameters(
    seismic: BuildingSeismic, spec: BuildingSpec, units: UnitSystem, direction: str
) -> tuple[ElfParameters, str]:
    """The lateral force parameters for ``direction``, and where the period comes from.

    Raises:
        BuildingError: when the code cannot give a period for the system.
    """
    from opensees_studio.core.equivalent_lateral import (
        ASCE_PERIOD_SYSTEMS,
        ElfError,
        ElfParameters,
        approximate_period,
    )

    given = seismic.period_x if direction == "X" else seismic.period_y
    system = seismic.system or f"{spec.frame}_mrf"
    if system not in ASCE_PERIOD_SYSTEMS:
        raise BuildingError(f"Unknown structural system {system!r}.")
    code = _ELF_CODE[seismic.method]
    approximate = 0.0
    use_period = False
    if seismic.method == "rnc07":
        # No empirical period in RNC-07: without one, the plateau (Art. 32 a).
        use_period = given > 0.0
        period = given if use_period else 1.0
        source = f"T = {given:g} s" if use_period else "the plateau of the spectrum (no period)"
    else:
        try:
            approximate = approximate_period(
                code,
                system,
                spec.height,
                length_scale(units, UnitSystem.SI_M_N),
            )
        except ElfError as exc:
            raise BuildingError(str(exc)) from exc
        period = given if given > 0.0 else approximate
        source = (
            f"T = {given:g} s"
            if given > 0.0
            else f"the empirical period Ta = {approximate:.3g} s ({ASCE_PERIOD_SYSTEMS[system][0]})"
        )
    parameters = ElfParameters(
        code=code,
        period=period,
        sds=seismic.sds,
        sd1=seismic.sd1,
        r=seismic.reduction,
        importance=seismic.importance,
        eccentricity_ratio=seismic.eccentricity_ratio,
        a0=seismic.a0,
        soil=seismic.soil,
        importance_class=seismic.importance_class,
        regularity=seismic.regularity,
        use_period=use_period,
        approximate_period=approximate if seismic.method == "nscm" else 0.0,
    )
    return parameters, source


def seismic_case_names(direction: str, eccentric: bool) -> list[tuple[str, int]]:
    """``(case name, eccentricity sign)`` of the earthquake along ``direction``."""
    if eccentric:
        return [(f"EQ {direction} +e", 1), (f"EQ {direction} -e", -1)]
    return [(f"EQ {direction}", 0)]


@dataclass(frozen=True)
class BuildingLoads:
    """The floor loads of a building, per area and in project units, and its design code."""

    code: str = "rnc07"
    """Key of ``core.warehouse.CODE_PRESETS``."""
    floor_dead: float = 0.0
    """Slab, finishes and partitions on every floor below the roof (the self
    weight of the frame is the dead case's own)."""
    roof_dead: float = 0.0
    """The same on the roof."""
    floor_live: float = 0.0
    roof_live: float = 0.0
    floor_live_seismic: float = 0.0
    """The part of the floor live load that counts as seismic weight (the CVR
    of RNC-07 Tabla 1, 0.15 CV by NSCM 9.6)."""
    roof_live_seismic: float = 0.0
    combinations: bool = True
    seismic: BuildingSeismic | None = None

    def __post_init__(self) -> None:
        if self.code not in CODE_PRESETS:
            raise BuildingError(f"Unknown design code {self.code!r}.")
        values = (
            self.floor_dead,
            self.roof_dead,
            self.floor_live,
            self.roof_live,
            self.floor_live_seismic,
            self.roof_live_seismic,
        )
        if min(values) < 0.0:
            raise BuildingError("Loads are entered as positive, downward values.")
        for part, whole, what in (
            (self.floor_live_seismic, self.floor_live, "floor"),
            (self.roof_live_seismic, self.roof_live, "roof"),
        ):
            if part > whole * (1.0 + 1e-9):
                raise BuildingError(
                    f"The {what} live load in the seismic weight cannot exceed the "
                    f"{what} live load."
                )


def occupancy_loads(code: str, occupancy: str, units: UnitSystem) -> dict[str, float]:
    """The live loads of a use by a code, as :class:`BuildingLoads` fields in project units."""
    from opensees_studio.core.warehouse import pressure_from_kpa

    family = live_load_family(code)
    if family not in OCCUPANCY_LIVE_KPA:
        raise BuildingError(f"No table of live loads by use for the design code {code!r}.")
    table = OCCUPANCY_LIVE_KPA[family]
    if occupancy not in OCCUPANCIES:
        raise BuildingError(f"Unknown use {occupancy!r}.")
    floor, floor_seismic = table[occupancy]
    roof, roof_seismic = table["roof"]
    return {
        "floor_live": pressure_from_kpa(floor, units),
        "floor_live_seismic": pressure_from_kpa(floor_seismic, units),
        "roof_live": pressure_from_kpa(roof, units),
        "roof_live_seismic": pressure_from_kpa(roof_seismic, units),
    }


def floor_loads(building: Building, floor: float, roof: float) -> list[Any]:
    """One floor panel load per bay and floor: ``roof`` on the top level, ``floor`` below."""
    from opensees_studio.core.loads import FloorLoad

    distribution = _DISTRIBUTION[building.spec.slab]
    top = building.spec.n_storeys
    return [
        FloorLoad(nodes=corners, value=value, distribution=distribution)  # type: ignore[arg-type]
        for level, panels in sorted(building.panels.items())
        for value in [roof if level == top else floor]
        if value > 0.0
        for corners in panels
    ]


# ──────────────────────────────── the plan ────────────────────────────────
@dataclass
class BuildingPlan:
    """Everything a project gains to become the building; nothing is applied yet."""

    building: Building
    sections: list[Any] = field(default_factory=list)
    """New sections, created because a member kind had none chosen."""
    groups: list[Any] = field(default_factory=list)
    grid: CoordinateGridSystem | None = None
    storeys: list[Any] = field(default_factory=list)
    """New storeys: a level the project already has a storey at keeps it."""
    retained_nodes: list[Node] = field(default_factory=list)
    """The node at the centre of mass of each floor that gets a diaphragm."""
    diaphragms: list[Any] = field(default_factory=list)
    mass_source: Any = None
    """The project's mass source as it should be, or None to leave it."""
    time_series: list[Any] = field(default_factory=list)
    patterns: list[Any] = field(default_factory=list)
    cases: list[Any] = field(default_factory=list)
    pattern_loads: list[tuple[int, str, list[Any]]] = field(default_factory=list)
    """``(pattern id, PlainLoadPattern list name, loads)`` to append."""
    combinations: list[Any] = field(default_factory=list)
    lateral: dict[str, ElfResult] = field(default_factory=dict)
    """Direction -> base shear and storey forces, for a report."""
    notes: list[str] = field(default_factory=list)

    def apply(self, project: Project) -> None:
        """Write the plan into ``project`` (headless: scripts and tests, no undo)."""
        project.sections.extend(self.sections)
        project.nodes.extend(self.building.nodes)
        project.nodes.extend(self.retained_nodes)
        project.elements.extend(self.building.elements)
        project.groups.extend(self.groups)
        if self.grid is not None:
            project.coord_systems.append(self.grid)
        project.storeys.extend(self.storeys)
        project.diaphragms.extend(self.diaphragms)
        project.time_series.extend(self.time_series)
        project.load_patterns.extend(self.patterns)
        project.analyses.extend(self.cases)
        patterns = {p.id: p for p in project.load_patterns}
        for pattern_id, list_name, loads in self.pattern_loads:
            getattr(patterns[pattern_id], list_name).extend(loads)
        if self.mass_source is not None:
            project.mass_source = self.mass_source
        project.combinations.extend(self.combinations)


def _unique(name: str, taken: set[str]) -> str:
    candidate, n = name, 2
    while candidate in taken:
        candidate, n = f"{name} {n}", n + 1
    taken.add(candidate)
    return candidate


def plan_building(
    project: Project,
    spec: BuildingSpec,
    *,
    sections: Mapping[str, int | None] | None = None,
    loads: BuildingLoads | None = None,
    with_grid: bool = True,
    group_names: Mapping[str, str] | None = None,
) -> BuildingPlan:
    """Plan the building ``spec`` for ``project`` without changing the project.

    ``sections`` gives the section id of each member kind (:data:`SECTION_KEYS`);
    a missing or None entry gets :func:`default_section`. ``loads`` adds the
    slab loads to the dead case and to the live cases, the mass source, the
    earthquake cases and the combinations of its code. ``group_names`` renames
    the groups (a translation).

    Raises:
        BuildingError: when the project is not a 3D frame model, or the numbers
            do not describe a building.
    """
    from opensees_studio.core.member_groups import section_groups
    from opensees_studio.core.storeys import Storey, elevation_tolerance

    if (project.ndm, project.ndf) != BUILDING_NDF:
        raise BuildingError(
            "A building needs a 3D frame model (ndm = 3, ndf = 6); this project is "
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
    for key in SECTION_KEYS:
        section_id = chosen.get(key)
        if section_id is not None:
            if section_id not in existing:
                raise BuildingError(f"Section {section_id} ({key}) is not in the project.")
            section_ids[key] = int(section_id)
            continue
        name = default_section_name(key, spec.frame)
        if name not in created:
            section = default_section(key, spec.frame, scratch, scratch.next_section_id())
            scratch.sections.append(section)
            new_sections.append(section)
            created[name] = section.id
        section_ids[key] = created[name]

    building = build_building(
        spec,
        section_ids,
        first_node_id=project.next_node_id(),
        first_element_id=project.next_element_id(),
    )
    plan = BuildingPlan(building=building, sections=new_sections)
    scratch.nodes.extend(building.nodes)
    scratch.elements.extend(building.elements)

    groups = section_groups(
        building.members,
        elements=building.elements,
        sections=scratch.sections,
        names={**GROUPS, **(group_names or {})},
        colours=GROUP_COLOURS,
        taken={g.name for g in project.groups},
        first_id=scratch.next_group_id(),
    )
    scratch.groups.extend(groups)
    plan.groups.extend(groups)
    if with_grid:
        plan.grid = building_grid(
            spec, name=_unique("Building", {c.name for c in project.coord_systems})
        )

    # Storeys: a level the project already has one at keeps it.
    tol = elevation_tolerance(scratch)
    storey_names = {s.name for s in project.storeys}
    storey_at: dict[int, Any] = {}
    for level in range(1, spec.n_storeys + 1):
        elevation = spec.origin[2] + spec.zs[level]
        found = next((s for s in scratch.storeys if abs(s.elevation - elevation) <= tol), None)
        if found is None:
            found = Storey(
                id=scratch.next_storey_id(),
                name=_unique(
                    "Roof" if level == spec.n_storeys else f"Storey {level}", storey_names
                ),
                elevation=elevation,
            )
            scratch.storeys.append(found)
            plan.storeys.append(found)
        storey_at[level] = found

    gravity = _plan_gravity(plan, project, scratch, loads) if loads is not None else None
    if spec.diaphragms:
        _plan_diaphragms(plan, project, scratch, storey_at)
    if loads is not None and gravity is not None:
        _plan_lateral_and_combinations(plan, project, scratch, loads, gravity)
    return plan


def _static_cases_of(project: Project, pattern_id: int) -> list[int]:
    return [
        c.id
        for c in project.analyses
        if c.type == "Static" and pattern_id in getattr(c, "pattern_ids", ())
    ]


@dataclass
class _Gravity:
    """The gravity patterns of a plan, kept between its steps."""

    dead: Any = None
    floor_live: Any = None
    roof_live: Any = None


def _add_case(plan: BuildingPlan, scratch: Project, series: Any, pattern: Any, case: Any) -> None:
    if getattr(case, "system", CASE_SYSTEM) != CASE_SYSTEM:
        case = case.model_copy(update={"system": CASE_SYSTEM})
    for target, planned, item in (
        (scratch.time_series, plan.time_series, series),
        (scratch.load_patterns, plan.patterns, pattern),
        (scratch.analyses, plan.cases, case),
    ):
        # The scratch project gets its own copy: the plan's loads are added to
        # it as they are planned, and must not reach the plan's pattern twice.
        target.append(item.model_copy(deep=True))
        planned.append(item)


def _plan_gravity(
    plan: BuildingPlan, project: Project, scratch: Project, loads: BuildingLoads
) -> _Gravity:
    """The dead and live cases, the floor panels and the mass source."""
    from opensees_studio.core.defaults import make_dead_load_case, make_load_cases
    from opensees_studio.core.loads import PlainLoadPattern
    from opensees_studio.core.mass_source import MassSource, MassSourcePattern

    building = plan.building
    gravity = _Gravity()
    gravity.dead = next(
        (p for p in project.load_patterns if isinstance(p, PlainLoadPattern) and p.self_weight),
        None,
    )
    if gravity.dead is None:
        _add_case(plan, scratch, *make_dead_load_case(scratch))
        gravity.dead = plan.patterns[-1]

    def live_pattern(name: str) -> Any:
        found = next(
            (
                p
                for p in project.load_patterns
                if isinstance(p, PlainLoadPattern)
                and p.name == name
                and _static_cases_of(project, p.id)
            ),
            None,
        )
        if found is None:
            series, patterns, cases = make_load_cases(scratch, [name])
            _add_case(plan, scratch, series[0], patterns[0], cases[0])
            found = patterns[0]
        return found

    def add_panels(pattern: Any, panels: list[Any]) -> None:
        if not panels:
            return
        plan.pattern_loads.append((pattern.id, "floor_loads", panels))
        # The scratch pattern carries them too: the mass source reads them there.
        for candidate in scratch.load_patterns:
            if candidate.id == pattern.id and isinstance(candidate, PlainLoadPattern):
                candidate.floor_loads.extend(panels)

    add_panels(gravity.dead, floor_loads(building, loads.floor_dead, loads.roof_dead))
    floor_live = floor_loads(building, loads.floor_live, 0.0)
    if floor_live:
        gravity.floor_live = live_pattern(FLOOR_LIVE_CASE)
        add_panels(gravity.floor_live, floor_live)
    roof_live = floor_loads(building, 0.0, loads.roof_live)
    if roof_live:
        gravity.roof_live = live_pattern(ROOF_LIVE_CASE)
        add_panels(gravity.roof_live, roof_live)

    # The mass: everything the dead case weighs, and the live load the code
    # counts. The dead case has the self weight, so the elements' own is off.
    wanted = [(gravity.dead.id, 1.0)]
    if gravity.floor_live is not None and loads.floor_live_seismic > 0.0:
        wanted.append((gravity.floor_live.id, loads.floor_live_seismic / loads.floor_live))
    if gravity.roof_live is not None and loads.roof_live_seismic > 0.0:
        wanted.append((gravity.roof_live.id, loads.roof_live_seismic / loads.roof_live))
    current = project.mass_source
    entries = [MassSourcePattern(pattern_id=p, factor=f) for p, f in wanted]
    if current is None:
        source = MassSource(element_self_mass=False, patterns=entries)
    else:
        have = {entry.pattern_id for entry in current.patterns}
        extra = [entry for entry in entries if entry.pattern_id not in have]
        update: dict[str, Any] = {"patterns": [*current.patterns, *extra]}
        if gravity.dead.id not in have and current.element_self_mass:
            # The dead case joins the source with its self weight: the elements'
            # own would count it a second time.
            update["element_self_mass"] = False
        source = current.model_copy(update=update)
        if extra:
            plan.notes.append(
                "The project already had a mass source: the building's dead and live "
                "cases were added to it. Check that no weight is counted twice "
                "(Define > Mass Source)."
            )
    if source != current:
        plan.mass_source = source
        scratch.mass_source = source
    return gravity


def _plan_diaphragms(
    plan: BuildingPlan, project: Project, scratch: Project, storey_at: Mapping[int, Any]
) -> None:
    """A rigid diaphragm per floor, its retained node at the centre of the floor's mass."""
    from opensees_studio.core.constraints import RigidDiaphragm
    from opensees_studio.core.mass_source import diaphragm_centre_of_mass, effective_nodal_masses

    building = plan.building
    tied = {d.storey_id for d in project.diaphragms if d.storey_id is not None}
    # Weighed once: a diaphragm added below moves the mass of its own floor
    # only, so the floors still to come weigh the same before and after it.
    masses = effective_nodal_masses(scratch)
    for level in range(1, building.spec.n_storeys + 1):
        storey = storey_at[level]
        if storey.id in tied:
            plan.notes.append(
                f"Storey {storey.name or storey.id} already has a rigid diaphragm: the "
                "building's floor joins it."
            )
            continue
        x, y, _z = diaphragm_centre_of_mass(scratch, building.floor_nodes(level), masses=masses)
        # Exactly in the floor: OpenSees warns about every joint of a diaphragm
        # whose retained node is a rounding error above or below it.
        z = building.spec.origin[2] + building.spec.zs[level]
        # The centre comes out of sums of products: rounded, the same building
        # is the same file on every machine (`warehouse.portable`).
        retained = Node(id=scratch.next_node_id(), coords=(portable(x), portable(y), z))
        scratch.nodes.append(retained)
        plan.retained_nodes.append(retained)
        diaphragm = RigidDiaphragm(
            id=scratch.next_diaphragm_id(),
            name=f"Diaphragm {storey.name or storey.id}",
            retained_node=retained.id,
            storey_id=storey.id,
        )
        scratch.diaphragms.append(diaphragm)
        plan.diaphragms.append(diaphragm)


def _portable_forces(forces: Sequence[float]) -> tuple[float, float, float, float, float, float]:
    """The six components of a nodal load, rounded by :func:`warehouse.portable`."""
    fx, fy, fz, mx, my, mz = (portable(v) for v in forces)
    return fx, fy, fz, mx, my, mz


def _plan_lateral_and_combinations(
    plan: BuildingPlan,
    project: Project,
    scratch: Project,
    loads: BuildingLoads,
    gravity: _Gravity,
) -> None:
    """The earthquake cases and the combinations of the code."""
    from opensees_studio.core.code_combinations import (
        CODES,
        EARTHQUAKE_DIRECTIONS,
        envelope_groups,
        generate_for_code,
    )
    from opensees_studio.core.combinations import CombinationTerm, LoadCombination
    from opensees_studio.core.defaults import make_load_cases
    from opensees_studio.core.equivalent_lateral import (
        ElfError,
        equivalent_lateral_forces,
        nodal_forces,
    )
    from opensees_studio.core.loads import NodalLoad
    from opensees_studio.core.mass_source import effective_nodal_masses

    preset = CODE_PRESETS[loads.code]
    spec = plan.building.spec
    units = project.meta.units

    seismic_ids: list[int] = []
    direction_of: dict[int, str] = {}
    if loads.seismic is not None:
        seismic = loads.seismic
        ratio = seismic.eccentricity_ratio
        eccentric = ratio > 0.0 and spec.diaphragms
        if ratio > 0.0 and not spec.diaphragms:
            plan.notes.append(
                "Without rigid diaphragms the accidental torsion is left out of the "
                "earthquake cases."
            )
        taken = {p.name for p in scratch.load_patterns} | {c.name for c in scratch.analyses}
        # Weighed once: the cases added below carry no load of the mass source.
        masses = effective_nodal_masses(scratch)
        for direction in seismic.directions:
            parameters, source = elf_parameters(seismic, spec, units, direction)
            try:
                result = equivalent_lateral_forces(
                    scratch, SEISMIC_DIRECTIONS.index(direction), parameters, masses=masses
                )
            except ElfError as exc:
                raise BuildingError(str(exc)) from exc
            plan.lateral[direction] = result
            wanted = seismic_case_names(direction, eccentric)
            names = [_unique(name, taken) for name, _sign in wanted]
            series, patterns, cases = make_load_cases(scratch, names)
            for (_name, sign), one_series, pattern, case in zip(
                wanted, series, patterns, cases, strict=True
            ):
                _add_case(plan, scratch, one_series, pattern, case)
                forces = nodal_forces(scratch, result, sign, ratio, masses=masses)
                plan.pattern_loads.append(
                    (
                        pattern.id,
                        "nodal_loads",
                        [
                            NodalLoad(node_id=n, forces=_portable_forces(f))
                            for n, f in sorted(forces.items())
                        ],
                    )
                )
                seismic_ids.append(plan.cases[-1].id)
                direction_of[plan.cases[-1].id] = direction
            plan.notes.append(
                f"Earthquake along {direction} by {SEISMIC_METHODS[seismic.method]}, with "
                f"{source}: {result.notes[0]} W = {result.total_weight:.6g}, base shear "
                f"{result.base_shear:.6g}."
                + (
                    f" Accidental eccentricity {ratio:g} of the floor, to each side."
                    if eccentric
                    else ""
                )
            )
            plan.notes.extend(result.notes[1:])

    if not loads.combinations:
        return
    roles: dict[str, list[int]] = {"D": _static_cases_of(scratch, gravity.dead.id)}
    if gravity.floor_live is not None:
        roles["L"] = _static_cases_of(scratch, gravity.floor_live.id)
    if gravity.roof_live is not None:
        role = preset.roof_live_role
        roles[role] = [*roles.get(role, []), *_static_cases_of(scratch, gravity.roof_live.id)]
    if seismic_ids:
        roles["E"] = seismic_ids
    options: dict[str, Any] = {}
    if seismic_ids:
        options[EARTHQUAKE_DIRECTIONS] = direction_of
        if loads.code in ORTHOGONAL_RULE_CODES and len(set(direction_of.values())) > 1:
            options["orthogonal"] = True
        if loads.code == "nscm" and loads.seismic is not None and loads.seismic.method == "nscm":
            # Ev = 0.2 a0 Fas CM (NSCM Ec. 7.8-4): the site's value, not the generator's.
            from opensees_studio.core import nscm

            try:
                site = nscm.NscmSite(
                    a0=loads.seismic.a0,
                    site_class=loads.seismic.soil,
                    risk_category=loads.seismic.importance_class or "II",
                    r0=loads.seismic.reduction,
                )
                options["a0_fas"] = round(float(site.a0 * site.fas), 4)
            except (nscm.NscmError, KeyError, ValueError) as exc:
                raise BuildingError(str(exc)) from exc
    case_names = {c.id: c.name or str(c.id) for c in scratch.analyses}
    generated = generate_for_code(loads.code, roles, case_names=case_names, options=options or None)
    used = {c.name for c in project.combinations}
    fresh = [g for g in generated if g.name not in used]
    if len(fresh) < len(generated):
        plan.notes.append(
            f"{len(generated) - len(fresh)} combination(s) of {CODES[loads.code].label} "
            "already exist and were left as they are."
        )
    next_id = project.next_combination_id()
    ids_by_group: dict[str, list[int]] = {}
    for offset, item in enumerate(fresh):
        plan.combinations.append(
            LoadCombination(id=next_id + offset, name=item.name, terms=list(item.terms))
        )
        ids_by_group.setdefault(item.group, []).append(next_id + offset)
    next_id += len(fresh)
    for group in envelope_groups(generated):
        name = envelope_name(group)
        if name in used or len(ids_by_group.get(group, ())) < 2:
            continue
        plan.combinations.append(
            LoadCombination(
                id=next_id,
                name=name,
                combination_type="Envelope",
                terms=[
                    CombinationTerm(source="combination", ref_id=i) for i in ids_by_group[group]
                ],
            )
        )
        next_id += 1


__all__ = [
    "ACCIDENTAL_ECCENTRICITY",
    "BUILDING_CODES",
    "BUILDING_NDF",
    "BUILDING_SEISMIC_METHODS",
    "DEFAULT_CONCRETE_MM",
    "DEFAULT_STEEL_SHAPES",
    "FLOOR_LIVE_CASE",
    "FRAME_MATERIALS",
    "GROUPS",
    "GROUP_COLOURS",
    "OCCUPANCIES",
    "OCCUPANCY_LIVE_KPA",
    "ROOF_LIVE_CASE",
    "SECTION_KEYS",
    "SLAB_SPANS",
    "Building",
    "BuildingError",
    "BuildingLoads",
    "BuildingPlan",
    "BuildingSeismic",
    "BuildingSpec",
    "build_building",
    "building_grid",
    "default_section",
    "default_section_name",
    "elf_parameters",
    "floor_loads",
    "live_load_family",
    "occupancy_loads",
    "plan_building",
    "rectangle_torsion_constant",
    "seismic_case_names",
]
