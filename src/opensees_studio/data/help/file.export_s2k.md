---
title: File → Export → SAP2000 Text
group: File
summary: The frame model as SAP2000 text tables, readable again by Import.
see_also: file.import_s2k, file.export_ifc
order: 310
---

Writes the project as a SAP2000 text file (`.s2k`) in the project's own units
(`CurrUnits`). Everything File → Import → SAP2000 Text reads is written, so an
exported file imports back to the same model. SAP2000 is a trademark of
Computers and Structures, Inc.; the file follows the text format and has not
been checked by CSI or in SAP2000.

# What is written
- Joints, restraints, added joint masses and support springs, global grid lines
  and the active DOFs (UX, UZ, RY only for a 2D frame).
- Elastic beam-columns on elastic sections, with their end releases,
  partial-fixity springs and per-frame property modifiers. Each section is
  written with SAP2000's local 2 on this program's local z (local y in 2D), and
  a member whose axes differ from SAP2000's default gets the local-axis angle
  that makes them match, including the member's `local_axis_angle`. A section
  with a shape (rectangle, I, pipe, tube) is written as that shape, any other as
  a general section; every one carries its area, inertias, torsion constant and
  shear areas (0 when the member has no shear deformation).
- One material per distinct set of modulus, shear modulus, unit weight and unit
  mass (named MAT1, MAT2, …).
- Shells (`ShellMITC4` on an elastic plate section) as thick-shell areas.
- Rigid diaphragms (`CONSTRAINT DEFINITIONS - DIAPHRAGM` and
  `JOINT CONSTRAINT ASSIGNMENTS`).
- Plain load patterns with their self weight, joint forces, and uniform,
  trapezoidal and point frame loads in local directions.
- Linear static cases, eigen modal cases, response-spectrum cases (CQC or SRSS)
  with their tabulated spectra, and combinations of static cases and of each
  other.

# What is not written
The export reports what it leaves out: other element and section types, end
offsets, insertion points, the mass source, shell and floor loads, imposed
displacements, temperature loads, nonlinear static, modal, spectrum and
transient cases, and constraints other than diaphragms (rigid links and
equalDOFs). A nonprismatic section
is written as the elastic pieces it was subdivided into, not as a SAP2000
`NONPRISMATIC` table, so the exported file carries the same mechanical model but
not the taper template.
