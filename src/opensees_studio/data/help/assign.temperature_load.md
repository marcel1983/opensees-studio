---
title: Assign → Frame → Temperature Load
group: Assign — frame
summary: A temperature change of the selected members: uniform, and across each axis.
see_also: assign.distributed_load, analyze.cases
order: 1340
---

The member's temperature changes by `ΔT + g_y·y + g_z·z` at the point `(y, z)` of
its cross section, in the member's local axes:

- **α** — the coefficient of thermal expansion, about 1.2e-5 per °C for steel and
  for concrete;
- **Uniform ΔT** — heats (positive) or cools the whole section: a free member grows
  `α ΔT L`, a member held at both ends takes a compression `EA α ΔT`;
- **Gradient along local y / z** — the temperature difference per unit depth,
  `(T on the + face - T on the - face) / depth`. A free member bends to a
  curvature `α g` toward the cooler face; a member held at both ends takes a
  constant moment `EI α g`. Which axis is "up": a horizontal member's local
  **y** points up in a **2D** model, its local **z** in a **3D** one (local y is
  then horizontal), so a hot top face is a positive `gradient_y` in 2D and a
  positive `gradient_z` in 3D.

# How it is solved
OpenSees' elastic frame elements take no thermal load, so the member is held
fixed, its fixed-end forces are applied to the structure with the opposite sign,
and the fixed-end forces are added back to the member's end forces. The
displacements, reactions, force diagrams, combinations and the steel check then
see the real member forces: `N = EA (ε - α ΔT)`, `M = EI (κ - α g)`.

# Limits
- Elastic beam-columns with an elastic section (property modifiers on A and the
  inertias apply), **without end releases, end offsets or an insertion point**:
  the action refuses other members before changing anything.
- **Static cases only**, under LoadControl with a Linear or Constant time series
  (a case with N steps applies it in N parts). Other case types refuse a pattern
  that carries temperature loads.
- The load goes into the active Plain pattern (a default one is created if there
  is none); Edit → Mesh and Replicate carry it to the new members.
