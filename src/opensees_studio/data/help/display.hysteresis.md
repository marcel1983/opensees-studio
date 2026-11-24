---
title: Display → Hysteresis
group: Display
summary: Force against displacement for an element or a node, over a transient.
see_also: display.time_history, mechanics.isolators
order: 1670
---

Plots one response against another (force vs displacement, moment vs rotation)
along the time history. That loop is where the energy dissipation of an element
is read: its enclosed area is the energy absorbed per cycle.

- Typical pairs: an isolator's shear force against its relative displacement (the
  bilinear loop), a plastic hinge's moment against rotation, a base shear
  against a roof displacement.
- A loop that is a straight line means the element stayed elastic; a loop that
  pinches means the model is degrading.
