"""How the runner realises frame releases, end offsets, insertion points and modifiers.

:func:`plan_frame_members` reads the project once and returns a
:class:`FramePlan`: the extra OpenSees objects to emit and, per frame element,
the node tags and joint offsets its ``element`` command uses. The runner emits
the plan in its build order; nothing here calls OpenSees, so the exported
script (which records the runner) stays the same command sequence.

**End releases.** OpenSees 3.8's ``elasticBeamColumn -release`` flags are not
used: in 3D a released ``ElasticBeam3d`` does not condense the fixed-end forces
of a ``-beamPoint`` load (measured: a moment at the released end), and force-
and displacement-based elements have no release option at all. Instead a
released end connects to a hidden node coincident with the joint:

* ``equalDOF`` ties the translations and every *kept* rotation that lines up
  with a global axis (exact, any element type, any constraint handler);
* a ``zeroLength`` element oriented along the member's local axes carries each
  partial-fixity spring and, when a kept rotation does not line up with a
  global axis (a skewed member that keeps torsion but releases M2 and M3),
  a penalty spring for it, :data:`PENALTY_FACTOR` times the member's own
  rotational stiffness. A fibre member has no elastic stiffness to scale
  that penalty from, so that one case is refused with a remedy.

The joint's reaction does not include what reaches it through ``equalDOF``:
:attr:`FramePlan.attached` lists the hidden nodes per joint so the runner can
add their reactions (moved to the joint) back.

**End offsets and insertion points** are ``geomTransf ... -jntOffset`` (exact,
no extra DOFs). A released end that is also offset is released at the face of
the rigid zone, as in SAP2000: a face node hangs off the joint with
``rigidLink beam`` and the release node pair sits at the face. ``rigidLink``
is not an identity constraint, which the Plain handler ignores, so such a
model runs with the Transformation handler (:attr:`FramePlan.needs_transformation`).
``Corotational`` in 3D ignores ``-jntOffset`` in OpenSees 3.8 (it prints "rigid
joint zones not implemented yet" and uses zero), so that combination is refused.

**Releases at a rigid-diaphragm joint.** A joint a diaphragm constrains is
already the constrained node of an MP constraint, and OpenSees 3.8's
Transformation handler cannot chain constraints: it keeps one MP per
constrained node and numbers a retained node that is itself constrained wrong,
solving without a warning (Lagrange and Penalty do chain, but their eigen
analysis is wrong: they put the constraint block into the mass matrix too). A
hidden node tied to such a joint by ``equalDOF`` or ``rigidLink`` is therefore
not an option, and no rearrangement of node-to-node constraints avoids the chain
(the hidden node needs its in-plane DOFs from the diaphragm's retained node and
the rest from the joint). So at a diaphragm joint:

* an ``elasticBeamColumn`` with an elastic section releases M2 / M3 in the
  element (``-releasey`` / ``-releasez``, condensed in its basic system, so at
  the face of a rigid end zone) and T by a zero ``G J`` (a member released in
  torsion at one end carries no torque). That is exact, but OpenSees condenses
  only the full-length ``-beamUniform``: a member with a point, partial or
  trapezoidal load, a consistent mass matrix, or a partial-fixity spring at that
  end takes the next route instead;
* any other member with elastic properties hangs the released end off a hidden
  node joined to the joint by a ``zeroLength`` whose kept directions are
  penalty springs, :data:`DIAPHRAGM_PENALTY_FACTOR` times the member's own
  stiffness (results within about 1e-7 of the exact ones, measured; a stiffer
  spring loses more to round-off than it gains). A fibre member, or such an end
  with a rigid end zone, is refused with a remedy.

**Modifiers** become a derived ``section Elastic`` per distinct (section,
modifiers) pair, or scaled inline properties for ``beamWithHinges``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from opensees_studio.core import (
    BeamWithHingesElement,
    ElasticBeamColumn,
    ElasticSection,
    FrameMember,
    Project,
)
from opensees_studio.core.diaphragms import constrained_node_ids, diaphragms_supported
from opensees_studio.core.frame_members import MemberLayout, member_layout, split_member_loads
from opensees_studio.core.geometry.frame_options import RELEASE_AXIS, RELEASE_DOFS

#: Penalty spring for a kept rotation about a skewed axis, as a multiple of the
#: member's largest rotational stiffness ``4 E I / L`` (or ``G J / L``).
PENALTY_FACTOR = 1.0e8

#: Penalty springs tying a released end's hidden node to a diaphragm joint, as a
#: multiple of the member's own translational / rotational stiffness. Measured on
#: the example building with partially fixed beams (against an exact reference):
#: 1e4 leaves about 3e-7 relative error, 1e5 about 1e-7 in displacements and 5e-8
#: in periods; from 1e6 on the dense eigen solver's round-off, which grows with
#: the stiffest entry, costs more than the stiffer spring gains (5e-6 at 1e6).
DIAPHRAGM_PENALTY_FACTOR = 1.0e5

#: ``elasticBeamColumn`` release flag of each release DOF, and its bit per end.
_ELEMENT_RELEASE = {"M3": "-releasez", "M2": "-releasey"}
_ELEMENT_RELEASE_BIT = {"i": 1, "j": 2}

#: zeroLength direction of each release DOF (rotation about local x, y, z).
_ZERO_LENGTH_DIR = {"T": 4, "M2": 5, "M3": 6}

_ALIGN_TOL = 1e-9


@dataclass(frozen=True)
class ExtraNode:
    tag: int
    coords: tuple[float, ...]
    joint: int
    """The project node this hidden node belongs to (reactions fold into it)."""


@dataclass(frozen=True)
class SpringLink:
    """A ``zeroLength`` element with one ``uniaxialMaterial Elastic`` per direction."""

    tag: int
    node_a: int
    node_b: int
    dirs: tuple[int, ...]
    material_tags: tuple[int, ...]
    stiffnesses: tuple[float, ...]
    orient: tuple[float, ...]


@dataclass(frozen=True)
class DerivedSection:
    tag: int
    args: tuple[Any, ...]
    """Arguments after ``"Elastic", tag`` of ``ops.section``."""


@dataclass
class MemberPlan:
    """What the ``element`` command of one frame member uses."""

    layout: MemberLayout | None
    nodes: tuple[int, int]
    offset_i: tuple[float, ...] = ()
    offset_j: tuple[float, ...] = ()
    section_id: int | None = None
    inline: dict[str, float] = field(default_factory=dict)
    """Modified ``A``, ``Iz``, ``Iy``, ``J`` of a ``beamWithHinges``."""
    rho: float | None = None
    element_releases: dict[str, int] = field(default_factory=dict)
    """``-releasez`` / ``-releasey`` code (1 end i, 2 end j, 3 both) of an elastic member
    released inside the element (see "Releases at a rigid-diaphragm joint")."""

    @property
    def release_args(self) -> tuple[Any, ...]:
        """The ``elasticBeamColumn`` release options, empty when the element releases nothing."""
        return tuple(
            arg
            for flag in ("-releasez", "-releasey")
            if self.element_releases.get(flag)
            for arg in (flag, self.element_releases[flag])
        )

    @property
    def joint_offset(self) -> tuple[float, ...]:
        """``-jntOffset`` values, empty when neither end is offset."""
        if not any(self.offset_i) and not any(self.offset_j):
            return ()
        return (*self.offset_i, *self.offset_j)


@dataclass
class FramePlan:
    members: dict[int, MemberPlan] = field(default_factory=dict)
    nodes: list[ExtraNode] = field(default_factory=list)
    rigid_links: list[tuple[int, int]] = field(default_factory=list)
    equal_dofs: list[tuple[int, int, tuple[int, ...]]] = field(default_factory=list)
    springs: list[SpringLink] = field(default_factory=list)
    sections: list[DerivedSection] = field(default_factory=list)
    #: joint → hidden nodes whose reactions belong to it.
    attached: dict[int, list[ExtraNode]] = field(default_factory=dict)
    #: (element id, end) → global rotation DOFs (1-based) the member leaves unstiffened at
    #: that joint; only for ends whose release lines up with the global axes.
    released_dofs: dict[tuple[int, str], set[int]] = field(default_factory=dict)

    @property
    def needs_transformation(self) -> bool:
        """A ``rigidLink`` is in the model: the Plain handler would ignore it."""
        return bool(self.rigid_links)


class _Tags:
    def __init__(self, used: list[int]) -> None:
        self._next = max(used, default=0) + 1

    def take(self) -> int:
        tag = self._next
        self._next += 1
        return tag


def _rotation_dofs(ndm: int) -> tuple[int, ...]:
    return (3,) if ndm == 2 else (4, 5, 6)


def _kept_rotation_dofs(layout: MemberLayout, kept: Sequence[str]) -> tuple[int, ...] | None:
    """Global rotation DOFs equivalent to keeping ``kept`` local rotations, None if skewed."""
    if layout.ndm == 2:
        return (3,) if "M3" in kept else ()
    if not kept:
        return ()
    if len(kept) == 3:
        return (4, 5, 6)
    axes = (layout.x, layout.y, layout.z)
    projector = sum(np.outer(axes[RELEASE_AXIS[d]], axes[RELEASE_AXIS[d]]) for d in kept)
    diagonal = np.round(np.diag(projector))
    if np.max(np.abs(projector - np.diag(diagonal))) > _ALIGN_TOL:
        return None
    return tuple(4 + g for g in range(3) if diagonal[g] == 1.0)


def _elastic_stiffness(
    project: Project, el: Any, clear_length: float
) -> tuple[float, float] | None:
    """Largest translational and rotational stiffness of an elastic member, None for a fibre one.

    ``max(E A / L, 12 E Iz / L^3, 12 E Iy / L^3)`` and ``max(4 E Iz, 4 E Iy, G J) / L``.
    """
    if isinstance(el, BeamWithHingesElement):
        E, A, Iz, Iy, G, J = el.E, el.A, el.Iz, el.Iy, el.G, el.J
    else:
        section = next((s for s in project.sections if s.id == el.section_id), None)
        if not isinstance(section, ElasticSection):
            return None
        E, A, Iz, Iy, G, J = section.E, section.A, section.Iz, section.Iy, section.G, section.J
    L = clear_length
    bending = max(Iz, Iy or 0.0)
    translational = max(E * A / L, 12.0 * E * bending / L**3)
    rotational = max(4.0 * E * bending, (G or 0.0) * (J or 0.0)) / L
    return translational, rotational


def _elastic_rotational_stiffness(project: Project, el: Any, clear_length: float) -> float | None:
    """``max(4 E Iz, 4 E Iy, G J) / L`` of an elastic member, None for a fibre member."""
    stiffness = _elastic_stiffness(project, el, clear_length)
    return None if stiffness is None else stiffness[1]


def diaphragm_joints(project: Project) -> set[int]:
    """Nodes a rigid diaphragm constrains (a released end there cannot use ``equalDOF``)."""
    if not project.diaphragms or not diaphragms_supported(project):
        return set()
    return {nid for d in project.diaphragms for nid in constrained_node_ids(project, d)}


def _condensable(project: Project, el: Any, layout: MemberLayout) -> bool:
    """Whether OpenSees can release ``el`` exactly inside the element.

    An ``elasticBeamColumn`` on an elastic section with a lumped mass, whose
    every load reaches the flexible part as a full-length ``-beamUniform``:
    ``ElasticBeam3d`` condenses only that load's fixed-end forces, and its
    consistent mass ignores the release.
    """
    if not isinstance(el, ElasticBeamColumn) or el.consistent_mass or project.ndm != 3:
        return False
    section = next((s for s in project.sections if s.id == el.section_id), None)
    if not isinstance(section, ElasticSection):
        return False
    segments: list[Any] = []
    points: list[Any] = []
    for pat in project.load_patterns:
        for ul in getattr(pat, "element_loads", ()):
            if ul.element_id == el.id:
                w = (ul.wx, ul.wy, ul.wz)
                segments.append((0.0, 1.0, w, w))
        for dl in getattr(pat, "distributed_loads", ()):
            if dl.element_id == el.id:
                segments.append((dl.x_start, dl.x_end, dl.start(), dl.end()))
        for pl in getattr(pat, "point_loads", ()):
            if pl.element_id == el.id:
                points.append((pl.x, (pl.px, pl.py, pl.pz)))
    if not segments and not points:
        return True
    split = split_member_loads(layout, segments, points)
    return not split.points and all(piece.is_uniform_full for piece in split.pieces)


def check_frame_options(project: Project) -> list[str]:
    """Problems with the frame assignments that the runner cannot realise."""
    problems: list[str] = []
    for el in project.elements:
        if not isinstance(el, FrameMember):
            continue
        for end in ("i", "j"):
            released = el.releases.end(end).released
            if project.ndm == 2 and any(d != "M3" for d in released):
                problems.append(
                    f"Element {el.id}: a 2D frame can only release M3 (got {', '.join(released)} "
                    f"at end {end})."
                )
        if project.ndm == 2 and el.insertion.offset_3:
            problems.append(
                f"Element {el.id}: a 2D frame cannot be offset along local 3 (out of plane)."
            )
    return problems


def _kept(release: Any, ndm: int) -> list[str]:
    kept = [d for d in RELEASE_DOFS if d not in release.released]
    return [d for d in kept if d == "M3"] if ndm == 2 else kept


def _unstiffened(layout: MemberLayout, release: Any) -> set[int] | None:
    """Global rotations a released end leaves unstiffened at its joint; None when skewed."""
    kept_dofs = _kept_rotation_dofs(layout, _kept(release, layout.ndm))
    if kept_dofs is None:
        return None
    springs = [d for d in release.released if release.spring(d) > 0.0]
    stiffened = {*kept_dofs, *(_kept_rotation_dofs(layout, springs) or ())}
    return set(_rotation_dofs(layout.ndm)) - stiffened


def plan_frame_members(project: Project) -> FramePlan:
    """Plan the extra OpenSees objects for every frame member's assignments."""
    problems = check_frame_options(project)
    if problems:
        raise ValueError("Frame assignments cannot be analysed:\n  - " + "\n  - ".join(problems))
    plan = FramePlan()
    node_tags = _Tags([n.id for n in project.nodes])
    element_tags = _Tags([e.id for e in project.elements])
    material_tags = _Tags([m.id for m in project.materials])
    section_tags = _Tags([s.id for s in project.sections])
    derived: dict[tuple[Any, ...], int] = {}
    ndm = project.ndm
    translations = (1, 2) if ndm == 2 else (1, 2, 3)
    at_diaphragm = diaphragm_joints(project)

    for el in project.elements:
        if not isinstance(el, FrameMember):
            continue
        layout = member_layout(project, el)
        member = MemberPlan(layout=layout, nodes=(el.nodes[0], el.nodes[1]))
        plan.members[el.id] = member
        # Released ends at a diaphragm joint that the element itself releases.
        condensed = {
            end
            for end, nid in zip(("i", "j"), el.nodes, strict=False)
            if nid in at_diaphragm
            and el.releases.end(end).released
            and not el.releases.end(end).springs
        }
        if condensed and (layout is None or not _condensable(project, el, layout)):
            condensed = set()
        # A torsion release in the element is a zero G J: the member carries no
        # torque at all, so a hidden node at its other end keeps T tied.
        torsion_free = any("T" in el.releases.end(end).released for end in condensed)
        _plan_modifiers(project, el, member, derived, section_tags, plan, torsion_free)
        if layout is None:
            continue
        if (
            ndm == 3
            and el.geom_transf == "Corotational"
            and (layout.has_offset("i") or layout.has_offset("j"))
        ):
            raise ValueError(
                f"Element {el.id}: OpenSees 3.8 ignores joint offsets on a 3D Corotational "
                "transformation. Use Linear or PDelta, or remove the end offsets / insertion point."
            )
        nodes = list(member.nodes)
        for k, end in enumerate(("i", "j")):
            offset = layout.offset_i if end == "i" else layout.offset_j
            release = el.releases.end(end)
            if not release.released or end in condensed:
                member_offset = tuple(float(v) for v in offset[:ndm])
                if end == "i":
                    member.offset_i = member_offset
                else:
                    member.offset_j = member_offset
                if end in condensed:
                    for dof in release.released:
                        if dof in _ELEMENT_RELEASE:
                            flag = _ELEMENT_RELEASE[dof]
                            code = member.element_releases.get(flag, 0)
                            member.element_releases[flag] = code | _ELEMENT_RELEASE_BIT[end]
                    unstiffened = _unstiffened(layout, release)
                    if not layout.has_offset(end) and unstiffened is not None:
                        plan.released_dofs[(el.id, end)] = unstiffened
                continue
            joint = nodes[k]
            joint_xyz = layout.joint_i if end == "i" else layout.joint_j
            kept = _kept(release, ndm)
            if torsion_free and "T" not in kept:
                kept = [d for d in RELEASE_DOFS if d == "T" or d in kept]
            if joint in at_diaphragm:
                nodes[k] = _plan_penalty_end(
                    project,
                    el,
                    layout,
                    end,
                    joint,
                    kept,
                    plan,
                    node_tags,
                    element_tags,
                    material_tags,
                )
                if end == "i":
                    member.offset_i = (0.0,) * ndm
                else:
                    member.offset_j = (0.0,) * ndm
                unstiffened = _unstiffened(layout, release)
                if unstiffened is not None:
                    plan.released_dofs[(el.id, end)] = unstiffened
                continue
            base = joint
            if layout.has_offset(end):
                face = ExtraNode(
                    node_tags.take(), tuple(float(v) for v in (joint_xyz + offset)[:ndm]), joint
                )
                plan.nodes.append(face)
                plan.attached.setdefault(joint, []).append(face)
                plan.rigid_links.append((joint, face.tag))
                base = face.tag
                base_xyz = face.coords
            else:
                base_xyz = tuple(float(v) for v in joint_xyz[:ndm])
            inner = ExtraNode(node_tags.take(), base_xyz, joint)
            plan.nodes.append(inner)
            plan.attached.setdefault(joint, []).append(inner)
            nodes[k] = inner.tag
            if end == "i":
                member.offset_i = (0.0,) * ndm
            else:
                member.offset_j = (0.0,) * ndm

            kept_dofs = _kept_rotation_dofs(layout, kept)
            dirs: list[int] = []
            stiffness: list[float] = []
            if kept_dofs is None:
                k_rot = _elastic_rotational_stiffness(project, el, layout.clear_length)
                if k_rot is None:
                    raise ValueError(
                        f"Element {el.id}: releasing {', '.join(release.released)} at end {end} "
                        "of a fibre member whose local axes are skewed to the global axes cannot "
                        "be modelled exactly. Release torsion at that end too (a pin), or "
                        "use an elastic section."
                    )
                for d in kept:
                    dirs.append(_ZERO_LENGTH_DIR[d])
                    stiffness.append(PENALTY_FACTOR * k_rot)
                kept_dofs = ()
            plan.equal_dofs.append((base, inner.tag, (*translations, *kept_dofs)))
            for d in release.released:
                if release.spring(d) > 0.0:
                    dirs.append(_ZERO_LENGTH_DIR[d])
                    stiffness.append(release.spring(d))
            if dirs:
                plan.springs.append(
                    _spring_link(
                        layout, base, inner.tag, dirs, stiffness, element_tags, material_tags
                    )
                )
            unstiffened = _unstiffened(layout, release)
            if not layout.has_offset(end) and unstiffened is not None:
                plan.released_dofs[(el.id, end)] = unstiffened
        member.nodes = (nodes[0], nodes[1])
    return plan


