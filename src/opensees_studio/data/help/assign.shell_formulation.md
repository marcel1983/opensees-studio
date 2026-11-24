---
title: Assign → Area → Shell Formulation
group: Assign — areas
summary: Which OpenSees shell element the selected shells are: MITC4, DKGQ, NLDKGQ, DKGT.
see_also: define.create_shell, assign.surface_load, mechanics.shells
order: 900
---

Every shell keeps its nodes, section, loads and results; only the element
OpenSees builds changes. Pick a pair: the first applies to the selected
quadrilaterals, the second to the triangles.

- **MITC4 / DKGT** — the default. `ShellMITC4` (Dvorkin-Bathe mixed
  interpolation) is a thick-shell element with transverse shear; it is what the
  importers create.
- **DKGQ / DKGT** — `ShellDKGQ` (Lu, Xie, Zhang): a Discrete Kirchhoff plate with
  a generalised-conforming membrane and a real drilling (in-plane rotation)
  stiffness. The better choice for thin slabs and for walls whose edges frame
  into beams or columns in their own plane. It has no transverse-shear strain,
  so its V13/V23 resultants read zero: take shear from equilibrium.
- **NLDKGQ / NLDKGT** — the geometrically nonlinear versions (updated
  Lagrangian), for large displacements: wall or slab buckling, catenary action.
  In a linear step they behave as DKGQ/DKGT.

`ShellDKGT` is the triangle of the family, for panels a quadrilateral mesh cannot
cover. Every formulation takes the plate sections of Define → Section Library
(elastic, layered or fibre) and reports the same eight stress resultants. Verified
against the simply supported plate and the Scordelis-Lo roof in the Verification
Manual. The SAP2000 and IFC exporters write every quadrilateral as an area or
a surface member whatever its formulation, and leave triangles out, listed in
their report.
