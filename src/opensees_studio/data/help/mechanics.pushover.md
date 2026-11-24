---
title: Pushover: displacement control and what it produces
group: Mechanics
summary: Pushing the structure to a target displacement to see how it yields.
see_also: mechanics.static, display.pushover
order: 70
---

A pushover case applies the pattern's load while increasing a **control
displacement** at a chosen node and DOF, recording the base shear at every step.
It is monotonic: the point is the sequence in which members yield and where the
capacity curve softens, not the cycling.

# Parameters
- **Control node and DOF** — where the displacement is imposed, usually the roof
  in the lateral direction (in 3D: DOF 1 for X, 2 for Y, 3 for Z, 4-6 for
  rotations; in a 2D model: 1 for X, 2 for Z, 3 for the rotation Ry). A positive
  target on a 2D rotation turns about +Y, the global convention.
- **Target displacement** — how far the node is pushed. It comes from a design
  displacement, a code formula, or a fraction of the height.
- **Steps and increment** — the target divided into steps. Too few and the
  solver can jump past a limit point.
- **Algorithm and convergence test** — Newton-family iterations with a
  displacement or energy test; a pushover that fails to converge is reporting a
  real limit, not necessarily a bug.

# Mechanics
The base shear vs roof displacement curve is the structure's capacity. On it:
- the **initial slope** is the elastic stiffness;
- **yielding** of the first member shows as a kink;
- a **softening** branch means a mechanism is forming;
- the **overstrength** is how much more the structure carries than its first
  yield, and the **ductility** is the displacement at the target over the yield
  displacement. Both are read off the curve by hand or by a bilinear fit.
