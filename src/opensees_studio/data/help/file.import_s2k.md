---
title: File → Import → SAP2000 Text (.s2k / .$2k)
group: File
summary: A model saved as SAP2000 text tables, as a new project in the nearest unit system.
see_also: file.export_s2k, file.import_s3d, file.open
order: 290
---

Reads a SAP2000 text file (`.s2k` or `.$2k`: tables of `Key=Value` records) and
makes it the **current project**. It replaces what is open, so unsaved changes
are asked about first, and the new project has no file until you save it.
SAP2000 is a trademark of Computers and Structures, Inc.; this reader was
written from the text format alone, without CSI software, and is not endorsed
by CSI.

# Units
The file's `CurrUnits` (for example `"KN, m, C"`) say what its numbers are in.
The project gets the nearest of the four systems (kN-m → m and N, kip-in → in
and kip, N-mm → mm and N, …) and every value is **scaled** to it by its
dimension. The log names both systems. A file without units is read as kN-m.

# What comes across
- **Joints** (global Cartesian, or with `GlobalX/Y/Z`) and their restraints.
  When only UX, UZ and RY are active and every joint is at Y = 0, the model
  becomes a **2D frame**.
- **Added joint masses** (`Mass1..3` and `MMI1..3`) and **support springs**
  (`U1..3`, `R1..3`), both in the joint local axes, which default to global. The
  mass source decides whether the added masses carry weight; a 2D model keeps
  only the in-plane components and reports the rest.
- **Grid lines** of the global system, with their labels.
- **Frames** as elastic beam-columns: the section and material assigned to each
  (a frame's own material overrides the section's), the local-axis angle (used
  to map the section orientation), the mass (unit mass × area) and the weight
  (unit weight × area, read by a load pattern's self weight). Shear areas make a
  Timoshenko member, as SAP2000 includes shear deformation.
- **Frame sections**: rectangular, I, pipe, box/tube and general by their
  property columns (the dimensions give closed-form values when those are
  missing), with the property modifiers applied to the values; other shapes by
  their properties only. Rectangles, I-shapes, pipes and tubes keep their shape
  for the extruded view. A **nonprismatic** section reads its segment table (in
  SAP2000's order, from the I end to the J end) into a `NonprismaticSection`
  template and subdivides each member into elastic pieces, 12 by default; the
  import asks for the piece count and the section can be edited later in Define >
  Section Library. A 2D model accepts a 0 in the inertia it does not bend about
  and in the torsion constant; a 3D section whose `J` is 0 gets a small one,
  because OpenSees needs torsional stiffness. Both substitutions are counted in
  the report.
- **End releases** of torsion and bending, partial-fixity springs, and each
  frame's **property modifiers** (`AMod`, `AS2Mod`, `AS3Mod`, `JMod`,
  `I22Mod`, `I33Mod`, `MassMod`, `WeightMod`, mapped to this program's local
  axes). A zero shear-area modifier turns shear deformation off; on a
  nonprismatic frame the segment sections' own shear areas govern, as in
  SAP2000's stored results.
- **Load patterns** with their self-weight multiplier, **joint forces** (global),
  **distributed frame loads** (uniform, trapezoidal or over part of the member,
  global, gravity, projected or local directions) and **point frame loads**.
- **Temperature loads** on frames: a uniform change, a joint-pattern variation
  along the member (its mean is used) and a cross-section gradient given per unit
  length, with the material's thermal expansion coefficient (`A1`).
- **Ground displacements** on restrained joints (support settlements), and
  **frame added mass** (`FRAME ADDED MASS ASSIGNMENTS`) added to the element's
  mass per length.
- **Rigid diaphragms** (`CONSTRAINT DEFINITIONS - DIAPHRAGM` and
  `JOINT CONSTRAINT ASSIGNMENTS`) as `RigidDiaphragm`, using SAP2000's
  floating centre-of-mass joint as the retained node so the runner can fix its
  out-of-plane DOFs. A diaphragm in a 2D model, a multi-level one, a joint
  outside its plane and a support left out of the floor are counted in the
  report.
- **Linear static load cases**, each with its load patterns. A pattern used with
  a factor other than 1 becomes a scaled copy (`LIVE x 0.5`). A file without
  load cases gets one per load pattern, as SAP2000 does. A case whose
  `InitialCond` names another imported static case runs it first as a preload,
  and its results include it.
- **Eigen modal cases**: a `LinModal` case with `ModeType=Eigen` becomes a modal
  case that asks for its `MaxNumModes`, with the solver left on this program's
  automatic routing (dense at or below 500 free DOF, ARPACK above). Other modal
  types, and a modal case with no `CASE - MODAL 1 - GENERAL` row, are counted in
  the report.
- **Response-spectrum cases**: a `LinRespSpec` case with a CQC or SRSS
  `ModalCombo` becomes a spectrum case on the file's first modal case, in its
  `U1..R3` direction and `ConstDamp`, with the tabulated function
  (`FUNCTION - RESPONSE SPECTRUM - USER`) as a project spectrum; `TransAccSF`
  takes its ordinates to the project units, and a `T = 0` point is read as
  `1e-6 s`. `ABS` and "10 Percent" combinations, more than one direction, a
  non-zero angle, accidental eccentricity and a second scale factor are counted
  in the report.
- **Combinations**: linear add, envelope, absolute add and SRSS, of cases and
  of other combinations.
- **Areas** with four joints and a shell section, as `ShellMITC4` with an
  elastic plate section. A Shell-Thin area becomes this thick-shell element,
  which also deforms in shear; the log notes it.

# Local axes
SAP2000 gives a frame's local 2 the upward direction in the member's vertical
plane (global +X for a vertical member), turned by its local-axis angle; OpenSees
gives a 3D beam its local z up. Per member the importer finds where local 2
lies and maps `I33`/`I22`, `AS2`/`AS3` and the M2/M3 releases onto this
program's axes (a section then used turned ends in "(axes 2-3)"). Loads are
re-projected, so they keep their direction. The SAP2000 angle is used for that
mapping; it is not stored as this program's own local-axis rotation (the IFC
round-trip carries that one).

