"""Area loads: shell pressure, floor panels to frames, imposed displacements (pure core)."""

from __future__ import annotations

import itertools
import json
import math

import numpy as np
import pytest

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticMembranePlateSection,
    ElasticSection,
    FloorLoad,
    ImposedDisplacement,
    LinearTimeSeries,
    Node,
    PlainLoadPattern,
    Project,
    ShellMITC4Element,
    SurfaceLoad,
)
from opensees_studio.core.area_loads import (
    AreaLoadError,
    _edge_members,
    _frames,
    edge_profile,
    floor_area,
    floor_member_loads,
    floor_panels,
    pattern_distributed_loads,
    surface_nodal_loads,
)


def _member_total(project: Project, loads) -> float:  # type: ignore[no-untyped-def]
    """The resultant (force) of trapezoidal member loads."""
    coords = {n.id: np.asarray(n.coords, dtype=float) for n in project.nodes}
    elements = {e.id: e for e in project.elements}
    total = 0.0
    for load in loads:
        i, j = elements[load.element_id].nodes
        length = float(np.linalg.norm(coords[j] - coords[i]))
        a = math.dist((0, 0, 0), load.start())
        b = math.dist((0, 0, 0), load.end())
        total += 0.5 * (a + b) * (load.x_end - load.x_start) * length
    return total


def _floor(lx: float = 6.0, ly: float = 4.0, split_first_beam: bool = False) -> Project:
    corners = [(0.0, 0.0), (lx, 0.0), (lx, ly), (0.0, ly)]
    nodes = [Node(id=k + 1, coords=(x, y, 3.0)) for k, (x, y) in enumerate(corners)]
    edges = [(1, 2), (2, 3), (3, 4), (4, 1)]
    if split_first_beam:
        nodes.append(Node(id=9, coords=(lx / 3, 0.0, 3.0)))
        edges = [(1, 9), (9, 2), *edges[1:]]
    elements = [ElasticBeamColumn(id=k + 1, nodes=e, section_id=1) for k, e in enumerate(edges)]
    return Project(
        ndm=3,
        ndf=6,
        nodes=nodes,
        elements=elements,
        sections=[ElasticSection(id=1, E=1.0, A=1.0, Iz=1.0, Iy=1.0, G=1.0, J=1.0)],
    )


# ─────────────────────────── floor panels ───────────────────────────
@pytest.mark.parametrize("distribution", ["two_way", "one_way_12", "one_way_23"])
@pytest.mark.parametrize("split", [False, True])
def test_a_floor_panel_hands_exactly_q_a_to_its_frames(distribution: str, split: bool) -> None:
    project = _floor(split_first_beam=split)
    load = FloorLoad(nodes=(1, 2, 3, 4), value=5.0, distribution=distribution)  # type: ignore[arg-type]
    loads = floor_member_loads(project, load)
    assert _member_total(project, loads) == pytest.approx(5.0 * floor_area(project, load))


def test_two_way_gives_trapezoids_on_long_edges_and_triangles_on_short_ones() -> None:
    assert edge_profile(6.0, 4.0, 5.0) == [
        (0.0, 2.0, 0.0, 10.0),
        (2.0, 4.0, 10.0, 10.0),
        (4.0, 6.0, 10.0, 0.0),
    ]
    assert edge_profile(4.0, 4.0, 5.0) == [(0.0, 2.0, 0.0, 10.0), (2.0, 4.0, 10.0, 0.0)]


def test_one_way_loads_only_the_edges_across_the_span() -> None:
    project = _floor()
    loads = floor_member_loads(
        project, FloorLoad(nodes=(1, 2, 3, 4), value=5.0, distribution="one_way_12")
    )
    assert {load.element_id for load in loads} == {2, 4}  # edges 2-3 and 4-1
    assert all(math.dist((0, 0, 0), load.start()) == pytest.approx(15.0) for load in loads)


def test_the_load_points_down_in_each_members_axes() -> None:
    project = _floor()
    for load in floor_member_loads(project, FloorLoad(nodes=(1, 2, 3, 4), value=5.0)):
        # Horizontal beams: gravity is -local z, nothing axial or along local y.
        assert load.wx_start == pytest.approx(0.0) and load.wy_start == pytest.approx(0.0)
        assert load.wz_start <= 0.0 and load.wz_end <= 0.0


