---
title: Assign → Joint → Joint Pattern Values
group: Assign — joints
summary: Give the selected joints a joint pattern's values: a linear formula or hydrostatic.
see_also: define.joint_patterns, assign.surface_load
order: 1410
---

Computes a value for every selected joint and merges it into a joint pattern
(an existing one, or a new one named here). The range of the values is shown
before OK.

# How the values are computed
- **X, Y, Z multipliers** — `A·x + B·y + C·z + D` at each joint, with A, B, C per
  length and D unitless.
- **Z coordinate at zero pressure and weight per unit volume** — `w·(Z₀ - z) + q`:
  zero at the free surface `Z₀`, growing with depth at the unit weight `w`, plus
  an optional uniform `q`. With `w` the fluid's weight per volume (9810 N/m³ for
  water) the values are the hydrostatic pressure itself: apply them with a
  surface load by this pattern and a multiplier of 1.

# Restriction and existing values
- **Zero negative values** (the default) keeps a hydrostatic pressure from pulling
  on the joints above the free surface; **zero positive values** does the
  opposite; **use all values** keeps them as computed.
- **Replace**, **add to** or **delete** the values the pattern already holds for
  the selected joints. Delete ignores the formula.

One undo step takes the whole assignment back.
