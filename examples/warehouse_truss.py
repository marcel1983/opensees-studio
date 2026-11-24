"""Build a steel warehouse on roof trusses, with the RNC-07 wind cases.

Run from the repository root:

    python examples/warehouse_truss.py

Produces ``examples/warehouse_truss.osmodel``: a 30 m x 36 m gable warehouse,
seven frames at 6 m, each a **Pratt roof truss** on two pinned-base columns:

- **Truss** — the top chord follows the roof (15 %) with a panel point under
  every purlin line; the bottom chord is horizontal, 1 m below the eave, so the
  truss is 1 m deep at the columns and 3.25 m at the ridge. Chords are
  continuous (HSS 6x6x1/4) and run into the columns, which go on up to the top
  chord: truss and columns work as a frame. Verticals and diagonals are pinned
  (HSS 3x3x3/16); the ties are HSS 4x4x3/16.
- **Bottom chord ties** — at the column lines, at the ridge and at every fourth
  panel point the bottom chord is tied to the next frame, and in the two braced
  bays each tie line has a vertical X between the chords. The steel check takes
  the bottom chord's unbraced length between tie lines.
- **End walls** — end wall columns no more than 6 m apart, pinned, each one the
  vertical of the end truss at its purlin line; girts at 1.6 m.
- **Wind** — RNC-07 Título IV, wind zone 2 and Group B (VR = 45 m/s), terrain
  R2: ``WIND +X``, ``WIND -X``, ``WIND +Y`` and ``WIND -Y``, and the RNC-07
  combinations with each of them.

Every case the wizard creates uses the sparse solver UmfPack: on a model with
this many pinned members the band solver takes tens of seconds per case.

Open it and run the cases: under ``DEAD`` the bottom chord is in tension and
the top chord in compression; under ``0.9CM + 1.6Pz`` with ``WIND +X`` the roof
lifts and the bottom chord goes into compression between its ties.
"""

from __future__ import annotations

from pathlib import Path

from opensees_studio.core import Project, ProjectMeta
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.trusses import TrussType
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
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="Trussed warehouse 30 x 36 m"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))

    spec = WarehouseSpec(
        span=30.0,
        eave_height=8.0,
        frame_spacing=6.0,
        n_frames=7,
        slope=0.15,
        purlin_spacing=1.5,
        girt_spacing=1.6,
        column_fly_brace_every=2,
        end_wall_column_spacing=6.0,
        roof_structure="truss",
        truss_type=TrussType.PRATT,
        truss_bottom="horizontal",
        truss_depth=1.0,
        bottom_chord_tie_every=4,
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
