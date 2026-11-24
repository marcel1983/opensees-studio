"""Build a three-storey concrete office building with the NSCM earthquake, for Managua.

Run from the repository root:

    python examples/building_office.py

Produces ``examples/building_office.osmodel``: an 18 m x 15 m office building,
three bays of 6 m along X and three of 5 m along Y, a 3.5 m first storey under
two of 3 m, on fixed bases. It is what ``core.building.plan_building`` makes of
a few numbers:

- **Frame** — 500 x 500 mm columns and 300 x 600 mm beams of the project's
  concrete, with their gross stiffness, in three groups (columns, beams along
  X, beams along Y), and a grid on the column lines and the floors.
- **Floors** — a storey per level and a rigid diaphragm tied to a node at the
  centre of the floor's mass. The slab is not modelled: its weight, the
  finishes and the partitions (4.5 kPa, 3.5 kPa on the roof) are two-way floor
  panels in ``DEAD``; the office live load of NSCM Tabla 7.1.1 (250 kg/m²) is
  in ``LIVE`` and the roof's (100 kg/m²) in ``ROOF LIVE``.
- **Mass** — the dead case plus 0.15 of the live load (NSCM 9.6 a), lumped at
  the diaphragms.
- **Earthquake** — the equivalent lateral force of NSCM 8.2.1 with ``a0 =
  0.36667 g`` (Tabla 14.2, Managua), site class C, risk category II and ``Ro =
  8`` (Tabla 5.5.1 C.5, special concrete moment frames), with the empirical
  period of the code. Each direction has two cases, ``EQ X +e`` and ``EQ X
  -e``: the storey forces at the centre of mass with the torque of the 5 %
  accidental eccentricity (NSCM 9.8) to either side.
- **Combinations** — NSCM LRFD, the earthquake with the 100 % + 30 % rule
  between one case of each direction and the vertical component of the site in
  the dead load factor.

Open it and run the cases: Design → Storey Drift Check gives the drift of
each floor, and ``EQ Y +e`` against ``EQ Y -e`` shows what the accidental
torsion adds on the outer frames.

The sections are a starting point, not a design, and the forces come from the
gross (uncracked) stiffness: reduce it as your concrete code asks before you
read drifts.
"""

from __future__ import annotations

from pathlib import Path

from opensees_studio.core import Project, ProjectMeta
from opensees_studio.core.building import (
    BuildingLoads,
    BuildingPlan,
    BuildingSeismic,
    BuildingSpec,
    occupancy_loads,
    plan_building,
)
from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.warehouse import pressure_from_kpa
from opensees_studio.services import load_project, save_project

CODE = "nscm"


def plan_building_project() -> tuple[Project, BuildingPlan]:
    """The project with the building in it, and the plan it came from."""
    project = Project(ndm=3, ndf=6, meta=ProjectMeta(name="Office building 18 x 15 m, Managua"))
    units = project.meta.units
    project.materials.extend(default_materials(project.next_material_id(), units))

    spec = BuildingSpec.regular(
        bays_x=3,
        bay_x=6.0,
        bays_y=3,
        bay_y=5.0,
        storeys=3,
        storey_height=3.0,
        first_storey_height=3.5,
        frame="concrete",
    )
    loads = BuildingLoads(
        code=CODE,
        floor_dead=pressure_from_kpa(4.5, units),
        roof_dead=pressure_from_kpa(3.5, units),
        **occupancy_loads(CODE, "office", units),
        seismic=BuildingSeismic(
            method="nscm",
            a0=0.36667,
            soil="C",
            importance_class="II",
            reduction=8.0,
        ),
    )
    plan = plan_building(project, spec, loads=loads)
    plan.apply(project)
    return project, plan


def build_building_project() -> Project:
    project, plan = plan_building_project()
    print(plan.building.summary())
    for note in plan.notes:
        print(note)
    return project


def main() -> None:
    project = build_building_project()
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
