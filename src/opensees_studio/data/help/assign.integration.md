---
title: Assign → Frame → Beam Integration
group: Assign — frame
summary: How many points along a member the section response is sampled at.
see_also: mechanics.fiber_sections, assign.geom_transf
order: 1270
---

# Values
- **Rule** — `Lobatto` (points at the ends and inside), `Legendre`, `NewtonCotes`,
  `Radau`, `Trapezoidal`, `Simpson`, or `HingeRadau` variants for
  `BeamWithHinges`.
- **Points** — how many integration points. Three to five is typical; a
  force-based member with a fibre section needs enough points to follow the
  curvature (often 5 to 7 for a member that yields).

# Mechanics
The member's flexibility is integrated from the *section* response at those
points: a fibre section that yields at mid-span but is only sampled at the ends
is not seen to yield. More points is more accurate and more expensive — the cost
is a section evaluation per point per iteration, per element.
