"""How each section becomes OpenSees commands.

The runner used to carry the argument assembly of every section in one method;
this module holds it, one emitter per section class, as
``services/material_emitters.py`` does for materials. Adding a section is an
emitter here: the runner only asks :func:`emit_section`.

The emitters are tried in order and the first whose class matches wins, the way
the ``match`` statement they came from did, so a subclass placed before its
parent keeps its own emitter.

Nothing here changed behaviour: the bodies are what was in
``OpenSeesRunner._emit_section``, moved.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from opensees_studio.core import (
    ElasticMembranePlateSection,
    ElasticSection,
    FiberSection,
    LayeredShellSection,
    NonprismaticSection,
    PlateFiberSection,
    SectionAggregator,
)


@dataclass(frozen=True)
class SectionContext:
    """What a section emitter needs besides the section."""

    ops: Any
    """``openseespy.opensees``, a recorder (script export) or a mock."""
    ndm: int
    fiber_torsion: Mapping[int, int]
    """Fiber section id → the torsion material of the aggregator that wraps it."""


SectionEmitter = Callable[[Any, SectionContext], None]

#: ``(section class, emitter)``, tried in order.
SECTION_EMITTERS: list[tuple[type, SectionEmitter]] = []


def section_emitter(cls: type) -> Callable[[SectionEmitter], SectionEmitter]:
    """Register the emitter of the sections of class ``cls``."""

    def _register(func: SectionEmitter) -> SectionEmitter:
        if any(known is cls for known, _ in SECTION_EMITTERS):
            raise RuntimeError(f"two emitters registered for {cls.__name__}")
        SECTION_EMITTERS.append((cls, func))
        return func

    return _register


def emit_section(sec: Any, ctx: SectionContext) -> None:
    """Emit ``sec`` into ``ctx.ops``; raise for a section with no emitter."""
    for cls, emit in SECTION_EMITTERS:
        if isinstance(sec, cls):
            emit(sec, ctx)
            return
    raise NotImplementedError(f"Section type not yet handled: {type(sec).__name__}")


@section_emitter(NonprismaticSection)
def _nonprismatic(sec: NonprismaticSection, ctx: SectionContext) -> None:
    # A library template. Members that use it are materialised as ordinary
    # elastic elements before the script is built.
    return


@section_emitter(ElasticMembranePlateSection)
def _membrane_plate(sec: ElasticMembranePlateSection, ctx: SectionContext) -> None:
    """``section ElasticMembranePlateSection tag E nu h rho``.

    The section ShellMITC4 takes. OpenSees defines it by its own (E, nu, h,
    rho), so it never references an nDMaterial.
    """
    ctx.ops.section("ElasticMembranePlateSection", sec.id, sec.E, sec.nu, sec.h, sec.rho)


@section_emitter(LayeredShellSection)
def _layered_shell(sec: LayeredShellSection, ctx: SectionContext) -> None:
    layers = [v for layer in sec.layers for v in (layer.material_id, layer.thickness)]
    ctx.ops.section("LayeredShell", sec.id, len(sec.layers), *layers)


@section_emitter(PlateFiberSection)
def _plate_fiber(sec: PlateFiberSection, ctx: SectionContext) -> None:
    ctx.ops.section("PlateFiber", sec.id, sec.material_id, sec.h)


@section_emitter(ElasticSection)
def _elastic(sec: ElasticSection, ctx: SectionContext) -> None:
    if ctx.ndm == 2:
        ctx.ops.section("Elastic", sec.id, sec.E, sec.A, sec.Iz)
    else:
        if sec.Iy is None or sec.G is None or sec.J is None:
            raise ValueError(f"ElasticSection {sec.id} needs Iy, G, J for 3D models.")
        ctx.ops.section("Elastic", sec.id, sec.E, sec.A, sec.Iz, sec.Iy, sec.G, sec.J)


@section_emitter(FiberSection)
def _fiber(sec: FiberSection, ctx: SectionContext) -> None:
    ops = ctx.ops
    if sec.GJ is not None:
        ops.section("Fiber", sec.id, "-GJ", sec.GJ)
    elif ctx.ndm == 3:
        torsion_mat = ctx.fiber_torsion.get(sec.id)
        if torsion_mat is not None:
            # FiberSection3d requires torsion. The SectionAggregator wrapping
            # this section will override T: use the same material so the
            # intent is transparent.
            ops.section("Fiber", sec.id, "-torsion", torsion_mat)
        else:
            raise ValueError(
                f"FiberSection {sec.id!r} is used in a 3D model but has no "
                "torsion defined. Either set GJ on the section or wrap it in "
                "a SectionAggregator with a T DOF pairing."
            )
    else:
        ops.section("Fiber", sec.id)
    # Patches: rectangular / circular.
    for patch in sec.patches:
        if patch.kind == "rect":
            ops.patch(
                "rect",
                patch.material_id,
                patch.n_fib_y,
                patch.n_fib_z,
                patch.y_i,
                patch.z_i,
                patch.y_j,
                patch.z_j,
            )
        elif patch.kind == "circ":
            ops.patch(
                "circ",
                patch.material_id,
                patch.n_fib_circ,
                patch.n_fib_rad,
                patch.y_center,
                patch.z_center,
                patch.r_inner,
                patch.r_outer,
                patch.start_angle,
                patch.end_angle,
            )
    # Layers: straight.
    for layer in sec.layers:
        if layer.kind == "straight":
            ops.layer(
                "straight",
                layer.material_id,
                layer.n_bars,
                layer.bar_area,
                layer.y_start,
                layer.z_start,
                layer.y_end,
                layer.z_end,
            )
    # Individual fibres (legacy / custom).
    for fb in sec.fibres:
        ops.fiber(fb.y, fb.z, fb.area, fb.material_id)


@section_emitter(SectionAggregator)
def _aggregator(sec: SectionAggregator, ctx: SectionContext) -> None:
    # section Aggregator $secTag $matTag1 $dof1 ... <-section $baseSec>
    args: list[Any] = [sec.id]
    for p in sec.pairings:
        args.extend([p.material_id, p.dof])
    if sec.section_id is not None:
        args.extend(["-section", sec.section_id])
    ctx.ops.section("Aggregator", *args)


def fiber_torsion_materials(sections: Any) -> dict[int, int]:
    """Fiber section id → the torsion material of a ``SectionAggregator`` wrapping it.

    OpenSees' FiberSection3d needs a torsion: when GJ is not set on the fiber
    section, the aggregator's T pairing supplies it.
    """
    out: dict[int, int] = {}
    for sec in sections:
        if isinstance(sec, SectionAggregator) and sec.section_id is not None:
            for pair in sec.pairings:
                if pair.dof == "T":
                    out[sec.section_id] = pair.material_id
    return out


__all__ = [
    "SECTION_EMITTERS",
    "SectionContext",
    "SectionEmitter",
    "emit_section",
    "fiber_torsion_materials",
    "section_emitter",
]