# Damaged files
Every error names the table and the line it came from ("Frame 3 (CONNECTIVITY -
FRAME, line 57): joint 'C' is not defined."). A line inside a table that is not a
`Key=Value` record is counted in the summary instead of being skipped in silence,
and a file with no joints is refused rather than opened as an empty project. A
truncated or corrupted file always fails with a message; it never takes the
window down.

# Work in progress
This is not a complete SAP2000 reader. The full list of what is read, the known
approximations and the unsupported objects is in
`docs/sap2000-import-status.md` in the repository; the import log remains the
authoritative report for a particular file. Counted in the summary and the log,
never dropped silently:

- links, tendons, cables, solids and area types other than four-node shells;
- nonlinear/staged cases (`NonStatic`), buckling (`LinBuckling`), modal and
  direct history (`LinModHist`), steady state and moving loads;
- `ABS` and "10 Percent" spectrum combinations, a second direction/angle or
  accidental eccentricity on a spectrum case, and a non-static initial
  condition;
- frame end offsets, length offsets, insertion points, P-Delta/Corotational
  transformations, axial/shear releases and curved frames (imported straight);
- an exact local-axis angle: the SAP2000 angle maps the section orientation and
  is not stored as this program's `local_axis_angle` (IFC carries it exactly);
- rigid links, equalDOF and body constraints; storeys, groups and section cuts;
  a 2D or multi-level diaphragm;
- gravity loads, moment loads on frames, some point-load directions, a
  temperature variation along the member (its mean is used), and ground
  displacements on free or spring-supported DOFs;
- range-add combinations and automatic lateral loads;
- a frame with releases keeps no shear deformation, because OpenSees'
  Timoshenko beam takes none (a point, partial or varying load keeps the shear
  areas: a static case that applies it runs that frame with As2 = As3 = 0).
