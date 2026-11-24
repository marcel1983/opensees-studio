---
title: Assign → Frame → Geometric Transformation
group: Assign — frame
summary: How an element's local axes relate to the global ones, and how large displacements are handled.
see_also: assign.local_axes, assign.integration, mechanics.static
order: 1250
---

# Values
- **Linear** — small displacements; the stiffness matrix is built once. Correct
  for most linear work and the default.
- **PDelta** — includes the second-order effect of axial force on bending: a
  compressed column loses lateral stiffness. This is what a stability or
  second-order analysis needs.
- **Corotational** — large displacements and rotations: the element's rigid-body
  motion is removed and the deformation is measured in a frame that follows it.
  Needed for a cable, a snap-through, or a member that rotates appreciably.

# Mechanics
With *P-Delta*, the geometric stiffness subtracts from the material stiffness in
proportion to the axial force. The **critical load** is where the two cancel; a
model that becomes singular as the load rises is telling you it has reached it.
The transformation also defines the local axes: for a member whose axis is
vertical, the local x/y orientation comes from the transformation, and the sign
of a diagram follows from it. A member's own rotation about local x is set in
**Assign → Frame → Local Axes**.