def _spring_link(
    layout: MemberLayout,
    node_a: int,
    node_b: int,
    dirs: list[int],
    stiffness: list[float],
    element_tags: _Tags,
    material_tags: _Tags,
) -> SpringLink:
    """A ``zeroLength`` along the member's local axes, its directions in ascending order."""
    order = np.argsort(dirs)
    return SpringLink(
        tag=element_tags.take(),
        node_a=node_a,
        node_b=node_b,
        dirs=tuple(dirs[n] for n in order),
        material_tags=tuple(material_tags.take() for _ in dirs),
        stiffnesses=tuple(stiffness[n] for n in order),
        orient=(*(float(v) for v in layout.x), *(float(v) for v in layout.y)),
    )


def _plan_penalty_end(
    project: Project,
    el: Any,
    layout: MemberLayout,
    end: str,
    joint: int,
    kept: list[str],
    plan: FramePlan,
    node_tags: _Tags,
    element_tags: _Tags,
    material_tags: _Tags,
) -> int:
    """Hang a released end at a diaphragm joint off a hidden node held by penalty springs.

    Returns the hidden node's tag. The ``zeroLength`` carries the end's force
    into the joint, so the hidden node is not one whose reaction is folded back.
    """
    release = el.releases.end(end)
    where = f"Element {el.id}: the release at end {end} (joint {joint}, which a rigid diaphragm "
    if layout.has_offset(end):
        raise ValueError(
            where + "constrains) is at the face of a rigid end zone, and OpenSees cannot tie that "
            "face to a diaphragm joint exactly. Use a full release (no partial fixity) on an "
            "elasticBeamColumn with an elastic section and only full-length uniform loads, "
            "remove the end offset, or take the joint out of the diaphragm."
        )
    stiffness = _elastic_stiffness(project, el, layout.clear_length)
    if stiffness is None:
        raise ValueError(
            where + "constrains) is on a fibre member, which has no elastic stiffness to scale "
            "the springs that tie it to the joint. Use an elastic section, or take the joint out "
            "of the diaphragm."
        )
    k_t, k_r = (DIAPHRAGM_PENALTY_FACTOR * v for v in stiffness)
    joint_xyz = layout.joint_i if end == "i" else layout.joint_j
    inner = ExtraNode(node_tags.take(), tuple(float(v) for v in joint_xyz[: layout.ndm]), joint)
    plan.nodes.append(inner)
    dirs = [1, 2, 3]
    values = [k_t, k_t, k_t]
    for d in kept:
        dirs.append(_ZERO_LENGTH_DIR[d])
        values.append(k_r)
    for d in release.released:
        if d not in kept and release.spring(d) > 0.0:
            dirs.append(_ZERO_LENGTH_DIR[d])
            values.append(release.spring(d))
    plan.springs.append(
        _spring_link(layout, joint, inner.tag, dirs, values, element_tags, material_tags)
    )
    return inner.tag


