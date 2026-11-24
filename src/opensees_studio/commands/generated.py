"""Insert a :class:`~opensees_studio.core.generated.GeneratedModel` as one undo step.

The model is checked against the project *before* anything is pushed: an error
raised inside a command's ``redo`` is lost by ``QUndoStack.push``, and a macro
that fails half way leaves its first commands in the model. So a generated
model either goes in whole, as one macro, or raises without touching the
project.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from opensees_studio.commands.analysis import AddAnalysisCasesCommand
from opensees_studio.commands.buildings import SetDesignSettingsCommand
from opensees_studio.commands.combinations import AddCombinationsCommand
from opensees_studio.commands.elements import AddElementsCommand
from opensees_studio.commands.grid import SetCoordSystemsCommand
from opensees_studio.commands.groups import SetGroupsCommand
from opensees_studio.commands.loads import AddPatternLoadsCommand
from opensees_studio.commands.materials import AddMaterialsCommand
from opensees_studio.commands.nodes import AddNodesCommand
from opensees_studio.commands.sections import AddSectionsCommand
from opensees_studio.commands.series_and_patterns import (
    AddLoadPatternCommand,
    AddTimeSeriesCommand,
)
from opensees_studio.core.loads import PlainLoadPattern

if TYPE_CHECKING:
    from PySide6.QtGui import QUndoStack

    from opensees_studio.core.generated import GeneratedModel
    from opensees_studio.core.project import Project
    from opensees_studio.viewmodels import ProjectViewModel


def model_problems(project: Project, model: GeneratedModel) -> list[str]:
    """Why ``model`` cannot be inserted into ``project`` as it is; empty when it can."""
    problems: list[str] = []

    def clash(what: str, new: list[Any], existing: list[Any]) -> None:
        taken = {item.id for item in existing}
        ids = [item.id for item in new]
        repeated = sorted({i for i in ids if i in taken or ids.count(i) > 1})
        if repeated:
            problems.append(f"{what} id(s) already in use: {repeated[:5]}.")

    clash("Material", model.materials, project.materials)
    clash("Section", model.sections, project.sections)
    clash("Node", model.nodes, project.nodes)
    clash("Element", model.elements, project.elements)
    clash("Group", model.groups, project.groups)
    clash("Time series", model.time_series, project.time_series)
    clash("Load pattern", model.patterns, project.load_patterns)
    clash("Analysis case", model.cases, project.analyses)
    clash("Combination", model.combinations, project.combinations)

    def missing(what: str, wanted: set[int], known: set[int]) -> None:
        unknown = sorted(wanted - known)
        if unknown:
            problems.append(f"Missing {what}(s): {unknown[:5]}.")

    def referenced(attribute: str) -> set[int]:
        ids = {getattr(element, attribute, None) for element in model.elements}
        return {i for i in ids if i is not None}

    missing(
        "section",
        referenced("section_id"),
        {s.id for s in (*project.sections, *model.sections)},
    )
    missing(
        "material",
        referenced("material_id"),
        {m.id for m in (*project.materials, *model.materials)},
    )
    missing(
        "node",
        {n for element in model.elements for n in getattr(element, "nodes", ())},
        {n.id for n in (*project.nodes, *model.nodes)},
    )
    plain = {
        p.id for p in (*project.load_patterns, *model.patterns) if isinstance(p, PlainLoadPattern)
    }
    for pattern_id, list_name, _loads in model.pattern_loads:
        if pattern_id not in plain:
            problems.append(f"Load pattern {pattern_id} ({list_name}) is not a Plain pattern.")
    if (
        model.grid is not None
        and not model.replace_grids
        and any(c.name == model.grid.name for c in project.coord_systems)
    ):
        problems.append(f"A coordinate system named '{model.grid.name}' already exists.")
    return problems


def _take_back(stack: QUndoStack, index: int) -> None:
    """Undo the macro pushed at ``index`` and drop it, so no Redo offers it again.

    Qt deletes an obsolete command instead of redoing it; that is the one way
    to remove a command from a ``QUndoStack``.
    """
    if stack.index() > index:
        stack.undo()
    if stack.index() == index and stack.count() > index:
        stack.command(index).setObsolete(True)
        stack.redo()


def insert_generated(vm: ProjectViewModel, model: GeneratedModel, *, text: str) -> None:
    """Push ``model`` into the open project as one undoable macro named ``text``.

    Raises:
        ValueError: when the model does not fit the project (nothing is pushed).
        Exception: whatever a command refused with; the macro is taken back,
            so the project is as it was.
    """
    project = vm.project
    if project is None:
        raise ValueError("Open or create a project first.")
    problems = model_problems(project, model)
    if problems:
        raise ValueError(" ".join(problems))

    stack = vm.undo_stack
    index = stack.index()
    stack.beginMacro(text)
    try:
        if model.materials:
            vm.apply_command(AddMaterialsCommand(vm, model.materials))
        if model.sections:
            vm.apply_command(AddSectionsCommand(vm, model.sections))
        if model.nodes:
            vm.apply_command(AddNodesCommand(vm, model.nodes))
        if model.elements:
            vm.apply_command(AddElementsCommand(vm, model.elements))
        if model.groups:
            vm.apply_command(SetGroupsCommand(vm, [*project.groups, *model.groups]))
        if model.grid is not None:
            kept = [] if model.replace_grids else project.coord_systems
            vm.apply_command(SetCoordSystemsCommand(vm, [*kept, model.grid]))
        for series in model.time_series:
            vm.apply_command(AddTimeSeriesCommand(vm, series))
        for pattern in model.patterns:
            vm.apply_command(AddLoadPatternCommand(vm, pattern))
        if model.cases:
            vm.apply_command(AddAnalysisCasesCommand(vm, model.cases))
        for pattern_id, list_name, loads in model.pattern_loads:
            vm.apply_command(AddPatternLoadsCommand(vm, list_name, loads, pattern_id))
        if model.combinations:
            vm.apply_command(AddCombinationsCommand(vm, model.combinations))
        if model.design is not None:
            vm.apply_command(SetDesignSettingsCommand(vm, model.design))
    except Exception:
        stack.endMacro()
        _take_back(stack, index)
        raise
    stack.endMacro()


__all__ = ["insert_generated", "model_problems"]
