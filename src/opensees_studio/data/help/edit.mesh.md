---
title: Edit → Mesh
group: Edit and tools
summary: Subdivide members and shells, and join the mesh up.
see_also: edit.check_duplicates, mechanics.fiber_sections, mechanics.shells
order: 750
---

# What it does
- **Bars** longer than the target become equal pieces (a 10 m bar at 3 m becomes
  four elements of 2.5 m). The pieces inherit the section, the material and the
  element's own fields, and a distributed load follows them: each piece carries
  the same `q`, not a third of it.
- **Shells** larger than the target are subdivided ``m x n`` in their own natural
  coordinates, so a general quadrilateral is meshed without leaving its own
  edges, the winding (which the shell's normal depends on) is preserved, and two
  meshed shells of the same size share their common edge.
- **The joins** are what make the mesh usable: a bar is split at every node that
  lies on it (a column whose top lands in the middle of a beam, a frame drawn
  across a slab edge), and bars are split where they cross each other, so a
  crossing becomes a shared node instead of two members passing by.

# Values
- **Target size** — the longest edge a piece may have, in project units. It
  defaults to a tenth of the model (or of the selection).
- **Mesh** — the selection, or the whole model.
- **Tolerance** — how close a node has to be to a bar to count as lying on it, and
  how close two bars have to be to count as crossing. One part per million of the
  model is the default; loosen it for a drawing that was not drawn exactly.
- The summary under the form says what the mesh will add and replace before you
  accept it. A mesh that would add thousands of elements is one keystroke away
  from one that adds ten.

# Mechanics
Meshing changes the *discretisation*, not the structure: for a linear elastic
model, splitting a prismatic member does not change the answer (the test suite
checks a cantilever's tip deflection and a uniformly loaded beam before and
after). What it buys is resolution where the response varies — a plastic hinge, a
shell's bending — and what it costs is degrees of freedom.
