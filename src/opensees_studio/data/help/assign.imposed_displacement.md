---
title: Assign → Joint → Imposed Displacement
group: Assign — joints
summary: A static displacement of the selected joints: a support settlement.
see_also: assign.support, assign.load
order: 1430
---

Imposes a displacement on one DOF of each selected joint, in the load pattern you
pick (OpenSees `sp` in that pattern). On a **restrained** DOF the support moves by
that much — a settlement, the classic case. On a **free** DOF the joint is held
at that value for the cases that run the pattern, as if a support were there.

The application removes the support's own constraint before imposing the new
value, and runs such a case with the **Transformation** constraint handler even
when it is set to Plain: Plain silently ignores a nonzero imposed value.

# Values
- **DOF** — the model's own DOFs: Ux, Uy, Uz, Rx, Ry, Rz in 3D; Ux, Uz, Ry in a
  2D frame (the X-Z plane).
- **Value** — length (or radians for a rotation), in the global sign convention:
  a settlement is negative Uz.

Check: a two-span continuous beam whose middle support settles d has the middle
reaction 6 E I d / L³ — the application matches it.
