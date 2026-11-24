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


def _library(
    name: str, text: str, *, shortcut: str | None = None, method: str | None = None
) -> ActionSpec:
    """define.<name> runs window.library.<name>; it starts a project when there is none."""
    return ActionSpec(f"define.{name}", text, f"library.{method or name}", shortcut=shortcut)


DEFINE_ACTIONS: tuple[ActionSpec, ...] = (
    # Both start a project when there is none, so they are always offered.
    ActionSpec("define.grid", "&Coordinate System/Grids…", "grids.define", shortcut="Ctrl+G"),
    ActionSpec("define.grid_wizard", "Grid &Wizard…", "grids.wizard"),
    _library("material_library", "&Material Library…", shortcut="Ctrl+Shift+M"),
    ActionSpec(
        "define.default_materials",
        "Add &Default Materials",
        "library.add_default_materials",
        needs=Needs.PROJECT,
        tooltip=(
            "Add the default steels (A36, A572 Gr. 50, A992, A500 Gr. B, A653 sheet), "
            "concretes (3000 and 4000 psi) and grouted block masonry the project lacks."
        ),
    ),
    _library("mc2010", "Concrete Creep && Shrin&kage (fib MC2010)…", method="mc2010_concrete"),
    _library("friction_library", "&Friction Models…"),
    # It calls OpenSees itself: the window enables it when OpenSeesPy is there.
    ActionSpec(
        "define.material_tester",
        "Material &Tester…",
        "library.material_tester",
        shortcut="Ctrl+Shift+T",
        needs=None,
    ),
    # Ctrl+Shift+G is Assign to Group and Ctrl+Shift+S is Save As: an
    # ambiguous shortcut fires neither (tests/gui/test_shortcuts.py).
    _library("ground_motions", "&Ground Motions…", shortcut="Ctrl+Shift+W"),
    _library("section_library", "&Section Library…", shortcut="Ctrl+Shift+E"),
    _library("concrete_section", "&Concrete Section Wizard…"),
    _library("steel_deck", "Steel Deck Sla&b Wizard…"),
    _library("section_designer", "Section &Designer…"),
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
    # Enabled with three or four joints selected: the window sets it.
    ActionSpec(
        "define.create_shell",
        "Create S&hell from 3 or 4 Nodes…",
        "areas.create_shell",
        needs=None,
    ),
    ActionSpec("define.groups", "&Groups…", "groups.define_groups", needs=Needs.PROJECT),
    ActionSpec(
        "define.section_cuts",
        "Section &Cuts…",
        "groups.define_section_cuts",
        needs=Needs.PROJECT,
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
    # The wizards: a structure from a few numbers, one undo step (GeneratorsController).
    ActionSpec(
        "define.frame_wizard",
        "Create Portal &Frame…",
        "generators.portal_frame",
        needs=Needs.PROJECT,
    ),
    ActionSpec(
        "define.truss_wizard", "Create &Truss…", "generators.create_truss", needs=Needs.PROJECT
    ),
    ActionSpec(
        "define.warehouse_wizard",
        "Create &Warehouse…",
        "generators.create_warehouse",
        needs=Needs.PROJECT,
        tooltip=(
            "A 3D steel warehouse from a few numbers: portal frames, purlins, girts, "
            "bracing, roof loads and the combinations of a design code."
        ),
    ),
    ActionSpec(
        "define.building_wizard",
        "Create &Building…",
        "generators.create_building",
        needs=Needs.PROJECT,
        tooltip=(
            "A multi-storey frame building from a few numbers: bays, storeys, floor "
            "loads, rigid diaphragms, the earthquake and the combinations of a design code."
        ),
    ),
)
