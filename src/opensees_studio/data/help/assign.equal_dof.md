---
title: Assign → Joint → equalDOF
group: Assign — joints
summary: Make one node's DOF follow another node's.
see_also: mechanics.constraints, assign.support
order: 1170
---

The first node selected is the **retained** (master) node, the second the
**constrained** (slave), and the DOF you tick are the ones tied. Uses: a rigid
floor, a rigid link, a hinge made of two coincident nodes.

# Values
- **DOF numbers** — 1-based, in the order the model uses them. A 3D frame: 1 = Ux,
  2 = Uy, 3 = Uz, 4 = Rx, 5 = Ry, 6 = Rz. A 2D model lives in the X-Z plane: a 2D
  frame has 1 = Ux, 2 = Uz, 3 = Ry, a 2D truss 1 = Ux and 2 = Uz. The dialog lists
  the model's own.
- Ticking 1 and 2 on a pair of nodes at the same level is a diaphragm in plan.

# Mechanics
Tying DOF removes them from the unknowns: the constrained node's displacement is
whatever the retained node's is. It does not add stiffness anywhere else — a
rigid floor is also, physically, a constraint that distributes horizontal force,
which is exactly what this does.

A node takes one constraint, and constraints do not chain: a node an equalDOF
constrains may retain another equalDOF or rigid link only when its own equalDOF
ties every DOF. OpenSees' Transformation handler (every eigen analysis uses it)
solves any other chain, a node constrained twice, or a loop without an error
into wrong results, so the model check refuses them. Tie each node straight to
one retained node instead.

A frame end released at the constrained node is made without a further
constraint, as at a diaphragm joint (see Assign → Frame → Releases/Partial
Fixity).
