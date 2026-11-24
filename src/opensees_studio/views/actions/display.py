"""Display menu commands: which results are shown and the views of them.

The post-processing views are ``DisplayController``'s; the case on screen and
its reactions are ``ResultsViewController``'s; what the viewport draws of the
model is ``VisibilityController``'s.
"""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs


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
    # A combination can be shown before anything ran: picking it says what to run.
    ActionSpec(
        "display.select_results",
        "Show Results &Of…",
        "results_view.pick",
        needs=Needs.PROJECT,
    ),
    # The next three need reactions on screen: ResultsViewController enables them.
    ActionSpec(
        "display.show_reactions",
        "Show &Reactions",
        "results_view.show_reactions",
        needs=None,
        checkable=True,
    ),
    ActionSpec(
        "display.reactions_table", "Reactions &Table", "results_view.reactions_table", needs=None
    ),
    ActionSpec(
        "display.reactions_dialog", "R&eactions…", "results_view.reactions_dialog", needs=None
    ),
    # What the viewport draws of the model (VisibilityController).
    ActionSpec(
        "display.display_options",
        "Display &Options…",
        "visibility.options",
        needs=Needs.PROJECT,
    ),
    ActionSpec(
        "display.show_load_assigns",
        "Show &Load Assigns…",
        "visibility.load_assigns",
        needs=Needs.PROJECT,
        tooltip=(
            "Choose the load pattern drawn (or all, one colour each), the kinds of load "
            "and whether their values are written."
        ),
    ),
)
