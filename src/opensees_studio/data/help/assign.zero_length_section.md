---
title: Assign → Joint → Zero-Length Section
group: Assign — joints
summary: A full section acting between two coincident nodes.
see_also: assign.bearing, assign.zero_length, mechanics.fiber_sections
order: 1200
---

A `ZeroLengthSection` element puts a **section** (elastic, fibre or aggregated)
between two nodes at the same point. It is how a plastic hinge, a base
connection or a section-level spring is modelled: the element's deformation is
the relative displacement and rotation of the two nodes.

# Values
- **Section** — what the element is made of, as a section rather than a set of
  materials.
- The two nodes must be **coincident**; they are a deliberate pair, and Edit →
  Check Model for Duplicates leaves them alone on purpose.
- The local axes come from the element's orientation: in a 3D model the two
  coincident nodes give no direction, so the orientation is taken from the global
  axes (Y for the section's local x).
