---
title: Assign → Frame → Pile Soil Springs (p-y, t-z, q-z)
group: Assign — frame
summary: Nonlinear soil springs along a pile, from its diameter and the soil layers.
see_also: assign.line_springs, define.material_library
order: 1450
---

Select the pile's members (a vertical chain of frame members) and give the pile
diameter, the elevation of the ground and the soil layers (depths below the
ground, with the effective unit weight; the undrained strength su for clay; the
friction angle and the initial modulus of subgrade reaction k for sand). Every
pile joint in the soil is tied to a new fixed ground joint at the same point by
a zero-length element with:

- **p-y** springs in each horizontal direction (`PySimple1`) — soft clay after
  Matlock (1970): pu = min((3 + γ'z/su + 0.5 z/D)·su·D, 9·su·D),
  y50 = 2.5·ε50·D (ε50 0.02/0.01/0.005 for su below 48/96 kPa/above); sand
  after API RP 2A: pu from C1, C2, C3 of the friction angle, the curve
  A·pu·tanh(k·z·y/(A·pu)) with A = max(0.9, 3 - 0.8 z/D);
- a **t-z** spring along the axis (`TzSimple1`) — clay f = α·su with API's α
  (0.5·ψ^-0.5 for ψ = su/sv' ≤ 1, else 0.5·ψ^-0.25), sand f = 0.8·sv'·tan(φ - 5°);
  z50 = 0.0025·D;
- at the tip, a **q-z** spring (`QzSimple1`) — clay q = 9·su, sand q = Nq·sv'
  with API's Nq (8 at 20° to 50 at 40°); z50 = 0.0125·D.

Each spring carries the soil of half of each member next to its joint, so mesh
the pile finely (a joint every half diameter to one diameter near the head).
Values are in the project's units. Pushed down to failure, the pile reaches
the sum of its shaft and tip capacities, and sideways its lateral springs'
(integration tests). The materials are ordinary entries of the Material
Library: adjust any of them by hand.
