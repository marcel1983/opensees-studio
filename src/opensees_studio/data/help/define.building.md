---
title: Define → Create Building
group: Define
summary: A multi-storey frame building from a few numbers: floors, loads, earthquake.
see_also: define.section_library, define.warehouse, define.storeys, define.mass_source, define.seismic_loads, assign.diaphragm, design.drift_check, file.new_model
order: 940
---

Builds a regular multi-storey building into the open 3D frame model as one
undoable step: a column at every grid intersection and beams both ways on every
floor, the supports, a group per kind of member and section ("Building columns
W14X90"), a grid on the column lines and
the floor levels, a storey and a rigid diaphragm per floor, the slab loads, the
mass source, the earthquake cases and the load combinations of a design code.
File → New Model → **Building** starts a new model with it. The preview on the
left follows every field.

# Geometry
- **Bays along X** and **along Y**, each with its **bay width**. When the bays
  differ, type their widths in **Unequal widths**, separated by spaces
  (`6 4.5 6`); that list then replaces the number of bays and their width.
- **Number of storeys**, the **storey height** and the **first storey height**
  (from the base to the first floor).
- **Column bases** — fixed or pinned.
- **Frame material** — steel or reinforced concrete. It sets the sections that
  are created when you choose none, and the empirical period of the earthquake.
- **Column section** — which way the depth of the column lies. Along X, the
  frames along X bend the columns about their strong axis.
- **Floors** — how each floor panel hands its load to the beams around it: a
  **two-way slab** to the four of them (triangles and trapezoids), a **one-way
  slab** only to the two beams it spans between (a slab spanning along X rests
  on the beams along Y).
- **Rigid diaphragm on every floor** — ties each floor in its own plane to a
  node at the centre of its mass (Assign → Joint → Diaphragm).

# Sections
One section for the columns, one for the beams along X and one for the beams
along Y. A member kind left at **(will be created)** gets a default section,
created in the same undo step: W14X90 columns and W18X50 beams of the AISC
library for a steel frame, 500 x 500 mm columns and 300 x 600 mm beams with
their gross (uncracked) stiffness for a concrete one. They are a starting
point, not a design.

**Section Library…** opens Define → Section Library over the wizard: add shapes of
the AISC library, a concrete or cold-formed section or one of your own, close
it, and the lists offer them. Each section is added as its own undoable step,
so it stays in the project even if you cancel the wizard.

# Floor loads and design code
The slab is **not modelled**. Its weight and the live load are floor panels,
one per bay and floor (Assign → Area → Floor Load to Frames), that load the
beams.

- **Design code** — RNC-07, NSCM (Managua) or ASCE 7-16 (LRFD or ASD).
- **Use of the floors** — residential, classrooms, hospital, offices or
  assembly. It fills the four live loads below from the code: RNC-07 Tabla 1
  (the maximum CV and the reduced CVR that goes with the earthquake), NSCM
  Tabla 7.1.1 (with 0.15 CV in the seismic weight, 9.6 a) or ASCE 7-16 Table
  4.3-1 (no live load in the seismic weight outside storage, 12.7.2). You can
  type other values.
- **Floor dead load** and **roof dead load** — slab, finishes, ceilings and
  partitions per area. The self weight of the beams and columns is the dead
  case's own. They go into `DEAD`.
- **Floor live load** goes into `LIVE` and **roof live load** into `ROOF LIVE`.
- **Live load in the seismic weight** — the part of each live load that counts
  as mass. It cannot exceed the live load.
- **Generate the load combinations of the code**.

The **mass** of the building is the mass source (Define → Mass Source): the
dead case plus that part of the live cases, lumped at the diaphragms. A project
that already had a mass source keeps it, with the building's cases added: check
that no weight is counted twice.

# Earthquake
With **Create the earthquake load cases** the wizard adds the equivalent
lateral force of the code, the same one as Define → Seismic Loads:

- **Method** — RNC-07 Art. 32, NSCM 8.2.1 or ASCE 7-16 12.8. It follows the
  design code and can be changed.
- **a0**, **soil** and **group or risk category** for the two Nicaraguan codes,
  with the **regularity** of RNC-07 Art. 23; **SDS**, **SD1** and **Ie** for
  ASCE 7.
- **Reduction factor** — Q, Ro or R. It starts at the value of an ordinary
  moment frame of the material (RNC-07 Q = 2; NSCM Tabla 5.5.1 and ASCE 7-16
  Table 12.2-1: 3.5 in steel, 3 in concrete). Raise it only for a system
  detailed for more ductility.
- **Period along X** and **along Y** — 0 takes the empirical period of the code
  (NSCM and ASCE 7) or, in RNC-07, which has none, the plateau of the spectrum.
  Type the period of a modal case to use it.
- **Accidental eccentricity** — a fraction of the floor's dimension across the
  earthquake: 0.1 by RNC-07 Art. 32 d, 0.05 by NSCM 9.8 and ASCE 7-16 12.8.4.2.
  Each direction then has two cases, `EQ X +e` and `EQ X -e`: the storey forces
  at the centre of mass with the torque to either side. With 0, or without
  rigid diaphragms, there is one case per direction, `EQ X`.

The summary at the bottom plans the building as the fields stand: the joints,
members, cases and combinations the project gains, the seismic weight and the
base shear of each direction with its coefficient. If the building cannot be
planned (for instance, a period the code cannot give), it says why and Finish
stays disabled.

In the combinations the `+e` and `-e` cases of a direction are alternatives.
RNC-07 (Art. 32 f) and NSCM take each direction with 30 % of the other; NSCM's
vertical component Ev = 0.2 a0 Fas CM (Ec. 7.8-4) goes into the dead load factor
with the a0 and the site class of this page.

# Afterwards
Run the cases and read the drifts with Design → Storey Drift Check. The forces
come from the **gross stiffness**: reduce it as your concrete code asks before
you read drifts (Assign → Frame → Property Modifiers). The displacements of the
earthquake cases are those of the reduced forces.

# Not included yet
Walls and bracing, slabs as shells, setbacks and openings in the floors, the
1.5 es of RNC-07 Art. 32 d (static eccentricity; a regular building has
almost none), the redundancy factor ρ and the overstrength combinations of
ASCE 7, wind on the building, and the design of the members.
