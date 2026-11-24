"""How each element becomes OpenSees commands.

The runner used to carry the argument assembly of every element in one
``match`` statement; this module holds it, one emitter per element class, as
``services/material_emitters.py`` does for materials and
``services/section_emitters.py`` for sections. Adding an element is an emitter
here: the runner only asks :func:`emit_element`.

The emitters are tried in order and the first whose class matches wins, the way
the ``match`` statement they came from did.

Nothing here changed behaviour: the bodies are what was in
``OpenSeesRunner._emit_element`` and its bearing helpers, moved.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from opensees_studio.core import (
    BEARING_CLASSES,
    SLIDING_BEARING_CLASSES,
    BeamWithHingesElement,
    CorotTrussElement,
    DispBeamColumn,
    ElasticBeamColumn,
    ForceBeamColumn,
    MVLEMElement,
    Project,
    QuadElement,
    ShellDKGTElement,
    ShellMITC4Element,
    TripleFrictionPendulumElement,
    TrussElement,
    TwoNodeLinkElement,
    ZeroLengthElement,
    ZeroLengthSectionElement,
)
from opensees_studio.core.plane import to_solver_vector3
from opensees_studio.services.frame_members import FramePlan

SKIP_BEARING_ORIENT_ENV = "OPENSEES_STUDIO_TEST_SKIP_BEARING_ORIENT"
"""Tests only: ``1`` leaves ``-orient`` off bearings, so OpenSees itself hard-exits on a
zero-length bearing (a real solver crash for the crash-reporting tests)."""


@dataclass(frozen=True)
class ElementContext:
    """What an element emitter needs besides the element."""

    ops: Any
    """``openseespy.opensees``, a recorder (script export) or a mock."""
    project: Project
    frame_plan: FramePlan
    """Releases, offsets and derived sections of the frame members (``services.frame_members``)."""
    transf_tags: Mapping[int, int]
    """Frame element id → its ``geomTransf`` tag."""

    @property
    def ndm(self) -> int:
        return self.project.ndm

    def frame_nodes(self, el: Any) -> tuple[int, int]:
        """The node tags a frame's ``element`` command uses: a released end's hidden node."""
        member = self.frame_plan.members.get(el.id)
        return member.nodes if member is not None else (el.nodes[0], el.nodes[1])

    def frame_section(self, el: Any) -> int:
        """The section a frame uses: a derived section when its stiffness is modified."""
        member = self.frame_plan.members.get(el.id)
        if member is not None and member.section_id is not None:
            return member.section_id
        return int(el.section_id)


ElementEmitter = Callable[[Any, ElementContext], None]

#: ``(element classes, emitter)``, tried in order.
ELEMENT_EMITTERS: list[tuple[tuple[type, ...], ElementEmitter]] = []


def element_emitter(*classes: type) -> Callable[[ElementEmitter], ElementEmitter]:
    """Register the emitter of the elements of ``classes``."""

    def _register(func: ElementEmitter) -> ElementEmitter:
        for cls in classes:
            if any(cls in known for known, _ in ELEMENT_EMITTERS):
                raise RuntimeError(f"two emitters registered for {cls.__name__}")
        ELEMENT_EMITTERS.append((classes, func))
        return func

    return _register


def emit_element(el: Any, ctx: ElementContext) -> None:
    """Emit ``el`` into ``ctx.ops``; raise for an element with no emitter."""
    for classes, emit in ELEMENT_EMITTERS:
        if isinstance(el, classes):
            emit(el, ctx)
            return
    raise NotImplementedError(f"Element type not yet handled: {type(el).__name__}")


# ─────────────────────── trusses ───────────────────────
@element_emitter(TrussElement)
def _truss(el: TrussElement, ctx: ElementContext) -> None:
    ctx.ops.element("truss", el.id, *el.nodes, el.area, el.material_id, "-rho", el.rho)


@element_emitter(CorotTrussElement)
def _corot_truss(el: CorotTrussElement, ctx: ElementContext) -> None:
    ctx.ops.element("corotTruss", el.id, *el.nodes, el.area, el.material_id, "-rho", el.rho)


# ─────────────────────── frames ───────────────────────
@element_emitter(ElasticBeamColumn)
def _elastic_beam_column(el: ElasticBeamColumn, ctx: ElementContext) -> None:
    member = ctx.frame_plan.members.get(el.id)
    if member is not None and member.tension_only is not None:
        bar = member.tension_only
        ctx.ops.uniaxialMaterial("Elastic", bar.material_tag, bar.E, 0.0, bar.e_negative)
        ctx.ops.element("truss", el.id, *el.nodes, bar.A, bar.material_tag, "-rho", bar.rho)
        return
    tag = ctx.transf_tags[el.id]
    rho = member.rho if member is not None and member.rho is not None else el.rho
    ebc_args: list[Any] = [ctx.frame_section(el), tag, "-mass", rho]
    if el.consistent_mass:
        ebc_args.append("-cMass")
    if member is not None and member.timoshenko is not None:
        # Shear areas on the section: a Timoshenko beam (no sections, no -release).
        t_args: list[Any] = [*member.timoshenko, tag, "-mass", rho]
        if el.consistent_mass:
            t_args.append("-cMass")
        ctx.ops.element("ElasticTimoshenkoBeam", el.id, *ctx.frame_nodes(el), *t_args)
        return
    # A release at a constrained joint is condensed in the element.
    if member is not None:
        ebc_args.extend(member.release_args)
    ctx.ops.element("elasticBeamColumn", el.id, *ctx.frame_nodes(el), *ebc_args)


@element_emitter(ForceBeamColumn)
def _force_beam_column(el: ForceBeamColumn, ctx: ElementContext) -> None:
    tag = ctx.transf_tags[el.id]
    ctx.ops.beamIntegration(el.integration, el.id, ctx.frame_section(el), el.integration_points)
    ctx.ops.element(
        "forceBeamColumn",
        el.id,
        *ctx.frame_nodes(el),
        tag,
        el.id,
        "-iter",
        el.max_iter,
        el.tolerance,
    )


@element_emitter(DispBeamColumn)
def _disp_beam_column(el: DispBeamColumn, ctx: ElementContext) -> None:
    tag = ctx.transf_tags[el.id]
    ctx.ops.beamIntegration(el.integration, el.id, ctx.frame_section(el), el.integration_points)
    ctx.ops.element("dispBeamColumn", el.id, *ctx.frame_nodes(el), tag, el.id)


# ─────────────────────── links and bearings ───────────────────────
@element_emitter(ZeroLengthElement)
def _zero_length(el: ZeroLengthElement, ctx: ElementContext) -> None:
    zl_args: list[Any] = [
        "zeroLength",
        el.id,
        *el.nodes,
        "-mat",
        *el.material_ids,
        "-dir",
        *el.dofs,
    ]
    # ``-doRayleigh 1`` only when requested (default off, matching OpenSees'
    # zeroLength default), so an isolator can opt its stiffness into a
    # Kinit-proportional Rayleigh damping matrix.
    if el.do_rayleigh:
        zl_args += ["-doRayleigh", 1]
    ctx.ops.element(*zl_args)


def bearing_orient(el: Any, project: Project) -> tuple[float, ...]:
    """``(x1, x2, x3, y1, y2, y3)`` for an elastomeric or sliding bearing.

    The user's ``orient`` wins. Otherwise x is the element axis (node i
    to node j) or, for coincident nodes, the vertical (global Z; OpenSees'
    y of a 2D model, see core.plane); y is the shear direction, global X unless the axis
    is horizontal, then the horizontal perpendicular to the axis.
    OpenSees 3.8 terminates the process when a zero-length bearing has
    no -orient, so the six values are always written.
    """
    ndm = project.ndm
    if el.orient is not None:
        return (
            *to_solver_vector3(el.orient[:3], ndm),
            *to_solver_vector3(el.orient[3:6], ndm),
        )
    # Worked out in OpenSees' own frame: a 2D model's (X, Z) are its (x, y).
    pi = np.asarray(to_solver_vector3(project.node(el.nodes[0]).coords, ndm), dtype=float)
    pj = np.asarray(to_solver_vector3(project.node(el.nodes[1]).coords, ndm), dtype=float)
    if ndm == 2:
        pi[2] = pj[2] = 0.0
    axis = pj - pi
    length = float(np.linalg.norm(axis))
    up = np.array([0.0, 1.0, 0.0]) if ndm == 2 else np.array([0.0, 0.0, 1.0])
    x = axis / length if length > 1e-12 else up
    y = np.cross(up, x) if ndm == 3 else np.array([x[1], -x[0], 0.0])
    if float(np.linalg.norm(y)) < 1e-9:
        y = np.array([1.0, 0.0, 0.0])
    y = y / float(np.linalg.norm(y))
    return (*(float(v) for v in x), *(float(v) for v in y))


def bearing_args(el: Any, project: Project) -> list[Any]:
    """Argument list of ``ops.element`` for a bearing element.

    Matches the live OpenSeesPy 3.8.0 signatures::

        elastomericBearingPlasticity tag i j kInit qd alpha1 alpha2 mu
            -P p -Mz mz            (2D)
            -P p -T t -My my -Mz mz  (3D)
            -orient x1 x2 x3 y1 y2 y3 <-shearDist s> <-doRayleigh> <-mass m>
        elastomericBearingBoucWen tag i j kInit qd alpha1 alpha2 mu eta beta gamma
            ... same trailing arguments
        flatSliderBearing tag i j frnTag kInit
            ... same materials and trailing arguments, then <-iter maxIter tol>
        singleFPBearing tag i j frnTag Reff kInit
            ... same materials and trailing arguments, then <-iter maxIter tol>
    """
    args: list[Any]
    if isinstance(el, SLIDING_BEARING_CLASSES):
        if el.type == "SingleFPBearing":
            args = ["singleFPBearing", el.id, *el.nodes, el.friction_model_id, el.r_eff]
        else:
            args = ["flatSliderBearing", el.id, *el.nodes, el.friction_model_id]
        args.append(el.k_init)
    else:
        name = (
            "elastomericBearingBoucWen"
            if el.type == "ElastomericBearingBoucWen"
            else "elastomericBearingPlasticity"
        )
        args = [name, el.id, *el.nodes, el.k_init, el.qd, el.alpha1, el.alpha2, el.mu]
        if el.type == "ElastomericBearingBoucWen":
            args += [el.eta, el.beta, el.gamma]
    if project.ndm == 3:
        if el.t_material_id is None or el.my_material_id is None:
            raise ValueError(
                f"Bearing {el.id} needs T and My materials in a 3D model "
                "(t_material_id, my_material_id)."
            )
        args += [
            "-P",
            el.p_material_id,
            "-T",
            el.t_material_id,
            "-My",
            el.my_material_id,
            "-Mz",
            el.mz_material_id,
        ]
    else:
        args += ["-P", el.p_material_id, "-Mz", el.mz_material_id]
    if os.environ.get(SKIP_BEARING_ORIENT_ENV, "").strip() != "1":
        args += ["-orient", *bearing_orient(el, project)]
    if el.shear_dist != 0.5:
        args += ["-shearDist", el.shear_dist]
    if el.do_rayleigh:
        args.append("-doRayleigh")
    if el.mass > 0.0:
        args += ["-mass", el.mass]
    if isinstance(el, SLIDING_BEARING_CLASSES) and (el.max_iter != 25 or el.tol != 1e-12):
        args += ["-iter", el.max_iter, el.tol]
    return args


@element_emitter(*BEARING_CLASSES)
def _bearing(el: Any, ctx: ElementContext) -> None:
    ctx.ops.element(*bearing_args(el, ctx.project))


@element_emitter(TwoNodeLinkElement)
def _two_node_link(el: TwoNodeLinkElement, ctx: ElementContext) -> None:
    ctx.ops.element("twoNodeLink", el.id, *el.nodes, *el.opensees_args(ctx.ndm))


@element_emitter(TripleFrictionPendulumElement)
def _triple_friction_pendulum(el: TripleFrictionPendulumElement, ctx: ElementContext) -> None:
    ctx.ops.element("TripleFrictionPendulum", el.id, *el.nodes, *el.opensees_args())


# ─────────────────────── walls, sections, shells, continua ───────────────────────
@element_emitter(MVLEMElement)
def _mvlem(el: MVLEMElement, ctx: ElementContext) -> None:
    ctx.ops.element("MVLEM", el.id, *el.opensees_args())


@element_emitter(ZeroLengthSectionElement)
def _zero_length_section(el: ZeroLengthSectionElement, ctx: ElementContext) -> None:
    # element zeroLengthSection $eleTag $iNode $jNode $secTag
    ctx.ops.element("zeroLengthSection", el.id, *el.nodes, el.section_id)


@element_emitter(ShellMITC4Element)
def _shell_quad(el: ShellMITC4Element, ctx: ElementContext) -> None:
    # element ShellMITC4|ShellDKGQ|ShellNLDKGQ eleTag n1 n2 n3 n4 secTag
    ctx.ops.element(el.type, el.id, *el.nodes, el.section_id)


@element_emitter(ShellDKGTElement)
def _shell_triangle(el: ShellDKGTElement, ctx: ElementContext) -> None:
    # element ShellDKGT|ShellNLDKGT eleTag n1 n2 n3 secTag
    ctx.ops.element(el.type, el.id, *el.nodes, el.section_id)


@element_emitter(QuadElement)
def _quad(el: QuadElement, ctx: ElementContext) -> None:
    # element quad         eleTag n1 n2 n3 n4 thk type matTag <pressure rho b1 b2>
    # element bbarQuad     eleTag n1 n2 n3 n4 thk matTag
    # element enhancedQuad eleTag n1 n2 n3 n4 thk type matTag
    if el.variant == "quad":
        ctx.ops.element(
            "quad",
            el.id,
            *el.nodes,
            el.thickness,
            el.behaviour,
            el.material_id,
            el.pressure,
            el.rho,
            el.b1,
            el.b2,
        )
    elif el.variant == "bbarQuad":
        ctx.ops.element("bbarQuad", el.id, *el.nodes, el.thickness, el.material_id)
    else:  # enhancedQuad
        ctx.ops.element(
            "enhancedQuad", el.id, *el.nodes, el.thickness, el.behaviour, el.material_id
        )


@element_emitter(BeamWithHingesElement)
def _beam_with_hinges(el: BeamWithHingesElement, ctx: ElementContext) -> None:
    tag = ctx.transf_tags[el.id]
    # OpenSees 3D signature:
    #   element beamWithHinges id ni nj secI lpI secJ lpJ E A Iz Iy G J transfTag
    # 2D signature drops Iy, G, J:
    #   element beamWithHinges id ni nj secI lpI secJ lpJ E A Iz transfTag
    member = ctx.frame_plan.members.get(el.id)
    inline = member.inline if member is not None else {}
    args = [
        el.id,
        *ctx.frame_nodes(el),
        el.section_i_id,
        el.lp_i,
        el.section_j_id,
        el.lp_j,
        el.E,
        inline.get("A", el.A),
        inline.get("Iz", el.Iz),
    ]
    if ctx.ndm == 3:
        if el.Iy is None or el.G is None or el.J is None:
            raise ValueError(f"BeamWithHinges {el.id} needs Iy, G, J in 3D models.")
        args.extend([inline.get("Iy", el.Iy), el.G, inline.get("J", el.J)])
    args.append(tag)
    ctx.ops.element("beamWithHinges", *args)


__all__ = [
    "ELEMENT_EMITTERS",
    "SKIP_BEARING_ORIENT_ENV",
    "ElementContext",
    "ElementEmitter",
    "bearing_args",
    "bearing_orient",
    "element_emitter",
    "emit_element",
]
