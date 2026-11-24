"""Assign menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

_JOINTS = Needs.PROJECT | Needs.SELECTED_NODES
_ELEMENTS = Needs.PROJECT | Needs.SELECTED_ELEMENTS
_TWO_JOINTS = Needs.PROJECT | Needs.TWO_NODES


def _load(name: str, text: str, needs: Needs | None, shortcut: str | None = None) -> ActionSpec:
    """A load command: ``assign.<name>`` runs ``window.loads.assign_<name>``."""
    return ActionSpec(
        f"assign.{name}",
        text,
        f"loads.assign_{name}",
        shortcut=shortcut,
        needs=needs,
        legacy_attribute=f"_act_assign_{name}",
    )


def _joint(name: str, text: str, needs: Needs = _JOINTS, shortcut: str | None = None) -> ActionSpec:
    """A joint command: ``assign.<name>`` runs ``window.joints.assign_<name>``."""
    return ActionSpec(
        f"assign.{name}",
        text,
        f"joints.assign_{name}",
        shortcut=shortcut,
        needs=needs,
        legacy_attribute=f"_act_assign_{name}",
    )


def _springs(kind: str, text: str) -> ActionSpec:
    """assign.<kind>_springs runs window.areas.assign_<kind>_springs."""
    return ActionSpec(
        f"assign.{kind}_springs",
        text,
        f"areas.assign_{kind}_springs",
        needs=_ELEMENTS,
        legacy_attribute=f"_act_assign_{kind}_springs",
    )


def _member(name: str, text: str) -> ActionSpec:
    """A member command: ``assign.<name>`` runs ``window.members.assign_<name>``."""
    return ActionSpec(
        f"assign.{name}",
        text,
        f"members.assign_{name}",
        needs=_ELEMENTS,
        legacy_attribute=f"_act_assign_{name}",
    )


ASSIGN_ACTIONS: tuple[ActionSpec, ...] = (
    # Ctrl+G is Coordinate System/Grids: a shared shortcut fires neither.
    ActionSpec(
        "assign.group",
        "Assign to &Group…",
        "groups.assign_group",
        shortcut="Ctrl+Shift+G",
        needs=Needs.PROJECT | Needs.SELECTION,
        legacy_attribute="_act_assign_group",
    ),
    # What holds a joint, what it weighs and what joins it to another one.
    _joint("support", "&Restraints…", shortcut="Ctrl+R"),
    _joint("masses", "&Masses…"),
    _joint("springs", "S&prings…"),
    _joint("equal_dof", "&EqualDOF…", _TWO_JOINTS),
    _joint("zero_length", "Zero-&Length Element…", _TWO_JOINTS),
    _joint("zls", "&Zero-Length Section…", _TWO_JOINTS),
    _joint("bearing", "&Bearing…", _TWO_JOINTS),
    _joint("link", "&Link (twoNodeLink / TFP)…", _TWO_JOINTS),
    # What a member is made of and how it is modelled.
    _member("section", "S&ection…"),
    _member("material", "&Material…"),
    _member("geom_transf", "&Geometric Transformation…"),
    _member("local_axes", "&Local Axes…"),
    _member("integration", "Beam &Integration…"),
    _member("releases", "&Releases/Partial Fixity…"),
    _member("end_offsets", "&End (Length) Offsets…"),
    _member("insertion", "I&nsertion Point…"),
    _member("modifiers", "Property M&odifiers…"),
    _member("auto_mesh", "&Auto Mesh…"),
    ActionSpec(
        "assign.tension_only",
        "&Tension Only…",
        "members.assign_tension_only",
        needs=_ELEMENTS,
    ),
    # What turns a member into something else.
    _member("hinge", "Plastic &Hinge…"),
    _member("wall", "RC &Wall (MVLEM)…"),
    _member("pile", "&Pile Soil Springs (p-y, t-z, q-z)…"),
    ActionSpec(
        "assign.diaphragm",
        "&Diaphragm…",
        "building.assign_diaphragm",
        needs=Needs.PROJECT,
        legacy_attribute="_act_assign_diaphragm",
    ),
    ActionSpec(
        "assign.rigid_link",
        "Rigid &Link…",
        "building.assign_rigid_link",
        needs=_TWO_JOINTS,
        legacy_attribute="_act_assign_rigid_link",
    ),
    ActionSpec(
        "assign.remove_constraints",
        "Remove &Constraints",
        "building.remove_constraints",
        needs=_JOINTS,
    ),
    # Shells and the distributed springs under shells, shell edges and members.
    ActionSpec(
        "assign.shell_formulation",
        "Shell &Formulation…",
        "areas.shell_formulation",
        needs=_ELEMENTS,
    ),
    _springs("area", "&Area Springs…"),
    _springs("edge", "&Edge Springs…"),
    _springs("line", "&Line Springs…"),
    # Loads on joints.
    ActionSpec(
        "assign.load",
        "&Point Loads…",
        "loads.assign_nodal_load",
        shortcut="Ctrl+L",
        needs=_JOINTS,
        legacy_attribute="_act_assign_load",
    ),
    _load("imposed_displacement", "Imposed &Displacement…", _JOINTS),
    _load("joint_pattern", "Joint &Pattern Values…", _JOINTS),
    # Loads on frames.
    _load("distributed_load", "&Distributed Load…", _ELEMENTS),
    _load("trapezoidal_load", "&Trapezoidal Load…", _ELEMENTS),
    _load("frame_point_load", "&Point Load…", _ELEMENTS),
    _load("temperature_load", "Te&mperature Load…", _ELEMENTS),
    _load("tendon", "Te&ndon (Post-Tensioning)…", _ELEMENTS),
    # Loads on areas. A floor load needs joints of a 3D model: the window sets it.
    _load("surface_load", "&Surface Load on Shells…", _ELEMENTS),
    _load("floor_load", "&Floor Load to Frames…", None),
)
