"""Build a steel warehouse with the NSCM earthquake cases, for Managua.

Run from the repository root:

    python examples/warehouse_seismic.py

Produces ``examples/warehouse_seismic.osmodel``: an 18 m x 30 m gable warehouse,
six pinned-base portal frames at 6 m, with end wall columns, girts and the
loads of the last three pages of Define → Create Warehouse:

- **Earthquake** — the static method of NSCM 8.2.1 with ``a0 = 0.36667 g``
  (Tabla 14.2, Managua), site class C, risk category II and ``Ro = 2``: the
  seismic coefficient of the plateau of the spectrum, ``c = 0.572``. The
  period is not used. The seismic weight is the steel, the roof dead load and
  0.3 of the roof live load (NSCM 9.6 b, warehouses); the base shear ``c W`` is
  shared between the joints by weight and height, as nodal loads in ``EQ X``
  (across, on the portal frames) and ``EQ Y`` (along, on the bracing).
- **Wind** — RNC-07 Título IV, wind zone 1 and Group B (VR = 30 m/s), terrain
  R2: ``WIND +X``, ``WIND -X``, ``WIND +Y`` and ``WIND -Y``.
- **Combinations** — NSCM LRFD: each wind with its own sign, and the
  earthquake both ways with the 100 % + 30 % rule and the vertical component of
  the site in the dead load factor (Ev = 0.2 a0 Fas CM = 0.095 CM, Ec. 7.8-4):
  ``1.295CM ± Eh:EQ X ± 0.3Eh:EQ Y`` and ``0.805CM ± ...``.

``Ro = 2`` is the wizard's starting value, not a recommendation: enter the one
of the lateral system of your building in the direction that has the least.
Accidental torsion is not included.

Open it and run the cases: ``EQ X`` sways the portal frames, ``EQ Y`` goes
down the roof and wall bracing of the end bays.
"""

from __future__ import annotations

from pathlib import Path

from opensees_studio.core import Project, ProjectMeta
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    WarehouseLoads,
    WarehouseSeismic,
    WarehouseSpec,
    WarehouseWind,
    force_from_kn,
    plan_warehouse,
    pressure_from_kpa,
)
from opensees_studio.core.wind import rnc07_regional_speed
from opensees_studio.services import load_project, save_project

CODE = "nscm"


def build_warehouse_project() -> Project:
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="Gable warehouse 18 x 30 m, Managua"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))

    spec = WarehouseSpec(
        span=18.0,
        eave_height=6.0,
        frame_spacing=6.0,
        n_frames=6,
        slope=0.15,
        purlin_spacing=1.5,
        girt_spacing=1.5,
        rafter_fly_brace_every=2,
        column_fly_brace_every=2,
        end_wall_column_spacing=6.0,
    )
    preset = CODE_PRESETS[CODE]
    loads = WarehouseLoads(
        code=CODE,
        roof_dead=pressure_from_kpa(0.10, units),
        roof_live=pressure_from_kpa(preset.roof_live_kpa, units),
        midspan_point=force_from_kn(preset.midspan_point_kn, units),
        wind=WarehouseWind(
            method="rnc07",
            speed=rnc07_regional_speed(1, "B"),
            exposure="R2",
            topography="T3",
        ),
        seismic=WarehouseSeismic(
            method="nscm",
            a0=0.36667,
            soil="C",
            importance_class="II",
            reduction=preset.seismic_reduction,
            roof_live=pressure_from_kpa(preset.seismic_live_kpa, units),
        ),
    )
    # No dead case yet: the plan creates it, with the sparse solver like the rest.
    plan = plan_warehouse(project, spec, loads=loads)
    plan.apply(project)
    print(plan.warehouse.summary())
    for note in plan.notes:
        print(note)
    return project


def main() -> None:
    project = build_warehouse_project()
    project.validate_references()
    print(
        f"Built '{project.meta.name}' — {len(project.nodes)} nodes, "
        f"{len(project.elements)} elements, {len(project.analyses)} cases, "
        f"{len(project.combinations)} combinations."
    )
    out_path = Path(__file__).with_suffix(".osmodel")
    save_project(project, out_path)
    print(f"Saved -> {out_path}")
    restored = load_project(out_path)
    restored.validate_references()
    assert restored.model_dump(by_alias=True) == project.model_dump(by_alias=True)
    print("Round-trip OK.")


if __name__ == "__main__":
    main()
