"""The groups a generator creates: one per kind of member and section.

A wizard (the warehouse, the building) knows what each member is (a column, a
purlin, a brace). It names a group after that kind and the section the members
have, ``"Columns W14X48"``, so the design and the views can take them by
typology and by section at once. A kind whose members have two sections gets
two groups. No Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from opensees_studio.core.groups import Group


def unique_name(name: str, taken: set[str]) -> str:
    """``name``, or ``name 2``, ``name 3``… when it is taken; the result is taken then."""
    candidate, n = name, 2
    while candidate in taken:
        candidate, n = f"{name} {n}", n + 1
    taken.add(candidate)
    return candidate


def section_groups(
    members: Mapping[str, list[int]],
    *,
    elements: Iterable[Any],
    sections: Iterable[Any],
    names: Mapping[str, str],
    colours: Mapping[str, str],
    taken: set[str],
    first_id: int,
) -> list[Group]:
    """One group per kind (in the order of ``names``) and section of its members.

    ``members`` maps a kind to its element ids, ``names`` a kind to its name
    (translated by the caller), and ``taken`` holds the group names the project
    already has; it gains the new ones.
    """
    section_of = {e.id: getattr(e, "section_id", None) for e in elements}
    section_name = {s.id: s.name or f"#{s.id}" for s in sections}
    groups: list[Group] = []
    for key, base in names.items():
        by_section: dict[int | None, list[int]] = {}
        for element_id in members.get(key, ()):
            by_section.setdefault(section_of.get(element_id), []).append(element_id)
        for section_id, ids in by_section.items():
            label = section_name.get(section_id) if section_id is not None else None
            name = f"{base} {label}" if label else base
            group = Group(id=first_id + len(groups), name=unique_name(name, taken), element_ids=ids)
            if key in colours:
                group.colour = colours[key]
            groups.append(group)
    return groups


__all__ = ["section_groups", "unique_name"]
