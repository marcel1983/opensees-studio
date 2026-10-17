"""Selection recolours the node glyph in place instead of rebuilding it.

The glyph output is a materialised copy, so the states are written onto it as the
input array repeated by the glyph stride. That only works if the output keeps the
input's point order; these tests check the colour lands on the right sphere, and
that selecting does not add an actor.
"""

from __future__ import annotations

import numpy as np
from tools.render_bench import RecordingPlotter

from opensees_studio.core import Node, Project
from opensees_studio.views.canvas3d.model_renderer import ModelRenderer


def _rendered(nodes: list[Node]) -> tuple[ModelRenderer, RecordingPlotter, Project]:
    project = Project(nodes=nodes)
    plotter = RecordingPlotter()
    renderer = ModelRenderer(plotter)
    renderer.render(project)
    return renderer, plotter, project


def test_selection_colours_the_sphere_of_the_selected_node() -> None:
    nodes = [
        Node(id=1, coords=(0.0, 0.0, 0.0)),
        Node(id=2, coords=(5.0, 0.0, 0.0)),
        Node(id=3, coords=(0.0, 5.0, 0.0)),
    ]
    renderer, _plotter, project = _rendered(nodes)

    renderer.update_selection(frozenset({2}), frozenset())

    assert renderer._node_glyph is not None
    states = np.asarray(renderer._node_glyph["_oss_state"])
    points = np.asarray(renderer._node_glyph.points)
    coords = np.array([node.coords for node in project.nodes])

    # Every glyph point belongs to the nearest input node; its colour must be
    # that node's state. A stride or ordering mistake swaps a sphere's colour.
    nearest = np.argmin(np.linalg.norm(points[:, None, :] - coords[None, :, :], axis=2), axis=1)
    expected = np.isin(nearest, [1])  # node id 2 is row 1
    assert np.array_equal(states.astype(bool), expected)


def test_selecting_does_not_add_an_actor() -> None:
    renderer, plotter, _project = _rendered(
        [Node(id=1, coords=(0.0, 0.0, 0.0)), Node(id=2, coords=(5.0, 0.0, 0.0))]
    )
    actors_after_render = plotter.meshes

    renderer.update_selection(frozenset({1}), frozenset())

    assert plotter.meshes == actors_after_render, "selection must not re-add the actor"


def test_clearing_the_selection_clears_every_sphere() -> None:
    renderer, _plotter, _project = _rendered(
        [Node(id=1, coords=(0.0, 0.0, 0.0)), Node(id=2, coords=(5.0, 0.0, 0.0))]
    )
    renderer.update_selection(frozenset({1, 2}), frozenset())
    renderer.update_selection(frozenset(), frozenset())

    assert renderer._node_glyph is not None
    states = np.asarray(renderer._node_glyph["_oss_state"])
    assert not states.any()
