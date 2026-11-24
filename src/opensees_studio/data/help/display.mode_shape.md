---
title: Display → Mode Shapes
group: Display
summary: Animate the modes of a modal case.
see_also: mechanics.modal, display.deformed
order: 1590
---

One mode at a time, animated, with the period and the modal participation
reported so the mode can be identified.

- Mode 1 is not always the one you expect: a torsional mode can come first in an
  irregular plan, and the participation factors are how you see it.
- The signs of a mode shape are arbitrary; the application normalises them so two
  runs look the same.
- A repeated eigenvalue (a symmetric structure) gives any two orthogonal shapes
  of that subspace; the application orthogonalises them before display.
- Hover a joint while a mode is on screen: the tooltip is a box with the joint's
  label, the mode and its period, and the joint's component per DOF in that
  mode. The values are the stored eigenvector, so they compare with each other
  (which joint moves most, in which direction), not with a length. Members show
  no tooltip while a mode is on screen.
