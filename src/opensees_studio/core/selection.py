"""Selection queries: which nodes and elements match a property.

The Select menu adds these to (or inverts) the current selection; the queries
themselves are pure and read only the project, so they are tested without Qt.

Materials are found wherever an element can reach them: its own material fields
(``material_id``, ``material_ids``, a bearing's ``p_material_id`` …) and those of
every section it references, followed through an aggregator's base section, so
"select by material" picks a frame whose fiber section has a fibre of it.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from opensees_studio.core.loads import PlainLoadPattern
from opensees_studio.core.project import Project
from opensees_studio.core.self_weight import is_weighted


def _ids_in(data: Any, suffix: str) -> Iterator[int]:
    """Every int stored under a key ending in ``suffix`` or ``suffix + 's'``, at any depth."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key.endswith(suffix) and isinstance(value, int):
                yield value
            elif key.endswith(suffix + "s") and isinstance(value, list | tuple):
                yield from (v for v in value if isinstance(v, int))
            else:
                yield from _ids_in(value, suffix)
    elif isinstance(data, list | tuple):
        for item in data:
            yield from _ids_in(item, suffix)


def element_section_ids(element: Any) -> set[int]:
    """Ids of the sections an element references (``section_id``, ``section_i_id`` …)."""
    return {
        value
        for key, value in element.model_dump().items()
        if key.startswith("section") and key.endswith("id") and isinstance(value, int)
    }


def _section_material_ids(project: Project, section_id: int, seen: set[int]) -> set[int]:
    if section_id in seen:
        return set()
    seen.add(section_id)
    section = next((s for s in project.sections if s.id == section_id), None)
    if section is None:
        return set()
    data = section.model_dump()
    found = set(_ids_in(data, "material_id"))
    base = data.get("section_id")
    if isinstance(base, int):
        found |= _section_material_ids(project, base, seen)
    return found


def element_material_ids(project: Project, element: Any) -> set[int]:
    """Ids of every material an element uses, directly or through its sections."""
    found = set(_ids_in(element.model_dump(), "material_id"))
    seen: set[int] = set()
    for section_id in element_section_ids(element):
        found |= _section_material_ids(project, section_id, seen)
    return found


# ──────────────────────────── element queries ────────────────────────────
def element_types(project: Project) -> list[str]:
    """The element types present in the model, sorted."""
    return sorted({element.type for element in project.elements})


def elements_of_type(project: Project, element_type: str) -> set[int]:
    return {element.id for element in project.elements if element.type == element_type}


def sections_in_use(project: Project) -> list[Any]:
    """The sections that at least one element references, in project order."""
    used: set[int] = set()
    for element in project.elements:
        used |= element_section_ids(element)
    return [section for section in project.sections if section.id in used]


def elements_with_section(project: Project, section_id: int) -> set[int]:
    return {
        element.id for element in project.elements if section_id in element_section_ids(element)
    }


def materials_in_use(project: Project) -> list[Any]:
    """The materials that at least one element uses, in project order."""
    used: set[int] = set()
    for element in project.elements:
        used |= element_material_ids(project, element)
    return [material for material in project.materials if material.id in used]


def elements_with_material(project: Project, material_id: int) -> set[int]:
    return {
        element.id
        for element in project.elements
        if material_id in element_material_ids(project, element)
    }


def weighted_elements(project: Project) -> set[int]:
    """The frames and shells that carry a self weight (section with a unit weight)."""
    return {element.id for element in project.elements if is_weighted(project, element)}


# ──────────────────────────── node queries ────────────────────────────
def restrained_nodes(project: Project) -> set[int]:
    """Nodes with at least one restrained DOF (the supports)."""
    return {node.id for node in project.nodes if any(node.restraint)}


def nodes_with_mass(project: Project) -> set[int]:
    return {node.id for node in project.nodes if any(node.mass)}


def nodes_of_elements(project: Project, element_ids: Iterable[int]) -> set[int]:
    """Every node of the given elements."""
    wanted = set(element_ids)
    return {
        node_id for element in project.elements if element.id in wanted for node_id in element.nodes
    }


def elements_within_nodes(project: Project, node_ids: Iterable[int]) -> set[int]:
    """Elements whose every node is in ``node_ids`` (the members a node window encloses)."""
    nodes = set(node_ids)
    return {element.id for element in project.elements if all(n in nodes for n in element.nodes)}


# ──────────────────────────── load queries ────────────────────────────
def loaded_by_pattern(project: Project, pattern_id: int) -> tuple[set[int], set[int]]:
    """``(node ids, element ids)`` that a plain pattern loads.

    A self-weight pattern loads every weighted frame and shell; a support-motion pattern
    the nodes it drives.
    """
    pattern = next((p for p in project.load_patterns if p.id == pattern_id), None)
    if pattern is None:
        return set(), set()
    if not isinstance(pattern, PlainLoadPattern):
        return set(getattr(pattern, "node_ids", ())), set()
    nodes = {load.node_id for load in pattern.nodal_loads}
    elements = {load.element_id for load in pattern.element_loads}
    elements |= {load.element_id for load in pattern.point_loads}
    if pattern.self_weight:
        elements |= weighted_elements(project)
    return nodes, elements


def invert(
    project: Project, nodes: Iterable[int], elements: Iterable[int]
) -> tuple[set[int], set[int]]:
    """Everything that is not selected, and nothing that is."""
    return (
        {node.id for node in project.nodes} - set(nodes),
        {element.id for element in project.elements} - set(elements),
    )