def test_a_panel_must_be_a_horizontal_framed_rectangle() -> None:
    project = _floor()
    with pytest.raises(AreaLoadError, match="not a rectangle"):
        floor_member_loads(project, FloorLoad(nodes=(1, 3, 2, 4), value=1.0))
    project.nodes[2] = project.nodes[2].model_copy(update={"coords": (6.0, 4.0, 3.5)})
    with pytest.raises(AreaLoadError, match="not horizontal"):
        floor_member_loads(project, FloorLoad(nodes=(1, 2, 3, 4), value=1.0))
    framed = _floor()
    framed.elements = framed.elements[:3]  # edge 4-1 has no beam
    with pytest.raises(AreaLoadError, match="No frame members"):
        floor_member_loads(framed, FloorLoad(nodes=(1, 2, 3, 4), value=1.0))


def test_floor_panels_finds_each_framed_bay_once() -> None:
    project = _floor(split_first_beam=True)
    assert floor_panels(project, {1, 2, 3, 4, 9}) == [(1, 2, 3, 4)]
    assert floor_panels(project, {1, 2, 3}) == []


def _skew_building(storeys: int = 3) -> Project:
    """Two bays by two, turned 27 degrees in plan, with split beams, braces and columns."""
    turn = math.radians(27.0)

    def at(x: float, y: float, z: float) -> tuple[float, float, float]:
        return (
            x * math.cos(turn) - y * math.sin(turn),
            x * math.sin(turn) + y * math.cos(turn),
            z,
        )

    nodes: list[Node] = []
    elements: list[ElasticBeamColumn] = []
    ids: dict[tuple[float, float, int], int] = {}

    def node(x: float, y: float, k: int) -> int:
        if (x, y, k) not in ids:
            ids[x, y, k] = len(nodes) + 1
            nodes.append(Node(id=len(nodes) + 1, coords=at(x, y, 3.2 * k)))
        return ids[x, y, k]

    def member(a: int, b: int) -> None:
        elements.append(ElasticBeamColumn(id=len(elements) + 1, nodes=(a, b), section_id=1))

    xs, ys = (0.0, 5.0, 11.0), (0.0, 4.0, 8.5)
    for k in range(1, storeys + 1):
        for x in xs:
            for y in ys:
                member(node(x, y, k - 1), node(x, y, k))
        for y in ys:  # beams along X, each split in two at an uneven point
            for x0, x1 in itertools.pairwise(xs):
                middle = node(x0 + 0.37 * (x1 - x0), y, k)
                member(node(x0, y, k), middle)
                member(node(x1, y, k), middle)  # against the edge
        for x in xs:
            for y0, y1 in itertools.pairwise(ys):
                member(node(x, y0, k), node(x, y1, k))
        member(node(xs[0], ys[0], k), node(xs[1], ys[1], k))  # a brace across a bay
    return Project(
        ndm=3,
        ndf=6,
        nodes=nodes,
        elements=elements,
        sections=[ElasticSection(id=1, E=1.0, A=1.0, Iz=1.0, Iy=1.0, G=1.0, J=1.0)],
    )


def _edge_members_one_by_one(project: Project, start, end, tol: float):  # type: ignore[no-untyped-def]
    """The members on an edge, by asking every element of the model in turn."""
    coords = {n.id: np.asarray(n.coords, dtype=float) for n in project.nodes}
    length = float(np.linalg.norm(end - start))
    unit = (end - start) / length
    found = []
    for element in project.elements:
        ts = []
        for nid in element.nodes:
            rel = coords[nid] - start
            t = float(rel @ unit)
            if float(np.linalg.norm(rel - t * unit)) > tol or t < -tol or t > length + tol:
                break
            ts.append(min(max(t, 0.0), length))
        else:
            if abs(ts[1] - ts[0]) > tol:
                found.append((element.id, ts[0], ts[1]))
    return found


def test_the_members_of_an_edge_are_the_ones_a_loop_over_the_model_finds() -> None:
    """The search by level and in one pass keeps the members, their order and their numbers."""
    project = _skew_building()
    frames = _frames(project)
    coords = frames.coords
    by_place = {
        (round(float(c[0]), 6), round(float(c[1]), 6), round(float(c[2]), 6)): n
        for n, c in coords.items()
    }
    corners = [n for n in by_place.values() if coords[n][2] > 0.0]
    checked = 0
    for a in corners:
        for b in corners:
            if a == b or abs(coords[a][2] - coords[b][2]) > 1e-9:
                continue
            start, end = coords[a], coords[b]
            tol = 1e-6 * float(np.linalg.norm(end - start))
            expected = _edge_members_one_by_one(project, start, end, tol)
            try:
                found = _edge_members(frames, start, end, tol)
            except AreaLoadError:
                continue  # not framed all the way: the old loop raised here too
            assert [(e.id, ti, tj) for e, ti, tj in found] == expected
            checked += 1
    assert checked >= 100


