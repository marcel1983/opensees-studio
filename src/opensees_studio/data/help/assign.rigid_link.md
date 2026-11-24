---
title: Assign → Joint → Rigid Link
group: Assign — joints
summary: Tie two joints with OpenSees rigidLink (beam or bar).
see_also: mechanics.constraints, assign.remove_constraints
order: 2200
---

# Values
- **beam** — the constrained node moves with the retained one as a rigid body:
  its translations include the rotation times the lever arm, and its rotations
  equal the retained node's. Needs rotations (ndf 3 in 2D, 6 in 3D).
- **bar** — only the translations are tied, as an inextensible bar would.
- **Retained / constrained node** — the two selected joints.

# Mechanics
Like a diaphragm, a rigid link is a constraint the Plain handler cannot enforce,
so the case runs with Transformation. The canvas draws it as a thick orange bar.

The retained node must not itself be constrained (unless by an equalDOF of every
DOF), and the constrained node takes no other constraint: see equalDOF. Two rigid
beam links in a row are one rigid link from the first node to the last.

A frame end released at the constrained node is made without a further
constraint, as at a diaphragm joint (see Assign → Frame → Releases/Partial
Fixity).
