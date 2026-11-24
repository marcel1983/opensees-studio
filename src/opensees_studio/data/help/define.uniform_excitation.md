---
title: Define → Add Uniform Excitation
group: Define
summary: A ground motion applied to every support at once.
see_also: mechanics.transient, define.path_ts, mechanics.ground_motions
order: 1120
---

The usual way to run a time history: one acceleration record, applied in one
direction, at every restrained support.

# Values
- **Direction** — the DOF driven: 1 = X, 2 = Y, 3 = Z (vertical) in 3D; 1 = X and
  2 = Z (vertical) in a 2D model, which lives in the X-Z plane.
- **Record / series** — the acceleration series, and optionally its velocity and
  displacement; the application derives them from the acceleration if you do not
  supply them.
- **Factor** — the scale applied to the record.

# Mechanics
The excitation is applied as an inertial load (`-accel`), so the structure sees
the ground acceleration and the supports move with it. For supports that move
differently (a long bridge), use an imposed support motion pattern instead.
