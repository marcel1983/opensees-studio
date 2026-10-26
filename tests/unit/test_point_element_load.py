"""Point loads inside frame elements: the model, its file format and its references."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    LinearTimeSeries,
    Node,
    PlainLoadPattern,
    PointElementLoad,
    Project,
)


def test_defaults_put_the_load_at_mid_span() -> None:
    load = PointElementLoad(element_id=3, py=-10.0)
    assert (load.py, load.pz, load.px, load.x) == (-10.0, 0.0, 0.0, 0.5)


@pytest.mark.parametrize("x", [-0.01, 1.01])
def test_the_position_is_a_fraction_of_the_length(x: float) -> None:
    with pytest.raises(ValidationError):
        PointElementLoad(element_id=1, py=-1.0, x=x)


def test_a_pattern_without_point_loads_saves_as_before() -> None:
    pattern = PlainLoadPattern(id=1, time_series_id=1)
    assert "point_loads" not in pattern.model_dump()


def test_point_loads_round_trip() -> None:
    pattern = PlainLoadPattern(
        id=1,
        time_series_id=1,
        point_loads=[PointElementLoad(element_id=2, py=-5.0, pz=1.0, px=2.0, x=0.25)],
    )
    again = PlainLoadPattern.model_validate_json(pattern.model_dump_json())
    assert again.point_loads == pattern.point_loads


def _project(point_on: int) -> Project:
    return Project(
        ndm=2,
        ndf=3,
        nodes=[Node(id=1, coords=(0.0, 0.0, 0.0)), Node(id=2, coords=(4.0, 0.0, 0.0))],
        sections=[ElasticSection(id=1, name="S", E=2e8, A=0.01, Iz=1e-4)],
        elements=[ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1)],
        time_series=[LinearTimeSeries(id=1)],
        load_patterns=[
            PlainLoadPattern(
                id=1,
                time_series_id=1,
                point_loads=[PointElementLoad(element_id=point_on, py=-1.0)],
            )
        ],
    )


def test_a_point_load_on_a_missing_element_is_a_reference_error() -> None:
    _project(1).validate_references()
    with pytest.raises(ValueError, match="point load on missing element 7"):
        _project(7).validate_references()
