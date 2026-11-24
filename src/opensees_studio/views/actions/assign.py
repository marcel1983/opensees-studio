"""Assign menu commands (the ones a controller already handles)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

_JOINTS = Needs.PROJECT | Needs.SELECTED_NODES
_ELEMENTS = Needs.PROJECT | Needs.SELECTED_ELEMENTS


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


ASSIGN_ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        "assign.diaphragm",
        "&Diaphragm…",
        "building.assign_diaphragm",
        needs=Needs.PROJECT,
        legacy_attribute="_act_assign_diaphragm",
    ),
    # Enabled with exactly two joints selected: the window sets it.
    ActionSpec(
        "assign.rigid_link",
        "Rigid &Link…",
        "building.assign_rigid_link",
        needs=None,
        legacy_attribute="_act_assign_rigid_link",
    ),
    ActionSpec(
        "assign.remove_constraints",
        "Remove &Constraints",
        "building.remove_constraints",
        needs=_JOINTS,
    ),
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
