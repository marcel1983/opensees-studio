---
title: File → Import → PORTICO Model (.s3d)
group: File
summary: A model saved by PORTICO, as a new project scaled to the units you choose.
see_also: file.open, file.import_dxf
order: 280
---

Reads a `.s3d` file from PORTICO (the browser-based structural analysis program,
`jpreyes/portico-core`) and makes it the **current project**. It replaces what is
open, so unsaved changes are asked about first, and the new project has no file
until you save it.

# Units
PORTICO never converts: the file's `units` label says which system its numbers
are in. **File units** is filled in from that label (`kN-m`, `kip-in`, `lb-in`,
…); change it if the label is wrong. **Project units** is the system the project
gets, and every value is **scaled** to it by its dimension: lengths, forces,
moments, stresses, masses, densities, spring stiffnesses and loads. A `kN-m`
file opened in `SI (m, N, kg, s, Pa)` has its forces multiplied by 1000 and its
densities in kg/m³. The **Scale** line shows the length and force factors.

Self weight is the material density times g in the project's units. PORTICO
always multiplies by 9.80665, which is only right for its own `kN-m`.

# What comes across
- Nodes, supports, support springs and nodal masses.
- Frame elements as elastic beam-columns. A section with shear areas makes a
  Timoshenko member, as in PORTICO, and the consistent mass matrix is used.
- Sections and materials: one elastic section per section, material and
  orientation used, with PORTICO's section modifiers applied to the values.
- End releases (torsion and bending) and end springs on released actions.
- Static load cases with their nodal, uniform and trapezoidal loads and self
  weight, each as a load pattern plus a linear static case of the same name.
- Prescribed support displacements, as one pattern every static case runs (as
  PORTICO imposes them in every static case).
- Load combinations and grid lines.
- **Areas** (quadrilaterals) as `ShellMITC4` with an elastic plate section per
  material and thickness; their element ids follow the members'. PORTICO's
  membrane and plate areas become full shells (a membrane gains bending, a plate
  gains membrane stiffness), which the log notes.
- **Diaphragms** as rigid diaphragms on PORTICO's master node (`masterId`, else
  the first node). The floor mass is spread equally over the floor's nodes on UX
  and UY (PORTICO uses the tributary of the beams).
- **Links**: a rigid link with all six DOFs is a rigid `beam` link, with the three
  translations a `bar`; a non-rigid link is an equalDOF of its DOFs.
- The **mass source**: its load cases and factors, the self weight when ticked,
  and the mass on all three translations, as PORTICO does.
- A model loaded only by prescribed displacements (a patch test) gets a static
  case of its own.
- **Cable** and **compression-only** members as trusses whose elastic material
  goes slack on the other side (`Eneg = 0` for a cable, a stiffness of 1e-9 E in
  tension for a strut). The static cases then run with Newton, and their
  combinations are no longer an exact superposition.

# Local axes
PORTICO gives a beam its local **y** up; OpenSees gives it local **z** up. Per
member the importer works out how the two triads relate and swaps `Iz`/`Iy`,
`Avy`/`Avz` and the bending releases where needed (the section name then ends in
"(axes 2-3)"). Distributed loads are re-projected onto the OpenSees axes, so they
keep their global direction.

# What it does not do (yet)
Counted in the summary and the log, never dropped silently: triangular areas
(there is no 3-node shell), areas of a 2D model, temperature loads, response
spectrum cases (the spectrum is not in the file), translational end releases,
unilateral, coupled and soil springs, a diaphragm's rotational mass and
accidental eccentricity, and distributed loads on a cable or a strut (a truss
takes none). A member with releases loses its shear deformation, because
OpenSees' Timoshenko beam takes none. A trapezoidal load keeps the shear areas:
a static case that applies it runs that member with As2 = As3 = 0 and says so.
