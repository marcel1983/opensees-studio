"""Define menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

#: A pattern refers to a time series: it is offered once the project has one.
_SERIES = Needs.PROJECT | Needs.TIME_SERIES


def _pattern(
    name: str, text: str, needs: Needs = Needs.NOTHING, *, method: str | None = None
) -> ActionSpec:
    """``define.<name>`` runs ``window.patterns.add_<name>`` and stays ``_act_add_<name>``."""
    return ActionSpec(
        f"define.{name}",
        text,
        f"patterns.{method or f'add_{name}'}",
        needs=needs,
        legacy_attribute=f"_act_add_{name}",
    )


DEFINE_ACTIONS: tuple[ActionSpec, ...] = (
    # A time series can be defined with no project open: the command starts one.
    _pattern("linear_ts", "Add &Linear TimeSeries…"),
    _pattern("path_ts", "Add &Path TimeSeries…"),
    _pattern("function_ts", "Add &Function TimeSeries (Constant, Trig, Pulse…)…"),
    ActionSpec("define.constant_ts", "Add &Constant TimeSeries…", "patterns.constant_ts"),
    _pattern("plain_pattern", "Add &Plain Load Pattern…", _SERIES),
    _pattern("uniform_excitation", "Add &Uniform Excitation…", _SERIES),
    _pattern(
        "multi_support",
        "Add &Multi-Support Excitation…",
        Needs.PROJECT | Needs.SELECTED_NODES,
    ),
    ActionSpec("define.storeys", "Store&ys…", "building.define_storeys", needs=Needs.PROJECT),
    ActionSpec(
        "define.joint_patterns",
        "&Joint Patterns…",
        "loads.define_joint_patterns",
        needs=Needs.PROJECT,
    ),
    ActionSpec(
        "define.mass_source",
        "Mass S&ource…",
        "building.define_mass_source",
        needs=Needs.PROJECT,
    ),
    ActionSpec(
        "define.seismic_loads",
        "Seismic &Loads (Equivalent Lateral Force)…",
        "building.define_seismic_loads",
        needs=Needs.PROJECT,
    ),
)
