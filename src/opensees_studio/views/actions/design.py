"""Design menu commands: every one needs a project and nothing else."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs


def _design(name: str, text: str, method: str | None = None) -> ActionSpec:
    return ActionSpec(f"design.{name}", text, f"design.{method or name}", needs=Needs.PROJECT)


DESIGN_ACTIONS: tuple[ActionSpec, ...] = (
    # Basis and stability.
    _design("design_basis", "Design &Basis (AISC)…"),
    _design("direct_analysis", "Direct &Analysis Method…"),
    _design("notional_loads", "Generate &Notional Loads (DAM)…"),
    # Members.
    _design("member_classification", "&Member Classification…"),
    _design("built_up", "B&uilt-Up Shapes…"),
    # Steel frame.
    _design("steel_check", "&Steel Frame Check (AISC 360-16)…"),
    _design("steel_ratios", "Display Steel &Ratios on Model"),
    _design("drift_check", "Storey &Drift Check…"),
    # Connections.
    _design("joint_connections", "Connections by &Joint…"),
    _design("base_plates", "Base &Plates (Column Bases)…"),
    _design("connections", "&Connections (AISC 358-22)…"),
    _design("gussets", "&Gussets (AISC 341-22)…"),
    _design("column_splices", "&Column Splices (AISC 341-22)…"),
    _design("chapter_j", "Connection Checks (AISC 360 &J)…"),
    # Calculators.
    _design("base_plate", "&Base Plate && Anchors (DG1, ACI 318)…"),
    _design("bolted", "Bolted Connection (&Prying, Bolt Group)…", "bolted_connection"),
    # Concrete and foundations.
    _design("concrete_check", "Co&ncrete Frame Check (ACI 318-19)…"),
    _design("footings", "&Footings (ACI 318-19, Soil)…"),
    _design("footing_pressures", "Footing &Pressure Plan…"),
)
