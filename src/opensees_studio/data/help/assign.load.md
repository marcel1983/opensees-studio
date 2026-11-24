---
title: Assign → Joint → Loads
group: Assign — joints
summary: Nodal forces and moments, applied in a load pattern.
see_also: define.plain_pattern, assign.distributed_load
order: 1180
---

# Values
- **Fx, Fy, Fz** — forces; **Mx, My, Mz** — moments, in the units the labels
  show (the project's).
- **Pattern** — which load pattern the load belongs to; a new one creates a
  default linear time series with it. The pattern used last is offered first.
- **Existing loads** — **Add** sums the load with the ones the joints already
  have in that pattern; **Replace** removes those first; **Delete** only
  removes them (the values are not used). Other patterns are not touched.
- Sign convention: global axes. Gravity is a negative Fz in a Z-up model.

# Mechanics
A nodal load is applied at a node; it does not depend on the members touching
it. A load on a node with no stiffness in that direction (an unrestrained node
that only touches trusses, say) produces a singular system rather than a large
displacement, so the solver's refusal is a modelling message, not a failure of
the solver.
