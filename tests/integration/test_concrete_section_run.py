"""Sections from the Concrete Section Wizard solve, with the stiffness of their fibres.

A cantilever column of the wizard's fibre section under a lateral load small
enough to leave the concrete uncracked deflects ``P L³ / (3 EI)`` with
``EI = Ec Ig + Es Σ As y²`` (the bars sit on top of the concrete patches, as the
fibre section counts them). The elastic section's cracked inertia gives the same
check with ``0.70 Ig``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("openseespy")

from opensees_studio.core import (
    ElasticBeamColumn,
    ForceBeamColumn,
    LinearTimeSeries,
    NodalLoad,
    Node,
    PlainLoadPattern,
    Project,
    ProjectMeta,
    StaticCase,
)
from opensees_studio.core.sections.concrete import (
    ConcreteSectionSpec,
    bar_positions,
    build_concrete_section,
)
from opensees_studio.services.opensees_runner import OpenSeesRunner

HEIGHT = 3.0
LOAD = 1000.0  # N: a tensile stress far below the cracking stress


def _column(element_kind: str, spec: ConcreteSectionSpec) -> tuple[Project, object]:
    built = build_concrete_section(spec, material_id=1, section_id=1, elastic=True)
    section_id = 1 if element_kind == "fiber" else 2
    element = (
        ForceBeamColumn(id=1, nodes=(1, 2), section_id=section_id)
        if element_kind == "fiber"
        else ElasticBeamColumn(id=1, nodes=(1, 2), section_id=section_id)
    )
    project = Project(
        meta=ProjectMeta(),
        ndm=2,
        ndf=3,
        nodes=[
            Node(id=1, coords=(0.0, 0.0, 0.0), restraint=(True, False, True, False, True, False)),
            Node(id=2, coords=(0.0, 0.0, HEIGHT)),
        ],
        materials=list(built.materials),  # type: ignore[arg-type]
        sections=[s for s in (built.fiber, built.elastic) if s is not None],
        elements=[element],
        time_series=[LinearTimeSeries(id=1)],
        load_patterns=[
            PlainLoadPattern(
                id=1,
                time_series_id=1,
                nodal_loads=[NodalLoad(node_id=2, forces=(LOAD, 0, 0, 0, 0, 0))],
            )
        ],
        analyses=[StaticCase(id=1, name="lateral", pattern_ids=[1])],
    )
    return project, built


def _tip(project: Project) -> float:
    results = OpenSeesRunner(project).run(project.analyses[0])
    return float(results.node_disp[2][-1][0])


@pytest.mark.parametrize("shape", ["rect", "circ", "tee"])
def test_fibre_section_has_the_uncracked_stiffness(shape: str) -> None:
    spec = ConcreteSectionSpec(shape=shape, h=0.5, b=0.3, confined=False)
    project, built = _column("fiber", spec)
    props = built.properties  # type: ignore[attr-defined]
    steel = sum(spec.bar_area * (y - props.y_c) ** 2 for y, _z in bar_positions(spec))
    ei = built.Ec * props.Iz + spec.Es * steel  # type: ignore[attr-defined]
    assert _tip(project) == pytest.approx(LOAD * HEIGHT**3 / (3 * ei), rel=0.03)


def test_confined_core_solves() -> None:
    project, _built = _column("fiber", ConcreteSectionSpec())
    assert _tip(project) > 0


def test_elastic_section_uses_the_cracked_inertia() -> None:
    spec = ConcreteSectionSpec(role="column")
    project, built = _column("elastic", spec)
    ei = built.Ec * 0.70 * built.properties.Iz  # type: ignore[attr-defined]
    assert _tip(project) == pytest.approx(LOAD * HEIGHT**3 / (3 * ei), rel=1e-6)
