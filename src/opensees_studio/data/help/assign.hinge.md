---
title: Assign → Frame → Hinge
group: Assign — frame
summary: The hinge sections of a BeamWithHinges member.
see_also: mechanics.fiber_sections, assign.section
order: 1480
---

A `BeamWithHinges` element concentrates the inelastic behaviour in a **hinge
length** at each end, with an elastic interior. It is the efficient way to model
a member that yields at its ends — a beam in a moment frame, a column base.

# Values
- **Hinge length at i and j** — how long the inelastic zone is. A common choice
  is a fraction of the section depth (0.5h to 1h).
- **Hinge sections** — the fibre (or elastic) section used inside the hinge
  zone, one per end; the interior uses the member's own section.

# Mechanics
The hinge length decides how much rotation the member can take before the
section's ultimate curvature is reached: a longer hinge spreads the same
curvature over more length. It is a modelling choice with a real effect on
ductility, not a numerical detail.
