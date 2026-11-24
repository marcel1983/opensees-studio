---
title: Define → Create Shell from 3 or 4 Nodes
group: Define
summary: A four-node shell from four selected nodes, a triangle from three.
see_also: define.section_library, assign.shell_formulation, mechanics.shells
order: 890
---

Select four nodes and a plate section, and the command builds a `ShellMITC4`;
select three and it builds a triangular `ShellDKGT` (in the order you picked
them). Walls, slabs and shear walls are shells. Change the formulation
afterwards with Assign → Area → Shell Formulation.

- The **winding** is derived from the coordinates: a click selection has no
  order, and a face built from a scrambled list is inverted or twisted. The
  order is taken counter-clockwise about the face's normal (the best-fit plane
  of the four points), and a selection that cannot form a face — coincident,
  collinear, or with one point inside the triangle of the others — is refused
  with the reason.
- The **plate section** carries E, ν, the thickness and the density. OpenSees
  wants a section for a shell, not a material: the thickness is the section's
  business.
- If the project has several plate sections you are asked which one.
