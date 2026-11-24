---
title: Define → Add Plain Load Pattern
group: Define
summary: A named group of loads, with the time series that drives it.
see_also: assign.load, assign.distributed_load, define.linear_ts
order: 1110
---

A `Plain` pattern holds the nodal loads and the distributed element loads
applied together, and points at a time series that scales them in time. Cases
reference patterns by id, so the same loads can be used by several cases.

- One pattern per load type (dead, live, wind, earthquake) is the usual
  arrangement: a static case can then combine them, and a transient can apply
  gravity first and the earthquake after `loadConst`.
- A load pattern with no loads is legal but does nothing.

# Self weight
- **Self-weight multiplier** — 1 adds the weight of every frame whose section
  has a **unit weight** (gamma, force per volume, set in the Section Library):
  gamma times A per unit length, downward (-Z, in 2D and in 3D), split over the
  member's local axes, so a column takes it axially and a sloped rafter partly
  axially. 0 leaves it out.
- A new project starts with a **DEAD** case: a time series, a pattern with a
  self-weight multiplier of 1 and a linear static analysis that runs it. The
  default section is steel (gamma = 77 kN/m³), so a frame drawn on a fresh
  model already has a gravity result. A **plate section** (shell) has a unit
  weight too: each ShellMITC4 takes gamma times h per unit area as consistent
  nodal forces over its real shape.
- A **fiber section** has a unit weight too, applied to its gross area (patches
  plus bars plus loose fibres: an RC section comes out heavier by its steel
  ratio, 1-3 %). An **aggregator** weighs what the section it wraps weighs.
- **Trusses** and **BeamWithHinges** members carry their own unit weight (in the
  Properties panel): a truss bar sends half its weight to each joint, a
  BeamWithHinges member takes gamma times its elastic area A per length.
  Assign → Frame → Hinge keeps the member's weight per length. 2D quads,
  zero-length elements, bearings and links carry no self weight.
