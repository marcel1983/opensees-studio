"""Display menu commands: the post-processing views (``DisplayController``)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec


def _view(name: str, text: str, *, shortcut: str | None = None) -> ActionSpec:
    """A view of the results on screen.

    Which results it needs is not a ``Needs`` flag (a static case, a modal one,
    a transient one…): the window enables it from the results on screen.
    """
    return ActionSpec(f"display.{name}", text, f"display.{name}", shortcut=shortcut, needs=None)


DISPLAY_ACTIONS: tuple[ActionSpec, ...] = (
    _view("show_deformed", "Show &Deformed Shape"),
    _view("show_mode_shape", "&Animate Mode Shape"),
    _view("show_force_diagram", "Show &Force Diagram…"),
    _view("shell_contours", "Show Shell &Contours…"),
    _view("show_time_history", "&Time-History Plot…"),
    _view("export_th_animation", "Export Time-History &Animation…"),
    _view("show_hysteresis", "&Hysteresis Plot…"),
    _view("show_pushover", "Show &Pushover Curve…"),
    _view("influence_line", "&Influence Line…"),
    _view("show_response_spectrum", "Show &Response Spectrum…"),
    # Enabled while a view's dock is open.
    _view("back_to_model", "Back to &Model View", shortcut="Ctrl+Shift+B"),
)
