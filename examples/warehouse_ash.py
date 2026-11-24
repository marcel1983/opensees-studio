"""Build a steel warehouse with the volcanic ash load of the Nicaraguan codes, for Masaya.

Run from the repository root:

    python examples/warehouse_ash.py

Produces ``examples/warehouse_ash.osmodel``: a 20 m x 30 m gable warehouse, six
pinned-base portal frames at 6 m, with the gravity loads of Define → Create
Warehouse and its **Ash and snow** page:

- **Ash** — NSCM 7.3 (and RNC-07 Art. 14): 20 kg/m² of wet ash per area of
  horizontal projection, the value both codes recommend when there is no local
  record. Masaya is one of the places where it is mandatory. The case ``ASH``
  puts it on the purlins, like the roof live load.
- **Combinations** — NSCM LRFD has a load of its own for the ash, CCV:
  ``1.2CM + 1.6CCV``, ``1.2CM + 1.6CVT`` and ``1.4CM``.

Neither code says how much ash gathers in a valley or a gutter: both ask you
to estimate it. A single gable has neither.

Open it and run the cases: ``ASH`` bends the rafters like the live load, with
twice its value.
"""

from __future__ import annotations

from pathlib import Path

from opensees_studio.core import Project, ProjectMeta
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.snow import ASH_LOAD_KPA
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    WarehouseLoads,
    WarehouseSnow,
    WarehouseSpec,
    force_from_kn,
    plan_warehouse,
    pressure_from_kpa,
)
from opensees_studio.services import load_project, save_project

CODE = "nscm"


def build_warehouse_project() -> Project:
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="Gable warehouse 20 x 30 m, Masaya"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))

    spec = WarehouseSpec(
        span=20.0,
        eave_height=6.0,
        frame_spacing=6.0,
        n_frames=6,
        slope=0.15,
        purlin_spacing=1.5,
        girt_spacing=1.5,
        rafter_fly_brace_every=2,
        column_fly_brace_every=2,
    )
    preset = CODE_PRESETS[CODE]
    loads = WarehouseLoads(
        code=CODE,
        roof_dead=pressure_from_kpa(0.10, units),
        roof_live=pressure_from_kpa(preset.roof_live_kpa, units),
        midspan_point=force_from_kn(preset.midspan_point_kn, units),
        snow=WarehouseSnow(method="ash", ground=pressure_from_kpa(ASH_LOAD_KPA, units)),
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
