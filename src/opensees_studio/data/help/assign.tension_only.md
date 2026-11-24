---
title: Assign → Frame → Tension Only
group: Assign — frame
summary: Make the selected members work in tension only, like rods and slender braces.
see_also: define.warehouse, assign.frame_releases, analyze.cases, define.load_combinations
order: 1395
---

A rod, a cable or a slender angle buckles as soon as it is pushed: in an X
brace only the diagonal the load stretches holds, and the other one goes
slack. **Tension only** models that, as SAP2000's tension/compression limits
do in a nonlinear case.

# Values
- **Frame member (tension and compression)** — the usual elastic member.
- **Tension only (a truss that goes slack in compression)** — the member runs
  as a truss between its two joints, with the E and A of its section, and its
  stiffness in compression is a millionth of its tension one (not zero, so an
  X whose two diagonals both shorten does not leave the bay a mechanism).

Only elastic frames with an elastic section can be tension only.

# What changes in the analysis
- **Axial force only.** Its bending, end releases and offsets do not apply,
  and its diagrams show the axial force alone. Its self weight goes half to
  each joint; a load along it (uniform, point, distributed) is refused when
  the case runs: put it on the joints.
- **Static cases are solved by Newton iteration**, even when the case says
  Linear (the run log says so), because which members work depends on the
  load.
- **Combinations do not superpose.** A combination adds the results of
  separate cases, which is only right while the same members work in each.
  Analyse each combination as a case of its own, with its patterns and their
  factors (Define → Load Cases, a static case with pattern factors), as the
  warehouse wizard does when its braces work in tension only.
- **Modal and response spectrum cases** take every member with its tension
  stiffness, engaged.
- PyNite does not model tension-only members: such a model needs OpenSeesPy.
