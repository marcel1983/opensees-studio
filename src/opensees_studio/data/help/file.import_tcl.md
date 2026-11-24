---
title: File → Import → OpenSees Tcl Script (.tcl)
group: File
summary: A model written as an OpenSees Tcl script, as a new project.
see_also: file.import_s2k, file.import_s3d, file.export_s2k
order: 300
---

Reads the model-building part of a `.tcl` script and makes it the **current
project**, replacing what is open (unsaved changes are asked about first).
Tcl is interpreted, never executed: only the model commands, variables,
`expr`, `foreach`, `if`, `proc` and `source` are understood. Analysis commands,
recorders and terminal output are counted and left out; define the cases in
the GUI instead.

# What comes across
- `model` (the -ndm/-ndf pair: 2D frame or truss, 3D frame or truss) and
  `node`, `fix`, `mass`, `equalDOF`, `rigidLink`, `rigidDiaphragm`.
- `uniaxialMaterial` Elastic, Steel01, Steel02, Concrete01, Concrete02,
  Concrete04, Hardening, ElasticPP and Hysteretic; `nDMaterial
  ElasticIsotropic`.
- `section Elastic`, `section Fiber` with rectangular/circular patches and
  straight layers, `section ElasticMembranePlateSection`; an `Aggregator` is
  imported as its base section.
- `element` truss, corotTruss, elasticBeamColumn, forceBeamColumn,
  nonlinearBeamColumn, dispBeamColumn, zeroLength, zeroLengthSection, quad,
  bbarQuad, enhancedQuad, ShellMITC4 and beamWithHinges.
- `pattern Plain` with `load` and `eleLoad -beamUniform` / `-beamPoint`, and
  the `timeSeries` Linear, Constant, Path and Trig they reference.
- `block2D` structured four-node meshes, with the same shape functions as
  OpenSees (four corners, the optional edge midpoints and the centre).

# What is not imported
- `system`, `numberer`, `constraints`, `test`, `algorithm`, `integrator`,
  `analysis`, `analyze`, `recorder` and `print`: the GUI's own cases replace
  them.
- `block3D` meshes, `UniformExcitation` and other non-Plain patterns, and
  materials, sections or element types not listed above. Each one is counted
  in the import log instead of being skipped in silence.
- A 3D `geomTransf` orientation other than the default: local axes are
  inferred from the member geometry. A 2D model is turned into this program's
  X-Z plane (OpenSees' x-y), so its supports, forces and moments keep their
  physical meaning.

# Units
Tcl carries no unit metadata. The dialog asks which system the script's
numbers are in; the values are kept exactly as written. OpenSees' own examples
usually use kip and inches (E ≈ 30000, fy ≈ 60, lengths in inches), so choose
**US (in, kip…)** for those and **SI** for a metric script.

# Safety
No shell, file or network command from the script is ever run. A `source`
include is read only from the script's own folder, and the interpreter has a
depth limit; malformed or unsupported input is reported with the file name
and does not take the window down.
