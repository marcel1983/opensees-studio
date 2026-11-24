---
title: Assign → Joint → Zero-Length Element
group: Assign — joints
summary: A uniaxial material in each global DOF between two coincident joints.
see_also: assign.zero_length_section, assign.link, mechanics.constraints
order: 1190
---

A `zeroLength` element connects two joints at the same point with one
**uniaxial material per chosen global DOF** (1..ndf). It is the general
building block for a plastic hinge, a base isolator, a soil spring or a damper:
the element's deformation is the relative displacement or rotation of the two
nodes.

# Values
- **DOF** — tick each global direction that carries a material. In a 2D model
  the DOFs are Ux, Uz and Ry; in a 3D model Ux, Uy, Uz, Rx, Ry and Rz. The
  dialog shows the model's own DOF names.
- **Material** — one uniaxial material per ticked DOF, in the same order as the
  ticks. Any uniaxial material works (`Elastic`, `Steel02`, `ElasticPPGap`,
  `ViscousDamper`, …).
- **-doRayleigh** — include the element's initial stiffness in the
  stiffness-proportional Rayleigh damping. OpenSees leaves zeroLength elements
  out by default, so an isolator whose initial stiffness anchors
  Kinit-proportional damping must set it.

# Mechanics
- The two joints must be **coincident**. They are a deliberate pair: Edit →
  Check Model for Duplicates leaves them alone, because merging them would
  delete the element.
- A zeroLength is not a support: if both nodes are free the element carries no
  load path. One node is normally restrained, or connected to the rest of the
  model.
- For a full section (P, Mz, My, T, Vy, Vz at once) use Assign → Joint →
  Zero-Length Section instead.

# Local axes
`zeroLength` uses the global axes for its DOFs; unlike `twoNodeLink` it has no
local orientation. Use `twoNodeLink` when the materials must act along a
member's local axes.
