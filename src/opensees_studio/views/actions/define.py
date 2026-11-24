"""Define menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

DEFINE_ACTIONS: tuple[ActionSpec, ...] = (
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
