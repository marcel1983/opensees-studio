"""Select-menu queries: by type, section, material, load pattern, and inversion."""

from __future__ import annotations

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    ElasticUniaxial,
    FiberSection,
    ForceBeamColumn,
    NodalLoad,
    Node,
    PlainLoadPattern,
    PointElementLoad,
    Project,
    TrussElement,
)
from opensees_studio.core import selection as q
from opensees_studio.core.sections import Fibre


def _project() -> Project:
    return Project(
        ndm=3,
        ndf=6,
        nodes=[
            Node(id=1, coords=(0, 0, 0), restraint=(True,) * 6),
            Node(id=2, coords=(4, 0, 0)),
            Node(id=3, coords=(0, 0, 3), mass=(1.0, 1.0, 1.0, 0.0, 0.0, 0.0)),
            Node(id=4, coords=(9, 9, 9)),
        ],
        materials=[ElasticUniaxial(id=1, name="steel", E=1.0), ElasticUniaxial(id=2, E=2.0)],
        sections=[
            ElasticSection(id=1, name="beam", E=1, A=1, Iz=1, Iy=1, G=1, J=1, unit_weight=1.0),
            FiberSection(id=2, name="fibre", fibres=[Fibre(y=0, z=0, area=1, material_id=2)]),
        ],
        elements=[
            ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1),
            ForceBeamColumn(id=2, nodes=(1, 3), section_id=2),
            TrussElement(id=3, nodes=(2, 3), area=1.0, material_id=1),
        ],
        load_patterns=[
            PlainLoadPattern(
                id=1,
                time_series_id=1,
                nodal_loads=[NodalLoad(node_id=3, forces=(1, 0, 0, 0, 0, 0))],
                point_loads=[PointElementLoad(element_id=3 - 1, py=1.0)],
            ),
            PlainLoadPattern(id=2, time_series_id=1, self_weight=1.0),
        ],
    )


def test_by_type() -> None:
    project = _project()
    assert q.element_types(project) == ["ElasticBeamColumn", "ForceBeamColumn", "Truss"]
    assert q.elements_of_type(project, "Truss") == {3}


def test_by_section_lists_only_used_sections() -> None:
    project = _project()
    assert [s.id for s in q.sections_in_use(project)] == [1, 2]
    assert q.elements_with_section(project, 2) == {2}


def test_by_material_reaches_through_a_fibre_section() -> None:
    project = _project()
    assert [m.id for m in q.materials_in_use(project)] == [1, 2]
    assert q.elements_with_material(project, 1) == {3}  # the truss's own material
    assert q.elements_with_material(project, 2) == {2}  # a fibre of the frame's section


def test_by_load_pattern_includes_the_self_weight() -> None:
    project = _project()
    assert q.loaded_by_pattern(project, 1) == ({3}, {2})
    assert q.loaded_by_pattern(project, 2) == (set(), {1})  # only frame 1 has a weight
    assert q.loaded_by_pattern(project, 99) == (set(), set())


def test_node_queries() -> None:
    project = _project()
    assert q.restrained_nodes(project) == {1}
    assert q.nodes_with_mass(project) == {3}
    assert q.nodes_of_elements(project, {1}) == {1, 2}
    assert q.elements_within_nodes(project, {1, 2, 3}) == {1, 2, 3}
    assert q.elements_within_nodes(project, {1, 2}) == {1}


def test_invert() -> None:
    project = _project()
    assert q.invert(project, {1, 2}, {3}) == ({3, 4}, {1, 2})
