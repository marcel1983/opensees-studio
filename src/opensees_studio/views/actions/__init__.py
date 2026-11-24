"""The window's commands, declared once (see :mod:`.spec`).

This package's ``__init__`` and the spec tables import no Qt, so a unit test
can check them; :mod:`.registry` is the part that builds ``QAction`` objects.
"""

from __future__ import annotations

from opensees_studio.views.actions.file import FILE_ACTIONS
from opensees_studio.views.actions.spec import ActionSpec, ActionState, Needs

#: Every declared command, in the order the areas were migrated.
ALL_ACTIONS: tuple[ActionSpec, ...] = (*FILE_ACTIONS,)

__all__ = ["ALL_ACTIONS", "ActionSpec", "ActionState", "Needs"]
