"""Line-diagram geometry for distributed member loads."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pyvista")

from opensees_studio.views.canvas3d.model_renderer import distributed_load_glyphs


def test_uniform_load_has_a_shaft_and_v_head_per_station_and_one_top_line() -> None:
    bases = [np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]), np.array([2.0, 0.0, 0.0])]
    directions = [np.array([0.0, 0.0, -1.0])] * 3
    points, polylines = distributed_load_glyphs(
        bases, directions, [0.5, 0.5, 0.5], np.array([1.0, 0.0, 0.0])
    )

    # Three stations: shaft + two head strokes each, plus the top line.
    assert len(polylines) == 10
    top = polylines[-1]
    assert len(top) == 3
    np.testing.assert_allclose(
        np.asarray(points)[top],
        [[0.0, 0.0, -0.5], [1.0, 0.0, -0.5], [2.0, 0.0, -0.5]],
        atol=1e-12,
    )


def test_triangular_load_keeps_its_zero_end_on_the_top_line() -> None:
    bases = [np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]), np.array([2.0, 0.0, 0.0])]
    directions = [np.zeros(3), np.array([0.0, 0.0, -1.0]), np.array([0.0, 0.0, -1.0])]
    points, polylines = distributed_load_glyphs(
        bases, directions, [0.0, 0.5, 1.0], np.array([1.0, 0.0, 0.0])
    )

    # No shaft/head at the zero end: 3 + 3 + the top line.
    assert len(polylines) == 7
    top = np.asarray(points)[polylines[-1]]
    np.testing.assert_allclose(
        top,
        [[0.0, 0.0, 0.0], [1.0, 0.0, -0.5], [2.0, 0.0, -1.0]],
        atol=1e-12,
    )


def test_arrowheads_stay_finite_when_the_load_runs_along_the_member() -> None:
    points, polylines = distributed_load_glyphs(
        [np.array([0.0, 0.0, 0.0])],
        [np.array([1.0, 0.0, 0.0])],
        [0.5],
        np.array([1.0, 0.0, 0.0]),
    )
    assert points.size > 0
    assert np.isfinite(points).all()
    assert len(polylines) == 3  # shaft + two head strokes
