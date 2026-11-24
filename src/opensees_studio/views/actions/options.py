"""Options menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

OPTIONS_ACTIONS: tuple[ActionSpec, ...] = (
    # Ticked by ModelLockController: results lock the model, the user unlocks it.
    ActionSpec(
        "options.lock_model",
        "&Lock Model",
        "model_lock.toggle",
        needs=Needs.PROJECT,
        checkable=True,
        tooltip=(
            "Locked: the model cannot be changed without asking. It locks itself when "
            "an analysis has results; unlocking discards them."
        ),
    ),
)
