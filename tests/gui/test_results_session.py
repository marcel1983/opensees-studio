"""``ResultsSession`` holds the results in memory and answers for them, with no window."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")

from opensees_studio.core import (
    CombinationTerm,
    ElasticBeamColumn,
    LinearTimeSeries,
    LoadCombination,
    ModalCase,
    Node,
    PlainLoadPattern,
    Project,
    StaticCase,
)
from opensees_studio.services.element_forces import ForceComponent
from opensees_studio.services.results import ModalResults, StaticResults
from opensees_studio.viewmodels.results_session import ResultsSession, case_names

pytestmark = pytest.mark.gui


def _project() -> Project:
    """One member, two static cases, a modal case and an envelope of the two."""
    project = Project(ndm=3, ndf=6)
    project.nodes.extend([Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0))])
    project.elements.append(ElasticBeamColumn(id=10, nodes=(1, 2), section_id=1))
    project.time_series.append(LinearTimeSeries(id=1, name="Ramp"))
    project.load_patterns.extend(
        [
            PlainLoadPattern(id=1, name="DEAD", time_series_id=1),
            PlainLoadPattern(id=2, name="LIVE", time_series_id=1),
        ]
    )
    project.analyses.extend(
        [
            StaticCase(id=1, name="DEAD", pattern_ids=[1]),
            StaticCase(id=2, name="LIVE", pattern_ids=[2]),
            ModalCase(id=3, name="MODAL"),
        ]
    )
    project.combinations.append(
        LoadCombination(
            id=1,
            name="ENV",
            combination_type="Envelope",
            terms=[CombinationTerm(ref_id=1), CombinationTerm(ref_id=2)],
        )
    )
    return project


def _static(case_id: int, name: str, axial: float) -> StaticResults:
    forces = np.zeros((1, 12))
    forces[0, 0] = axial
    forces[0, 6] = -axial
    return StaticResults(
        case_id=case_id,
        case_name=name,
        n_steps=1,
        node_disp={1: np.zeros((1, 6)), 2: np.zeros((1, 6))},
        node_reaction={1: np.array([[axial, 0.0, 0.0, 0.0, 0.0, 0.0]])},
        element_forces={10: forces},
    )


def test_an_empty_session_has_nothing_to_say() -> None:
    session = ResultsSession()
    project = _project()
    assert session.latest is None
    assert session.current(project) == {} and session.current(None) == {}
    assert not session.has_any(project) and not session.has_stored(project)
    assert session.for_report(project) == [] and session.for_report(None) == []
    assert session.choices(None) == [] and session.member_choices(None) == []
    # A combination is always offered: showing it says which cases to run.
    assert session.choices(project) == [("Combination: ENV", "combination:1")]
    assert session.current_key() == ""
    assert session.static() is None and not session.is_envelope()
    assert session.steps() == 1
    assert session.reaction_rows(project) == []
    assert session.diagram_data(project, ForceComponent.N).element_ids.size == 0
    assert case_names(None) == {}
    assert case_names(project) == {1: "DEAD", 2: "LIVE", 3: "MODAL"}


def test_static_results_feed_the_combinations_and_the_rest_only_the_report() -> None:
    session = ResultsSession()
    project = _project()
    dead, live = _static(1, "DEAD", 100.0), _static(2, "LIVE", -40.0)
    modal = ModalResults(case_id=3, case_name="MODAL", eigenvalues=np.array([4.0]))
    for results in (dead, live, modal):
        session.keep(project, results)
    session.keep(None, dead)  # no project: nothing to keep it against

    assert session.current(project) == {1: dead, 2: live}
    assert list(session.extra) == [3]
    assert session.has_stored(project) and session.has_any(project)
    assert session.for_report(project) == [dead, live, modal]
    assert session.choices(project) == [
        ("Case: DEAD  [StaticResults]", "case:1"),
        ("Case: LIVE  [StaticResults]", "case:2"),
        ("Combination: ENV", "combination:1"),
    ]
    assert [key for _label, key in session.member_choices(project)] == [
        "case:1",
        "case:2",
        "combination:1",
    ]

    # An edit of the model makes every kept result stale at once.
    project.nodes[1].coords = (5, 0, 0)
    assert session.current(project) == {}
    assert session.for_report(project) == []
    assert session.has_any(project)  # the modal extras are still held
    session.clear()
    assert not session.has_any(project) and session.extra == {}


def test_the_result_on_screen_a_case_and_then_an_envelope() -> None:
    session = ResultsSession()
    project = _project()
    dead, live = _static(1, "DEAD", 100.0), _static(2, "LIVE", -40.0)
    session.keep(project, dead)
    session.keep(project, live)

    session.latest = dead
    assert session.current_key() == "case:1"
    assert session.static() is dead and not session.is_envelope()
    assert session.caption_for(project, dead) == "DEAD  ·  Static"
    # A renamed case reads by its current name; an unknown one by the results' own.
    project.analyses[0].name = "PP"
    assert session.caption_for(project, dead) == "PP  ·  Static"
    assert session.caption_for(None, dead) == "DEAD  ·  Static"
    project.analyses[0].name = "DEAD"
    assert [row.node_id for row in session.reaction_rows(project)] == [1]
    assert session.diagram_data(project, ForceComponent.N).abs_max == pytest.approx(100.0)

    envelope = session.cases.combine(project, 1)
    session.latest = envelope
    assert session.current_key() == "combination:1"
    assert session.is_envelope()
    assert session.caption_for(project, envelope) == "ENV  ·  envelope"
    assert session.static("max") is envelope.max and session.static("min") is envelope.min
    data = session.diagram_data(project, ForceComponent.N)
    assert data.element_ids.size > 0 and data.abs_max == pytest.approx(100.0)

    session.clear()
    assert session.latest is None and session.current(project) == {}
