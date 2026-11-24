"""Select menu commands: everything, inverted, the previous one, and the queries."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs


def _query(name: str, text: str, *, needs: Needs | None = Needs.NOTHING) -> ActionSpec:
    """A query that adds what it finds to the selection (``SelectController.<name>``)."""
    return ActionSpec(
        f"select.{name}",
        text,
        f"select.{name}",
        needs=needs,
        legacy_attribute=f"_act_select_{name}",
    )


SELECT_ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        "select.all",
        "Select &all",
        "select.all_objects",
        shortcut="Ctrl+A",
        legacy_attribute="_act_select_all",
    ),
    # The Select menu enables these three when it opens (SelectController.refresh_menu).
    ActionSpec(
        "select.invert",
        "&Invert Selection",
        "select.invert",
        shortcut="Ctrl+I",
        needs=None,
        legacy_attribute="_act_invert_selection",
    ),
    _query("joints_of_elements", "Joints of Selected Elements", needs=None),
    _query("elements_within_joints", "Elements between Selected Joints", needs=None),
    # Enabled while there is a previous selection: the window sets it too, for
    # the side "ps" button.
    ActionSpec(
        "select.previous",
        "Get &Previous Selection",
        "select.previous",
        shortcut="Ctrl+P",
        needs=None,
        legacy_attribute="_act_previous_selection",
    ),
    _query("all_joints", "All &Joints"),
    _query("all_elements", "All &Elements"),
    _query("supports", "&Supported Joints"),
    _query("joints_with_mass", "Joints with &Mass"),
    _query("weighted", "Elements with Self &Weight"),
    _query("loose_joints", "&Loose Joints"),
    _query("joints_in_bars", "Joints &Inside Members"),
    _query("shell_edge_joints", "Joints on S&hell Edges"),
)
