---
title: Assign → Joint → Diaphragm
group: Assign — joints
summary: A floor rigid in its own plane (OpenSees rigidDiaphragm).
see_also: define.storeys, define.mass_source, mechanics.constraints, assign.remove_constraints
order: 2190
---

Every constrained joint follows the **retained** node in the two in-plane
translations and the rotation about the perpendicular axis; the out-of-plane
DOF stay free, so slabs still bend and columns still shorten.

# Values
- **Joints** — every joint of a storey (resolved when the model is built, so
  joints drawn later join the floor; supports in the plane are left out), or the
  selected joints.
- **Perpendicular axis** — Z for a floor; X or Y for a vertical rigid plane.
- **Retained node** — a new node at the centre of mass of the joints (their
  effective mass, the mass source included), or an existing selected node.

# Mechanics
A retained node that no element touches has no stiffness out of its plane: the
runner fixes those three DOF itself, OpenSees' own recipe. A case left at the
**Plain** constraint handler runs with **Transformation**: Plain drops a
diaphragm with a warning and then solves a singular system without reporting
failure. A joint can belong to one diaphragm only, and not also be the
constrained node of an equalDOF or rigid link; a joint out of the plane is
refused (OpenSees would silently drop it).

A joint of the diaphragm may not **retain** another constraint either: no
equalDOF or rigid link retained by it. The Transformation handler cannot chain
such constraints (it keeps one per node and numbers the chained one wrong) and
gives wrong results without an error, so the model check refuses them; leave
that joint out of the floor.

**Frame end releases** at a diaphragm joint work, without such a chain:

- an elastic beam-column with an elastic section is released inside the element
  (`-releasez` / `-releasey` for M3 / M2, a zero `G J` for torsion), exactly, and
  at the face of a rigid end zone when the end is offset;
- any other member with elastic properties (and an elastic beam-column with a
  point, partial or trapezoidal load, a consistent mass matrix, or partial
  fixity at that end, which OpenSees cannot condense) hangs the end off a hidden
  node held by penalty springs 10^5 times the member's own stiffness: results
  within about 10^-7 of the exact ones;
- a fibre member, or such a spring-held end with an end offset, is refused with
  a remedy.

The canvas draws the diaphragm as spokes from the retained node (a small cube).
Deleting the retained node deletes the diaphragm.
