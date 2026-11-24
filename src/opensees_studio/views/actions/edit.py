"""Edit menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

_SELECTION = Needs.PROJECT | Needs.SELECTION

EDIT_ACTIONS: tuple[ActionSpec, ...] = (
    # A text field with focus keeps Ctrl+C / Ctrl+V for itself (Qt's shortcut
    # override), so these act on the model only when the viewport has focus.
    ActionSpec("edit.copy", "&Copy", "transforms.copy", shortcut="std:Copy", needs=_SELECTION),
    # Enabled while the clipboard still holds objects of this project: the window sets it.
    ActionSpec("edit.paste", "&Paste…", "transforms.paste", shortcut="std:Paste", needs=None),
    ActionSpec("edit.move", "&Move…", "transforms.move", shortcut="Ctrl+M", needs=_SELECTION),
    ActionSpec(
        "edit.replicate",
        "&Replicate…",
        "transforms.replicate",
        shortcut="Ctrl+Shift+R",
        needs=_SELECTION,
    ),
    ActionSpec("edit.mirror", "Mirr&or…", "transforms.mirror", needs=_SELECTION),
    ActionSpec("edit.extrude", "E&xtrude…", "transforms.extrude", needs=_SELECTION),
    ActionSpec("edit.delete_loads", "Delete &Loads…", "loads.delete_loads", needs=Needs.PROJECT),
)
