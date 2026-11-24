---
title: File → Export → IFC
group: File
summary: The model as IFC4: the physical BIM model and the structural analysis model.
see_also: file.export_script, file.import_ifc, file.save
order: 550
---

Writes an IFC4 file (`.ifc`) with two linked descriptions of the structure, the
way BIM tools and structural programs exchange a model.

# The physical model (what BIM viewers draw)
- One building storey per storey (Define → Storeys) plus the base, each element
  in the storey it starts on.
- Frame members as **IfcColumn** (within 10° of vertical), **IfcBeam** (within
  10° of horizontal) or **IfcMember** (braces and every truss bar), extruded along
  their axis from their profile: an I or channel for an AISC section (looked up by
  its name), a rectangle, hollow or solid circle or angle from the section's
  shape, else the rectangle of the section's extent. Each carries a material
  profile set named after its section.
- Shells as **IfcSlab** (horizontal), **IfcWall** (vertical) or **IfcPlate**,
  their thickness extruded along the normal.

# The analytical model (what structural software reads)
- An IfcStructuralAnalysisModel (in-plane for a 2D model) with a point
  connection per node, its supports as boundary conditions, a curve member per
  frame or truss (end releases on the member's connection) and a surface member
  per shell with its thickness.
- One load case per Plain pattern, its action type guessed from the name (DEAD,
  LIVE, WIND, EQ …): nodal forces, uniform and trapezoidal member loads (a floor
  load as the member loads it becomes), point loads on members, shell pressures,
  imposed displacements, and the self weight as the case's self-weight
  coefficients. Load combinations become load groups of type combination with
  each case assigned by its factor.
- Every analytical member is assigned to its physical element.

# Good to know
- Coordinates and values stay in the project's units (metre, millimetre, foot or
  inch; newton or kip), declared in the file.
- Elements IFC has no member for (bearings, zero-length elements, plane quads)
  are left out, and so is a node no frame, truss or shell touches (a diaphragm's
  retained node) with its loads. The export says what it left out.
- Masses, analysis cases and results are not part of the file.
- Each section's exact values (E, G, A, I, J, unit weight) are written on its
  material in the `OpenSeesStudio_Section` property set, so File → Import → IFC
  brings the file back to the model it came from.
