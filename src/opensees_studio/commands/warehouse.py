"""Insert a planned warehouse (``core.warehouse.plan_warehouse``) as one undo step.

The plan is checked against the project *before* anything is pushed, and goes
in whole, as one macro, or raises without touching the project. Both come from
:mod:`opensees_studio.commands.generated`, which every generator shares; this
module only says which parts of a :class:`WarehousePlan` are which.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opensees_studio.commands.generated import insert_generated, model_problems
from opensees_studio.core.generated import GeneratedModel
from opensees_studio.core.warehouse import WarehousePlan

if TYPE_CHECKING:
    from opensees_studio.core.project import Project
    from opensees_studio.viewmodels import ProjectViewModel


def generated_model(plan: WarehousePlan) -> GeneratedModel:
    """``plan`` as the model the shared insertion takes."""
    return GeneratedModel(
        sections=plan.sections,
        nodes=plan.warehouse.nodes,
        elements=plan.warehouse.elements,
        groups=plan.groups,
        grid=plan.grid,
        time_series=plan.time_series,
        patterns=plan.patterns,
        cases=plan.cases,
        pattern_loads=plan.pattern_loads,
        combinations=plan.combinations,
        design=plan.design,
        notes=plan.notes,
    )


def plan_problems(project: Project, plan: WarehousePlan) -> list[str]:
    """Why ``plan`` cannot be inserted into ``project`` as it is; empty when it can."""
    return model_problems(project, generated_model(plan))


def insert_warehouse_plan(
    vm: ProjectViewModel, plan: WarehousePlan, *, text: str = "Create warehouse"
) -> None:
    """Push ``plan`` into the open project as one undoable macro.

    Raises:
        ValueError: when the plan does not fit the project (nothing is pushed).
    """
    insert_generated(vm, generated_model(plan), text=text)


__all__ = ["generated_model", "insert_warehouse_plan", "plan_problems"]
