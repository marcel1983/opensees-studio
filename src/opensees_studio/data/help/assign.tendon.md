---
title: Assign → Frame → Tendon (Post-Tensioning)
group: Assign — frame
summary: A post-tensioning tendon in each selected member, as its equivalent loads.
see_also: assign.temperature_load, analyze.cases
order: 1460
---

The tendon is not a member of the model: it is the push it exerts on the
concrete (load balancing), placed in a Plain load pattern.

# Profile
A parabola through three eccentricities measured along the member's **local
y**: at end i, at midspan and at end j. A horizontal 2D beam's local y is up, so
a tendon below the centroid has a negative eccentricity. For a continuous
draped tendon, give each member its own piece of the curve (the eccentricities
at a shared joint must match).

# What the member carries
- At each anchorage: the force P along the tendon at its eccentricity — an
  axial compression P, a shear P·de/dx and a moment -P·e about the centroid.
- Along the curve: the upward pressure 8·P·f/L² of a parabola of sag
  f = (e_i + e_j)/2 - e_mid (positive when the tendon dips towards -y), and the
  friction along the member.

A simply supported beam with a straight tendon below its centroid gets a
uniform moment P·e and the camber P·e·L²/(8EI); a parabolic one balances a
uniform load of 8·P·f/L². Both are pinned by the integration tests.

# Losses
- **Friction and wobble**: P(x) = P0·exp(-(μα + k·d)) from the stressing end
  (α the angle change, d the distance), the larger of the two values when
  stressed from both ends.
- **Long-term loss**: a fraction applied everywhere — creep, shrinkage,
  relaxation, and the elastic shortening of the concrete (the tendon is not
  modelled, so that loss is not computed).

Combine the pattern like any other; in a staged construction case, put it in
the stage where the tendon is stressed.
