---
title: Assign → Frame → End (Length) Offsets
group: Assign — frame
summary: Rigid end zones at the joints, e.g. the part of a beam inside a column.
see_also: assign.insertion_point, assign.frame_releases
order: 1310
---

# Values
- **End-I / End-J length** — the offset measured along the member from each
  joint, typically half the depth of the member it frames into.
- **Rigid-zone factor** — the part of each offset that is rigid (0 to 1). The
  flexible length is `L - factor × (length i + length j)`.
- **Automatic from connectivity** — instead of typed lengths, each end takes the
  largest half-extent, measured along this member, of the section of the other
  frame members that meet it at that joint (SAP2000 "automatic from
  connectivity"): a 0.4 m column gives a beam 0.2 m at that end. Members parallel
  to it and members whose section size is unknown add nothing. The lengths are
  worked out once, when you press OK, and stored like typed ones (change the
  geometry and assign again).

# Mechanics
The rigid zones are `geomTransf ... -jntOffset`, so they add no DOF. The end
forces, and the force diagrams, are those of the flexible part, at the faces of
the rigid zones. Loads are still given along the whole joint-to-joint length:
the part on a rigid zone goes straight to its joint as a force and the moment of
that force about the joint. A 3D Corotational transformation ignores joint
offsets in OpenSees 3.8, so the combination is refused.
