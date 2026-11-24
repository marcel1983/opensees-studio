"""View menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

_SELECTION = Needs.PROJECT | Needs.SELECTION


def _camera(
    name: str, text: str, shortcut: str, tooltip: str | None = None, *, legacy: str | None = None
) -> ActionSpec:
    """A command that moves the camera of the focused viewport."""
    return ActionSpec(
        f"view.{name}",
        text,
        f"viewport.{name}",
        shortcut=shortcut,
        tooltip=tooltip,
        legacy_attribute=legacy,
    )


VIEW_ACTIONS: tuple[ActionSpec, ...] = (
    _camera("iso", "&Isometric", "Ctrl+1", legacy="_act_view_iso"),
    _camera("top", "&Top (XY)", "Ctrl+2", legacy="_act_view_top"),
    _camera("front", "&Front (XZ)", "Ctrl+3", legacy="_act_view_front"),
    _camera("right", "&Right (YZ)", "Ctrl+4", legacy="_act_view_right"),
    # SAP2000's Move Up/Down in List: the next plan level or elevation line.
    # Enabled while the Level list has somewhere to go: the controller sets it.
    ActionSpec(
        "view.level_up",
        "▲ Move Up in List",
        "viewport.level_up",
        shortcut="Ctrl+Up",
        needs=None,
        tooltip="Next level up (plan) or the next grid line (elevation), showing only its objects",
    ),
    ActionSpec(
        "view.level_down",
        "▼ Move Down in List",
        "viewport.level_down",
        shortcut="Ctrl+Down",
        needs=None,
        tooltip=(
            "Next level down (plan) or the previous grid line (elevation), showing only its objects"
        ),
    ),
    # View → Rotate: the camera turns, the model does not.
    _camera(
        "rotate_left",
        "↺ Rotate Left",
        "Alt+Left",
        "Turn the view 15° to the left about the vertical axis",
    ),
    _camera(
        "rotate_right",
        "↻ Rotate Right",
        "Alt+Right",
        "Turn the view 15° to the right about the vertical axis",
    ),
    _camera("rotate_up", "⤒ Tilt Up", "Alt+Up", "Tilt the view 15° up"),
    _camera("rotate_down", "⤓ Tilt Down", "Alt+Down", "Tilt the view 15° down"),
    ActionSpec("view.grid_line_view", "Grid &Line View…", "viewport.grid_line_view"),
    # Enabled while a grid line view or a hidden set is active: the controller sets it.
    ActionSpec(
        "view.show_all_objects", "Show &All Objects", "viewport.show_all_objects", needs=None
    ),
    # Per-viewport hiding. These never touch the project: the ids stay in the
    # model, they are only not drawn in this one canvas.
    ActionSpec(
        "view.hide_selected",
        "&Hide Selected",
        "viewport.hide_selected",
        shortcut="Ctrl+H",
        needs=_SELECTION,
    ),
    ActionSpec(
        "view.isolate_selected",
        "&Isolate Selected",
        "viewport.isolate_selected",
        shortcut="Ctrl+Shift+I",
        needs=_SELECTION,
    ),
    ActionSpec(
        "view.invert_visible", "&Invert Visible", "viewport.invert_visible", needs=Needs.PROJECT
    ),
    # The six colours of the viewport (VisibilityController).
    ActionSpec("view.colors", "&Colors…", "visibility.colors", legacy_attribute="_act_view_colors"),
)