def _plan_modifiers(
    project: Project,
    el: Any,
    member: MemberPlan,
    derived: dict[tuple[Any, ...], int],
    section_tags: _Tags,
    plan: FramePlan,
    torsion_free: bool = False,
) -> None:
    mods = el.modifiers
    if isinstance(el, ElasticBeamColumn) and mods.mass != 1.0:
        member.rho = el.rho * mods.mass
    if not mods.scales_stiffness and not torsion_free:
        return
    if isinstance(el, BeamWithHingesElement):
        member.inline = {
            "A": el.A * mods.area,
            "Iz": el.Iz * mods.i33,
            **({"Iy": el.Iy * mods.i22} if el.Iy is not None else {}),
            **({"J": el.J * mods.torsion} if el.J is not None else {}),
        }
        return
    section = next((s for s in project.sections if s.id == el.section_id), None)
    if not isinstance(section, ElasticSection):
        raise ValueError(
            f"Element {el.id}: property modifiers on A, J, I22 or I33 need an elastic section; "
            f"section {el.section_id} is a {type(section).__name__}. Scale the fibre section "
            "itself, or reset those modifiers to 1."
        )
    if project.ndm == 2:
        args: tuple[Any, ...] = (section.E, section.A * mods.area, section.Iz * mods.i33)
    else:
        if section.Iy is None or section.G is None or section.J is None:
            raise ValueError(f"ElasticSection {section.id} needs Iy, G, J for 3D models.")
        args = (
            section.E,
            section.A * mods.area,
            section.Iz * mods.i33,
            section.Iy * mods.i22,
            section.G,
            0.0 if torsion_free else section.J * mods.torsion,
        )
    key = (section.id, args)
    if key not in derived:
        derived[key] = section_tags.take()
        plan.sections.append(DerivedSection(derived[key], args))
    member.section_id = derived[key]
