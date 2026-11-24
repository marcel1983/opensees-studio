---
title: Bearings and isolators: the bilinear model
group: Mechanics
summary: Kinit, Qd, α1, α2 and μ — what each one does to the hysteresis loop.
see_also: assign.bearing, concepts.model
order: 120
---

An elastomeric or sliding bearing is modelled as a **zero-length element between
two coincident nodes**: the nodes sit at the same point, and the element's
deformation is the relative displacement between them.

# Parameters (elastomeric, plasticity or Bouc-Wen)
- **Kinit** — the initial (unloaded) shear stiffness. It sets the period at
  small amplitude.
- **Qd** — the characteristic strength: the height of the hysteresis loop's
  flat part. Divided by the weight it gives the isolator's `Qd/W`.
- **α1 / α2** — the post-yield stiffness ratio before and after the second
  branch; α2 < α1 is what produces the stiffening at large displacement.
- **μ, η, β, γ** — the Bouc-Wen parameters: the hysteresis shape. β and γ
  together set whether the loop is softening, hardening or bilinear.

# Parameters (friction pendulum, flat slider)
- **μ** — the friction coefficient. The force is μ·N, so the friction model
  matters: a constant Coulomb μ, a velocity-dependent μ(v), or a μ that depends
  on the normal force.
- **R_eff** — the pendulum radius: the restoring stiffness is W/R_eff and the
  isolated period is T = 2π·√(R_eff/g).

# Mechanics
A bilinear isolator's loop encloses an area 4·Qd·(D - Dy) per cycle: that area
is the energy the bearing dissipates, and it is the reason to use one. The
**effective damping** follows from that area; the **effective stiffness** from
the secant between the loop's extremes.
- The two nodes must be **coincident**; the duplicate checker leaves them alone
  on purpose (see Edit → Check Model for Duplicates).
- A bearing is not a support: if both nodes are free to translate the isolator
  does nothing. One of them is normally restrained.
