"""The window's commands, declared once (see :mod:`.spec`).

This package's ``__init__`` and the spec tables import no Qt, so a unit test
can check them; :mod:`.registry` is the part that builds ``QAction`` objects.
"""

from __future__ import annotations

from opensees_studio.views.actions.assign import ASSIGN_ACTIONS
from opensees_studio.views.actions.define import DEFINE_ACTIONS
from opensees_studio.views.actions.design import DESIGN_ACTIONS
from opensees_studio.views.actions.display import DISPLAY_ACTIONS
from opensees_studio.views.actions.edit import EDIT_ACTIONS
from opensees_studio.views.actions.file import FILE_ACTIONS
from opensees_studio.views.actions.options import OPTIONS_ACTIONS
from opensees_studio.views.actions.select import SELECT_ACTIONS
from opensees_studio.views.actions.spec import ActionSpec, ActionState, Needs
from opensees_studio.views.actions.view import VIEW_ACTIONS

#: Every declared command, in the order the areas were migrated.
ALL_ACTIONS: tuple[ActionSpec, ...] = (
    *FILE_ACTIONS,
    *EDIT_ACTIONS,
    *DEFINE_ACTIONS,
    *ASSIGN_ACTIONS,
    *DESIGN_ACTIONS,
    *SELECT_ACTIONS,
    *VIEW_ACTIONS,
    *DISPLAY_ACTIONS,
    *OPTIONS_ACTIONS,
)

__all__ = ["ALL_ACTIONS", "ActionSpec", "ActionState", "Needs"]
