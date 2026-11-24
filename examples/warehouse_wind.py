"""Build a steel warehouse with end wall columns and the RNC-07 wind cases.

Run from the repository root:

    python examples/warehouse_wind.py

Produces ``examples/warehouse_wind.osmodel``: a 24 m x 36 m gable warehouse,
seven pinned-base portal frames at 6 m, with what Define → Create Warehouse adds
on its second and last pages:

- **End walls** — end wall columns no more than 6 m apart, each under a purlin
  line and pinned at both ends, with girts between them at 1.5 m.
- **Stabilising angles** — on every second purlin and every second girt, so the
  rafters, the side columns and the end wall columns have their unbraced
  lengths written for the steel check.
- **Wind** — RNC-07 Título IV, wind zone 2 and Group B (VR = 45 m/s), terrain
  R2 on flat ground, a closed building: one case per direction, ``WIND +X``,
  ``WIND -X``, ``WIND +Y`` and ``WIND -Y``. The pressures act on the purlins
  (roof), on the girts (walls) and, under the roof line of an end wall, on the
  end rafter.
- **Combinations** — RNC-07 Art. 15 with each wind case in turn, with its own
  sign only: 1.2CM + 1.6Pz + CV and 0.9CM + 1.6Pz.

Open it and run the cases: the 0.9CM + 1.6Pz combinations are the uplift check
of the bases, and ``WIND +Y`` shows the end wall columns sending their top
reaction along the purlins into the roof bracing of the first bay.
"""

from __future__ import annotations

from pathlib import Path

from opensees_studio.core import Project, ProjectMeta
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    WarehouseLoads,
    WarehouseSpec,
    WarehouseWind,
    force_from_kn,
    plan_warehouse,
    pressure_from_kpa,
)
from opensees_studio.core.wind import rnc07_regional_speed
from opensees_studio.services import load_project, save_project

CODE = "rnc07"


def build_warehouse_project() -> Project:
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="Gable warehouse 24 x 36 m, wind"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)

    spec = WarehouseSpec(
        span=24.0,
        eave_height=7.0,
        frame_spacing=6.0,
        n_frames=7,
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
            speed=rnc07_regional_speed(2, "B"),
            exposure="R2",
            topography="T3",
        ),
    )
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
