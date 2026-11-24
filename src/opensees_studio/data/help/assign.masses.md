---
title: Assign → Joint → Masses
group: Assign — joints
summary: The lumped mass at the selected nodes.
see_also: mechanics.modal, assign.equal_dof
order: 1160
---

# Values
- **mx, my, mz** — translational mass; **Ixx, Iyy, Izz** — rotational inertia.
  A mass of zero in a direction means that direction carries no inertia.
- Masses are what a modal or a transient case needs. A static case ignores them.
- Gravity is not a mass: an acceleration record acts on the mass (`-accel`), so a
  model with no mass has nothing for an earthquake to shake.

# Mechanics
- The period of a mode is T = 2π√(M/K): the mass you assign is the M half of
  that. Getting it wrong scales every period (and every spectral demand read at
  those periods).
- A common convention is to lump the seismic mass of a floor at its master node,
  which is also where equalDOF ties the floor together.
- Mass can also come from a section's `rho`, distributed over the element.
