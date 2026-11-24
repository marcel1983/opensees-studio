"""What a parametric generator hands back: the objects a project gains.

A wizard (portal frame, truss, warehouse, a New Model template) computes its
joints, members and everything that goes with them without touching the
project. The result is a :class:`GeneratedModel`; inserting it is one step for
all of them — :func:`opensees_studio.commands.generated.insert_generated` in
the application (checked first, one undo step) or :meth:`GeneratedModel.apply`
in a script.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opensees_studio.core.geometry.grid import CoordinateGridSystem
    from opensees_studio.core.project import Project


@dataclass
class GeneratedModel:
    """Everything a project gains from one generator run; nothing is applied yet.

    The ids are the final ones: a generator asks the project for the next free
    id of each kind (``project.next_node_id()`` …) and numbers from there.
    """

    materials: list[Any] = field(default_factory=list)
    sections: list[Any] = field(default_factory=list)
    nodes: list[Any] = field(default_factory=list)
    elements: list[Any] = field(default_factory=list)
    groups: list[Any] = field(default_factory=list)
    grid: CoordinateGridSystem | None = None
    replace_grids: bool = False
    """``grid`` becomes the project's only coordinate system (a new model's
    template) instead of being added to the ones it has."""
    time_series: list[Any] = field(default_factory=list)
    patterns: list[Any] = field(default_factory=list)
    cases: list[Any] = field(default_factory=list)
    pattern_loads: list[tuple[int, str, list[Any]]] = field(default_factory=list)
    """``(pattern id, PlainLoadPattern list name, loads)`` to append."""
    combinations: list[Any] = field(default_factory=list)
    design: Any = None
    """The project's design settings as they should be, or None to leave them."""
    notes: list[str] = field(default_factory=list)
    """Lines for the log: what the generator decided on the user's behalf."""

    def apply(self, project: Project) -> None:
        """Write the model into ``project`` (headless: scripts and tests, no undo)."""
        project.materials.extend(self.materials)
        project.sections.extend(self.sections)
        project.nodes.extend(self.nodes)
        project.elements.extend(self.elements)
        project.groups.extend(self.groups)
        if self.grid is not None:
            if self.replace_grids:
                project.coord_systems[:] = [self.grid]
            else:
                project.coord_systems.append(self.grid)
        project.time_series.extend(self.time_series)
        project.load_patterns.extend(self.patterns)
        project.analyses.extend(self.cases)
        patterns = {p.id: p for p in project.load_patterns}
        for pattern_id, list_name, loads in self.pattern_loads:
            getattr(patterns[pattern_id], list_name).extend(loads)
        project.combinations.extend(self.combinations)
        if self.design is not None:
            project.design = self.design


__all__ = ["GeneratedModel"]
