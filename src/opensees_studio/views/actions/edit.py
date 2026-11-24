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
    ActionSpec(
        "edit.check_duplicates",
        "Check Model for &Duplicates…",
        "model_tools.check_duplicates",
        needs=Needs.PROJECT,
    ),
    ActionSpec(
        "edit.merge_joints", "Merge &Joints…", "model_tools.merge_joints", needs=Needs.PROJECT
    ),
    ActionSpec(
        "edit.divide_frames",
        "Divide Frames at &Joints…",
        "model_tools.divide_frames",
        needs=Needs.PROJECT,
    ),
    # Enabled with two or more members selected: the window sets it.
    ActionSpec("edit.join_frames", "Join &Frames", "model_tools.join_frames", needs=None),
    ActionSpec("edit.mesh", "&Mesh…", "model_tools.mesh", needs=Needs.PROJECT),
    ActionSpec("edit.delete_loads", "Delete &Loads…", "loads.delete_loads", needs=Needs.PROJECT),
)
