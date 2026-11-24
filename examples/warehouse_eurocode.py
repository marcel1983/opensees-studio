"""Build a steel warehouse with the loads and combinations of the Eurocodes.

Run from the repository root:

    python examples/warehouse_eurocode.py

Produces ``examples/warehouse_eurocode.osmodel``: a 20 m x 30 m gable warehouse
at 1 in 5 (11.3°), six pinned-base portal frames at 6 m with girts and end wall
columns, and what Define → Create Warehouse makes of the design code
**EN 1990**:

- **Roof imposed load** — EN 1991-1-1 Table 6.10, category H: 0.4 kN/m².
- **Wind** — EN 1991-1-4 with a basic wind velocity of 26 m/s in terrain
  category II: qp at the ridge (8 m), the wall zones A to E of Table 7.1 and
  the roof zones F to J of Tables 7.4a and 7.4b. Across the ridge the roof has
  a negative and a positive set of values, so each of ``+X`` and ``-X`` has
  four cases (``A`` to ``D``); along it there are two, which differ in the
  internal pressure (+0.2 and -0.3).
- **Snow** — EN 1991-1-3 with sk = 1 kN/m²: ``SNOW`` and the two drifted
  arrangements of 5.3.3, ``SNOW +X`` and ``SNOW -X``.
- **Combinations** — EN 1990, Expression 6.10, also with a favourable permanent
  action (the wind lifts the roof), and the serviceability ones. The roof
  imposed load is not combined with the snow or the wind (EN 1991-1-1
  3.3.2 (1)), and the snow cases never act together.

The values are the recommended ones of the Eurocodes: a National Annex may
change them. Open it and look at ``WIND +Y A``: the purlins of the first bay,
under the zones F and G, carry about half as much again as those of the last.
"""

from __future__ import annotations

from pathlib import Path

from opensees_studio.core import Project, ProjectMeta
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    WarehouseLoads,
    WarehouseSnow,
    WarehouseSpec,
    WarehouseWind,
    plan_warehouse,
    pressure_from_kpa,
)
from opensees_studio.services import load_project, save_project

CODE = "en1990"


def build_warehouse_project() -> Project:
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="Gable warehouse 20 x 30 m, Eurocodes"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))

    spec = WarehouseSpec(
        span=20.0,
        eave_height=6.0,
        frame_spacing=6.0,
        n_frames=6,
        slope=0.2,
        purlin_spacing=1.5,
        girt_spacing=1.5,
        end_wall_column_spacing=5.0,
        rafter_fly_brace_every=2,
        column_fly_brace_every=2,
    )
    preset = CODE_PRESETS[CODE]
    loads = WarehouseLoads(
        code=CODE,
        roof_dead=pressure_from_kpa(0.10, units),
        roof_live=pressure_from_kpa(preset.roof_live_kpa, units),
        wind=WarehouseWind(method=preset.wind_method, speed=preset.wind_speed, exposure="II"),
        snow=WarehouseSnow(method=preset.snow_method, ground=pressure_from_kpa(1.0, units)),
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
