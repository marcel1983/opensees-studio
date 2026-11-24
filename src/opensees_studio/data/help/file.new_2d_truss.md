---
title: File → New 2D Truss
group: File
summary: A planar truss: ndm = 2, ndf = 2, no rotational degrees of freedom.
see_also: file.new_2d_frame, concepts.model
order: 210
---

Creates a project with two degrees of freedom per node (Ux, Uz: the model is in
the X-Z plane, Z up). Use it for a
genuine pin-jointed truss: with no rotational DOF there are no empty rows in the
stiffness matrix, so the solver does not have to be told what to do with a
rotational DOF that carries no stiffness.

- Members are `TrussElement` or `CorotTrussElement`, each with a material and an
  area. A member with no moment connection is what a truss is.
- Anything that needs bending (a beam, a frame) belongs in File → New 2D Frame.
- Applying a moment to a node of this model does nothing: there is no DOF for it.
