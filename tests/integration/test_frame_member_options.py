"""Frame end releases, end offsets, insertion points, modifiers and trapezoidal loads.

Every case is solved by OpenSees and checked against the closed form:

* a fixed-fixed beam with M3 released at end j is a propped cantilever:
  ``M_i = w L² / 8``, ``R_j = 3 w L / 8``; a partial-fixity spring ``k`` at that
  end carries ``M_j = k θ`` with ``θ = (w L² / 12) / (4 E I / L + k)``;
* a fixed-fixed beam with rigid end zones has the fixed-end forces of its clear
  span, and its joints also take the load on the rigid zones;
* a triangular load gives the fixed-end moments ``w0 L² / 30`` and
  ``w0 L² / 20``;
* an I33 modifier of 0.35 makes a cantilever 1 / 0.35 times as flexible.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")

from opensees_studio.core import (
    DispBeamColumn,
    ElasticBeamColumn,
    ElasticSection,
    EndRelease,
    ForceBeamColumn,
    FrameEndOffsets,
    FrameInsertion,
    FrameModifiers,
    FrameReleases,
    LinearTimeSeries,
    ModalCase,
    NodalLoad,
    Node,
    PlainLoadPattern,
    Project,
    StaticCase,
    TrapezoidalElementLoad,
    UniformElementLoad,
)
from opensees_studio.services.opensees_runner import OpenSeesRunner

E = 2.0e8
A = 0.02
I_SEC = 2.0e-4
L = 6.0
W = 10.0
FRAMES = [ElasticBeamColumn, ForceBeamColumn, DispBeamColumn]

FIXED_2D = (True, True, False, False, False, True)
FIXED_3D = (True,) * 6


def _section() -> ElasticSection:
    return ElasticSection(id=1, E=E, A=A, Iz=I_SEC, Iy=I_SEC, G=8e7, J=3e-4)


def _project(
    elements: list,
    nodes: list[Node],
    *,
    ndm: int = 2,
    pattern: PlainLoadPattern | None = None,
) -> Project:
    pattern = pattern or PlainLoadPattern(id=1, time_series_id=1)
    return Project(
        ndm=ndm,
        ndf=3 if ndm == 2 else 6,
        nodes=nodes,
        sections=[_section()],
        elements=elements,
        time_series=[LinearTimeSeries(id=1)],
        load_patterns=[pattern],
        analyses=[StaticCase(id=1, name="static", n_steps=1, pattern_ids=[1])],
    )


def _fixed_fixed(element: object, *, length: float = L, ndm: int = 2, **pattern) -> Project:  # type: ignore[no-untyped-def]
    fixed = FIXED_2D if ndm == 2 else FIXED_3D
    # End j slides axially (nothing loads it that way), so the model has a free DOF.
    sliding = (False, *fixed[1:])
    return _project(
        [element],
        [
            Node(id=1, coords=(0.0, 0.0, 0.0), restraint=fixed),
            Node(id=2, coords=(length, 0.0, 0.0), restraint=sliding),
        ],
        ndm=ndm,
        pattern=PlainLoadPattern(id=1, time_series_id=1, **pattern),
    )


def _solve(project: Project, tmp_path: Path):  # type: ignore[no-untyped-def]
    return OpenSeesRunner(project).run(project.analyses[0], results_dir=tmp_path)


def _released_j(**extra) -> FrameReleases:  # type: ignore[no-untyped-def]
    return FrameReleases(j=EndRelease(released=("M3",), **extra))


# ──────────────────────────── releases ────────────────────────────
@pytest.mark.parametrize("element_cls", FRAMES)
def test_a_moment_release_makes_a_propped_cantilever(element_cls: type, tmp_path: Path) -> None:
    element = element_cls(id=1, nodes=(1, 2), section_id=1, releases=_released_j())
    project = _fixed_fixed(element, element_loads=[UniformElementLoad(element_id=1, wy=-W)])

    results = _solve(project, tmp_path)

    forces = results.element_forces[1][0]
    assert abs(forces[2]) == pytest.approx(W * L**2 / 8, rel=1e-6)
    assert forces[5] == pytest.approx(0.0, abs=1e-6 * W * L**2)
    # The joint's reaction includes what reaches it through the release.
    assert results.node_reaction[2][0][1] == pytest.approx(3 * W * L / 8, rel=1e-6)
    assert results.node_reaction[2][0][2] == pytest.approx(0.0, abs=1e-6 * W * L**2)
    assert results.node_reaction[1][0][1] == pytest.approx(5 * W * L / 8, rel=1e-6)


def test_a_partial_fixity_spring_carries_k_theta(tmp_path: Path) -> None:
    k = 4 * E * I_SEC / L  # as stiff as the member itself
    element = ElasticBeamColumn(
        id=1, nodes=(1, 2), section_id=1, releases=_released_j(springs={"M3": k})
    )
    project = _fixed_fixed(element, element_loads=[UniformElementLoad(element_id=1, wy=-W)])

    results = _solve(project, tmp_path)

    theta = (W * L**2 / 12) / (4 * E * I_SEC / L + k)
    forces = results.element_forces[1][0]
    assert abs(forces[5]) == pytest.approx(k * theta, rel=1e-6)
    assert abs(forces[2]) == pytest.approx(W * L**2 / 12 + 2 * E * I_SEC / L * theta, rel=1e-6)
    assert abs(results.node_reaction[2][0][2]) == pytest.approx(k * theta, rel=1e-6)


def test_a_3d_release_about_local_y_under_gravity(tmp_path: Path) -> None:
    # A beam along X: gravity (-Z) is local z and bends it about local y (M2).
    element = ElasticBeamColumn(
        id=1, nodes=(1, 2), section_id=1, releases=FrameReleases(j=EndRelease(released=("M2",)))
    )
    project = _fixed_fixed(element, ndm=3, element_loads=[UniformElementLoad(element_id=1, wz=-W)])

    results = _solve(project, tmp_path)

    forces = results.element_forces[1][0]
    assert abs(forces[4]) == pytest.approx(W * L**2 / 8, rel=1e-6)
    assert forces[10] == pytest.approx(0.0, abs=1e-6 * W * L**2)
    assert results.node_reaction[2][0][2] == pytest.approx(3 * W * L / 8, rel=1e-6)


def test_a_torsion_release_sends_the_torque_down_the_other_member(tmp_path: Path) -> None:
    # Two members along X meet at node 2; a torque there goes all into member 1
    # when member 2 releases torsion at node 2.
    torque = 5.0
    elements = [
        ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1),
        ElasticBeamColumn(
            id=2, nodes=(2, 3), section_id=1, releases=FrameReleases(i=EndRelease(released=("T",)))
        ),
    ]
    nodes = [
        Node(id=1, coords=(0.0, 0.0, 0.0), restraint=FIXED_3D),
        Node(id=2, coords=(L, 0.0, 0.0)),
        Node(id=3, coords=(2 * L, 0.0, 0.0), restraint=FIXED_3D),
    ]
    load = NodalLoad(node_id=2, forces=(0.0, 0.0, 0.0, torque, 0.0, 0.0))
    project = _project(
        elements, nodes, ndm=3, pattern=PlainLoadPattern(id=1, time_series_id=1, nodal_loads=[load])
    )

    results = _solve(project, tmp_path)

    assert results.node_reaction[1][0][3] == pytest.approx(-torque, rel=1e-6)
    assert results.node_reaction[3][0][3] == pytest.approx(0.0, abs=1e-9)


def test_a_skewed_pinned_member_matches_the_aligned_one(tmp_path: Path) -> None:
    # Releasing M2 and M3 but keeping torsion on a member that is not along a
    # global axis takes the penalty spring; it must match the same member along X.
    def reaction(direction: np.ndarray, sub: str) -> float:
        end = L * direction
        element = ElasticBeamColumn(
            id=1,
            nodes=(1, 2),
            section_id=1,
            releases=FrameReleases(j=EndRelease(released=("M2", "M3"))),
        )
        project = _project(
            [element],
            [
                Node(id=1, coords=(0.0, 0.0, 0.0), restraint=FIXED_3D),
                Node(id=2, coords=tuple(end), restraint=FIXED_3D),
            ],
            ndm=3,
            pattern=PlainLoadPattern(
                id=1, time_series_id=1, element_loads=[UniformElementLoad(element_id=1, wz=-W)]
            ),
        )
        results = _solve(project, tmp_path / sub)
        return float(results.node_reaction[2][0][2])

    aligned = reaction(np.array([1.0, 0.0, 0.0]), "aligned")
    skewed = reaction(np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0), "skewed")
    assert aligned == pytest.approx(3 * W * L / 8, rel=1e-6)
    assert skewed == pytest.approx(aligned, rel=1e-6)


# ──────────────────────────── end offsets ────────────────────────────
@pytest.mark.parametrize("factor", [1.0, 0.5])
def test_rigid_end_zones_shorten_the_span(factor: float, tmp_path: Path) -> None:
    offset = 0.6
    element = ElasticBeamColumn(
        id=1,
        nodes=(1, 2),
        section_id=1,
        end_offsets=FrameEndOffsets(length_i=offset, length_j=offset, rigid_factor=factor),
    )
    project = _fixed_fixed(element, element_loads=[UniformElementLoad(element_id=1, wy=-W)])

    results = _solve(project, tmp_path)

    rigid = factor * offset
    clear = L - 2 * rigid
    forces = results.element_forces[1][0]
    assert abs(forces[2]) == pytest.approx(W * clear**2 / 12, rel=1e-6)
    assert abs(forces[1]) == pytest.approx(W * clear / 2, rel=1e-6)
    # The joints take the whole load, and the moment of the clear-span shear
    # and of the load on the rigid zone about the joint.
    assert results.node_reaction[1][0][1] == pytest.approx(W * L / 2, rel=1e-6)
    joint_moment = W * clear**2 / 12 + W * clear / 2 * rigid + W * rigid**2 / 2
    assert abs(results.node_reaction[1][0][2]) == pytest.approx(joint_moment, rel=1e-6)


def test_a_release_at_an_offset_end_acts_at_the_face(tmp_path: Path) -> None:
    offset = 0.5
    element = ElasticBeamColumn(
        id=1,
        nodes=(1, 2),
        section_id=1,
        end_offsets=FrameEndOffsets(length_i=offset, length_j=offset),
        releases=_released_j(),
    )
    project = _fixed_fixed(element, element_loads=[UniformElementLoad(element_id=1, wy=-W)])

    results = _solve(project, tmp_path)

    clear = L - 2 * offset
    forces = results.element_forces[1][0]
    assert abs(forces[2]) == pytest.approx(W * clear**2 / 8, rel=1e-6)
    assert forces[5] == pytest.approx(0.0, abs=1e-6 * W * L**2)
    shear_j = 3 * W * clear / 8
    assert results.node_reaction[2][0][1] == pytest.approx(shear_j + W * offset, rel=1e-6)
    assert abs(results.node_reaction[2][0][2]) == pytest.approx(
        shear_j * offset + W * offset**2 / 2, rel=1e-6
    )


def test_a_top_of_beam_insertion_point_makes_an_axial_load_eccentric(tmp_path: Path) -> None:
    # Cardinal point 8 puts the top of the section on the joints: the axis is
    # half a depth below them, so an axial load at the tip bends the member.
    load = 100.0
    depth = np.sqrt(12 * I_SEC / A)
    element = ElasticBeamColumn(
        id=1, nodes=(1, 2), section_id=1, insertion=FrameInsertion(cardinal_point=8)
    )
    project = _project(
        [element],
        [Node(id=1, coords=(0.0, 0.0, 0.0), restraint=FIXED_2D), Node(id=2, coords=(L, 0.0, 0.0))],
        pattern=PlainLoadPattern(
            id=1,
            time_series_id=1,
            nodal_loads=[NodalLoad(node_id=2, forces=(load, 0.0, 0.0, 0.0, 0.0, 0.0))],
        ),
    )

    results = _solve(project, tmp_path)

    forces = results.element_forces[1][0]
    assert abs(forces[2]) == pytest.approx(load * depth / 2, rel=1e-6)
    assert abs(forces[5]) == pytest.approx(load * depth / 2, rel=1e-6)
    assert results.node_reaction[1][0][2] == pytest.approx(0.0, abs=1e-6 * load * depth)


# ──────────────────────────── trapezoidal loads ────────────────────────────
@pytest.mark.parametrize("element_cls", FRAMES)
@pytest.mark.parametrize("ndm", [2, 3])
def test_triangular_load_fixed_end_moments(element_cls: type, ndm: int, tmp_path: Path) -> None:
    w0 = 12.0
    if ndm == 2:
        load = TrapezoidalElementLoad(element_id=1, wy_start=0.0, wy_end=-w0)
    else:
        load = TrapezoidalElementLoad(element_id=1, wz_start=0.0, wz_end=-w0)
    element = element_cls(id=1, nodes=(1, 2), section_id=1)
    project = _fixed_fixed(element, ndm=ndm, distributed_loads=[load])

    results = _solve(project, tmp_path)

    vertical = 1 if ndm == 2 else 2
    moment = 2 if ndm == 2 else 4
    assert results.node_reaction[1][0][vertical] == pytest.approx(3 * w0 * L / 20, rel=1e-6)
    assert results.node_reaction[2][0][vertical] == pytest.approx(7 * w0 * L / 20, rel=1e-6)
    assert abs(results.node_reaction[1][0][moment]) == pytest.approx(w0 * L**2 / 30, rel=1e-6)
    assert abs(results.node_reaction[2][0][moment]) == pytest.approx(w0 * L**2 / 20, rel=1e-6)


@pytest.mark.parametrize("element_cls", FRAMES)
def test_a_partial_load_on_a_simple_beam_follows_statics(element_cls: type, tmp_path: Path) -> None:
    # Load from 0.25 L to 0.75 L rising from w to 3 w: total 2 w (L/2),
    # centroid at L/2 + (L/2)(2*3+1)/(3*4) - L/4 = 0.541666 L... by statics.
    a, b, wa, wb = 0.25, 0.75, -W, -3 * W
    element = element_cls(id=1, nodes=(1, 2), section_id=1)
    project = _project(
        [element],
        [
            Node(id=1, coords=(0.0, 0.0, 0.0), restraint=(True, True, False, False, False, False)),
            Node(id=2, coords=(L, 0.0, 0.0), restraint=(False, True, False, False, False, False)),
        ],
        pattern=PlainLoadPattern(
            id=1,
            time_series_id=1,
            distributed_loads=[
                TrapezoidalElementLoad(element_id=1, x_start=a, x_end=b, wy_start=wa, wy_end=wb)
            ],
        ),
    )

    results = _solve(project, tmp_path)

    span = (b - a) * L
    total = -(wa + wb) / 2 * span
    centroid = a * L + span * (wa + 2 * wb) / (3 * (wa + wb))
    assert results.node_reaction[2][0][1] == pytest.approx(total * centroid / L, rel=1e-6)
    assert results.node_reaction[1][0][1] == pytest.approx(total * (L - centroid) / L, rel=1e-6)


def test_a_load_on_a_rigid_zone_goes_to_the_joint(tmp_path: Path) -> None:
    # A point load inside the rigid zone of a cantilever's root: nothing reaches
    # the flexible part, the support takes it directly.
    element = ElasticBeamColumn(
        id=1, nodes=(1, 2), section_id=1, end_offsets=FrameEndOffsets(length_i=1.0)
    )
    project = _project(
        [element],
        [Node(id=1, coords=(0.0, 0.0, 0.0), restraint=FIXED_2D), Node(id=2, coords=(L, 0.0, 0.0))],
        pattern=PlainLoadPattern(
            id=1,
            time_series_id=1,
            distributed_loads=[
                TrapezoidalElementLoad(element_id=1, x_end=0.1, wy_start=-W, wy_end=-W)
            ],
        ),
    )

    results = _solve(project, tmp_path)

    span = 0.1 * L
    assert results.node_reaction[1][0][1] == pytest.approx(W * span, rel=1e-6)
    assert results.node_reaction[1][0][2] == pytest.approx(W * span**2 / 2, rel=1e-6)
    assert np.allclose(results.element_forces[1][0], 0.0, atol=1e-9)


# ──────────────────────────── modifiers ────────────────────────────
@pytest.mark.parametrize("element_cls", FRAMES)
def test_a_cracked_section_modifier_softens_the_member(element_cls: type, tmp_path: Path) -> None:
    tip = 1.0
    element = element_cls(id=1, nodes=(1, 2), section_id=1, modifiers=FrameModifiers(i33=0.35))
    project = _project(
        [element],
        [Node(id=1, coords=(0.0, 0.0, 0.0), restraint=FIXED_2D), Node(id=2, coords=(L, 0.0, 0.0))],
        pattern=PlainLoadPattern(
            id=1,
            time_series_id=1,
            nodal_loads=[NodalLoad(node_id=2, forces=(0.0, -tip, 0.0, 0.0, 0.0, 0.0))],
        ),
    )

    results = _solve(project, tmp_path)

    assert results.node_disp[2][0][1] == pytest.approx(
        -tip * L**3 / (3 * E * 0.35 * I_SEC), rel=1e-6
    )


def test_the_weight_modifier_scales_the_self_weight(tmp_path: Path) -> None:
    element = ElasticBeamColumn(
        id=1, nodes=(1, 2), section_id=1, modifiers=FrameModifiers(weight=0.5)
    )
    project = _fixed_fixed(element, self_weight=1.0)
    project.sections[0] = project.sections[0].model_copy(update={"unit_weight": 25.0})

    results = _solve(project, tmp_path)

    assert results.node_reaction[1][0][1] == pytest.approx(0.5 * 25.0 * A * L / 2, rel=1e-6)


# ──────────────────────────── modal ────────────────────────────
def test_a_modal_run_with_releases_and_offsets(tmp_path: Path) -> None:
    # A simply supported beam built from a fixed-fixed one by releasing M3 at
    # both ends: its first frequency is (pi / L)^2 sqrt(E I / m).
    m = 50.0
    n = 8
    nodes = [Node(id=k + 1, coords=(L * k / n, 0.0, 0.0)) for k in range(n + 1)]
    nodes[0] = nodes[0].model_copy(update={"restraint": FIXED_2D})
    nodes[-1] = nodes[-1].model_copy(update={"restraint": FIXED_2D})
    elements = [
        ElasticBeamColumn(id=k + 1, nodes=(k + 1, k + 2), section_id=1, rho=m, consistent_mass=True)
        for k in range(n)
    ]
    elements[0] = elements[0].model_copy(
        update={"releases": FrameReleases(i=EndRelease(released=("M3",)))}
    )
    elements[-1] = elements[-1].model_copy(update={"releases": _released_j()})
    project = _project(elements, nodes)
    project.analyses[:] = [ModalCase(id=1, name="modal", n_modes=1)]

    results = OpenSeesRunner(project).run(project.analyses[0], results_dir=tmp_path)

    omega = (np.pi / L) ** 2 * np.sqrt(E * I_SEC / m)
    assert np.sqrt(results.eigenvalues[0]) == pytest.approx(omega, rel=1e-3)
