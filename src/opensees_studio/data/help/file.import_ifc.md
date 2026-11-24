---
title: File → Import → IFC
group: File
summary: An IFC file's analytical model, or its physical model with the axes joined, as a new project.
see_also: file.export_ifc, analyze.check_model, edit.mesh
order: 560
---

Reads an IFC file (IFC2x3 or IFC4, `.ifc` or `.ifczip`) and makes it the
**current project**. It replaces what is open, so unsaved changes are asked
about first, and the new project has no file until you save it. The dialog says
what the file holds before anything is imported.

# Analytical or physical
An IFC file can describe the structure twice:

- The **analytical model** (IfcStructuralAnalysisModel) is what Tekla, Revit's
  analytical model, SAP2000, ETABS and File → Export → IFC write. It is taken as
  it is: point connections become nodes with their supports (fixed, free or a
  spring stiffness), curve members become elastic beam-columns (or trusses for
  pin-jointed members) with their end releases, surface members with four
  corners become shells, and load cases come with their loads.
- The **physical model** (IfcColumn, IfcBeam, IfcMember, IfcSlab, IfcWall,
  IfcPlate) is solids, drawn to their faces. Each member's axis is taken from its
  extrusion (or from its Axis representation), and the axes are **joined**: an
  end that stops within 1.25 × half the member's depth of another member is
  moved onto that member's axis, a column end onto a column, a beam end onto a
  column first and then onto another beam, and a member is split where another
  one lands on it or crosses it. Slab and wall corners attach to the nearest
  member node within reach; each slab or wall becomes **one** shell, so
  subdivide it with Edit → Mesh, which also connects the members along its
  edges. A physical model has no supports (the bases of the columns at the
  lowest level can be fixed) and no loads.

The analytical model is chosen when the file has one.

# Units
The file's unit assignment says what its numbers are in. The project gets the
nearest of the four systems (millimetres → SI mm-N, metres → SI m-N, feet and
inches → the US systems) or the one you pick, and every value is converted by
its dimension. A unit the file does not declare is derived from its length and
force units; a modulus without its own unit is read in the file's pressure unit,
and a density without one in kg/m³.

# Sections and materials
- A profile named after an **AISC v16 shape** (W14X90, HSS6X6X1/4, also as the
  type name "W-Wide Flange:W14X90") takes the library's A, I and J.
- Otherwise the properties come from the profile's dimensions (I, channel, tee,
  angle, rectangle, round and rectangular hollow, or any closed polygon), or
  from Pset_ProfileMechanical. A member with no profile at all gets a 300 mm
  square placeholder, which the log reports.
- A member whose profile is turned 90° in a file without the local-axis
  property gets a section with Iy and Iz exchanged ("… (rotated 90°)"). A file
  written by this version carries the exact angle in `OpenSeesStudio_Frame` /
  `OpenSeesStudio_Member`, so the section keeps its Iy and Iz and the member
  turns instead.
- E, G and ν come from Pset_MaterialMechanical and the density (for self
  weight) from Pset_MaterialCommon. A material with no modulus gets the
  defaults of its kind (steel or concrete, from its category or name). Steel
  with a yield stress is also added as a Steel01, and concrete with a strength
  as a Concrete01, in Define → Materials.
- A file written by File → Export → IFC carries its exact values and comes back
  unchanged.

# Loads
Each load case becomes a Plain pattern and a static case: nodal forces and
moments, imposed displacements, uniform and piecewise-linear member loads (in
global or local coordinates, true or projected length), point loads on members,
surface pressures, and the self-weight coefficient. Load combinations come with
their factors. Distributed and concentrated moments on members are reported and
left out.

# Check before running
The log lists what was not imported. The import then runs Analyze → Check Model
and says so when it finds loose nodes or instabilities — after a physical
import, check the joints it made.
