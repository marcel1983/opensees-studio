---
title: Define → Friction Models
group: Define
summary: The friction laws the sliding bearings use.
see_also: assign.bearing, mechanics.isolators
order: 970
---

Isolators that slide need a friction model; elastomeric bearings do not.

- **Coulomb** — a constant coefficient μ. The simplest, and adequate when the
  sliding velocity is low.
- **VelDependent** — μ depends on the sliding velocity (a lubricated or PTFE
  interface heats up and changes as it moves).
- **VelNormalFrcDep** — μ depends on the velocity *and* on the normal force, for
  bearings whose normal force changes during the motion.

A bearing points at a friction model by id; the model's parameters are shared,
so changing one changes every bearing that uses it.