def test_a_panel_of_a_building_gets_the_loads_of_its_own_floor() -> None:
    project = _skew_building()
    level = {n.id: round(n.coords[2] / 3.2) for n in project.nodes}
    at = {
        (round(float(n.coords[0]), 6), round(float(n.coords[1]), 6), level[n.id]): n.id
        for n in project.nodes
    }
    turn = math.radians(27.0)

    def corner(x: float, y: float, k: int) -> int:
        return at[
            round(x * math.cos(turn) - y * math.sin(turn), 6),
            round(x * math.sin(turn) + y * math.cos(turn), 6),
            k,
        ]

    xs, ys = (0.0, 5.0, 11.0), (0.0, 4.0, 8.5)
    for k in (1, 2, 3):
        on_floor = {e.id for e in project.elements if all(level[n] == k for n in e.nodes)}
        for x0, x1 in itertools.pairwise(xs):
            for y0, y1 in itertools.pairwise(ys):
                panel = (corner(x0, y0, k), corner(x1, y0, k), corner(x1, y1, k), corner(x0, y1, k))
                load = FloorLoad(nodes=panel, value=2.5)
                loads = floor_member_loads(project, load)
                assert {tl.element_id for tl in loads} <= on_floor
                assert _member_total(project, loads) == pytest.approx(
                    2.5 * floor_area(project, load)
                )


def test_the_pattern_reads_its_floor_loads_with_its_member_loads() -> None:
    project = _floor()
    pattern = PlainLoadPattern(
        id=1, time_series_id=1, floor_loads=[FloorLoad(nodes=(1, 2, 3, 4), value=2.0)]
    )
    assert _member_total(project, pattern_distributed_loads(project, pattern)) == pytest.approx(
        48.0
    )


# ─────────────────────────── shells ───────────────────────────
def _plate() -> Project:
    nodes = [
        Node(id=1, coords=(0.0, 0.0, 0.0)),
        Node(id=2, coords=(2.0, 0.0, 0.0)),
        Node(id=3, coords=(2.0, 3.0, 0.0)),
        Node(id=4, coords=(0.0, 3.0, 0.0)),
    ]
    return Project(
        ndm=3,
        ndf=6,
        nodes=nodes,
        sections=[ElasticMembranePlateSection(id=1, E=3e10, nu=0.2, h=0.2)],
        elements=[ShellMITC4Element(id=1, nodes=(1, 2, 3, 4), section_id=1)],
    )


@pytest.mark.parametrize(
    ("direction", "axis", "sign"), [("Z", 2, 1.0), ("normal", 2, 1.0), ("X", 0, 1.0)]
)
def test_a_shell_pressure_adds_up_to_value_times_area(
    direction: str, axis: int, sign: float
) -> None:
    forces = surface_nodal_loads(
        _plate(), [SurfaceLoad(element_id=1, value=-4.0, direction=direction)]
    )  # type: ignore[arg-type]
    total = sum(forces.values())
    assert total[axis] == pytest.approx(sign * -4.0 * 6.0)
    assert all(f[axis] == pytest.approx(-4.0 * 6.0 / 4) for f in forces.values())


# ─────────────────────────── the file ───────────────────────────
def test_a_pattern_without_the_new_loads_saves_as_before() -> None:
    dumped = PlainLoadPattern(id=1, time_series_id=1).model_dump(mode="json")
    for key in ("surface_loads", "floor_loads", "imposed_displacements"):
        assert key not in dumped


def test_references_of_the_new_loads_are_checked() -> None:
    project = _floor()
    project.time_series.append(LinearTimeSeries(id=1))
    project.load_patterns.append(
        PlainLoadPattern(
            id=1,
            time_series_id=1,
            surface_loads=[SurfaceLoad(element_id=1, value=1.0)],
            floor_loads=[FloorLoad(nodes=(1, 2, 3, 77), value=1.0)],
            imposed_displacements=[ImposedDisplacement(node_id=88, dof=3, value=-0.01)],
        )
    )
    with pytest.raises(ValueError) as excinfo:
        project.validate_references()
    message = str(excinfo.value)
    assert "not a shell" in message and "missing node(s) [77]" in message and "88" in message
    assert json.loads(project.model_dump_json())["load_patterns"][0]["floor_loads"]
