---
title: Display → Pushover Curve
group: Display
summary: Base shear against the control displacement.
see_also: mechanics.pushover, analyze.cases
order: 1680
---

The capacity curve of a pushover case: what the structure carried as it was
pushed. The axes are labelled in the project's display units.

# Reading it
- The initial slope is the elastic stiffness; a kink is first yield; a softening
  branch means a mechanism is forming.
- The values come from the case's own recorders: the base shear is the sum of the
  support reactions in the pushed direction, at every step.
- A curve that stops early stopped converging — the log says at which step and
  why, and the results keep what was computed.
