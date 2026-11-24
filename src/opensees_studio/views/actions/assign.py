"""Assign menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

ASSIGN_ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        "assign.diaphragm",
        "&Diaphragm…",
        "building.assign_diaphragm",
        needs=Needs.PROJECT,
        legacy_attribute="_act_assign_diaphragm",
    ),
    # Enabled with exactly two joints selected: the window sets it.
    ActionSpec(
        "assign.rigid_link",
        "Rigid &Link…",
        "building.assign_rigid_link",
        needs=None,
        legacy_attribute="_act_assign_rigid_link",
    ),
    ActionSpec(
        "assign.remove_constraints",
        "Remove &Constraints",
        "building.remove_constraints",
        needs=Needs.PROJECT | Needs.SELECTED_NODES,
    ),
)
