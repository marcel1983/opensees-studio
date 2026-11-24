---
title: Assign → Joint → Link
group: Assign — joints
summary: A twoNodeLink or a Triple Friction Pendulum between two selected joints.
see_also: assign.bearing, define.friction_library
order: 1210
---

# twoNodeLink
One uniaxial material in each local direction you tick: 1 axial (local x),
2 and 3 shear, 4 to 6 rotations (2D: axial, shear, rotation). Use it for a
viscous damper (`ViscousDamper`), a gap or hook (`ElasticPPGap`), a hinge spring
(`ModIMKPeakOriented`), an isolator made of any hysteretic material, or a panel
spring. The local axes are OpenSees' (x from i to j); coincident joints need an
**orientation** "x1 x2 x3 y1 y2 y3" (the dialog proposes x vertical, y along X).
Optional element mass and stiffness-proportional Rayleigh damping.

# Triple Friction Pendulum (3D)
Three friction models (surfaces 1 to 3, the two inner surfaces share the first),
a vertical material and three rotational ones, the effective radii L1 to L3 and
the displacement limits d1 to d3, the axial load W used for the initial friction,
the yield displacement uy, the tension stiffness kvt, the minimum vertical force
and the tolerance. Apply the gravity load in a case of its own, in steps, and use
it as the **preload** of the dynamic case: the pendulum needs its axial load
before it can slide (as OpenSees' own examples do).

ElastomericX, LeadRubberX and HDR are not offered yet: with realistic inputs their
vertical response in OpenSees 3.8 could not be validated; use the elastomeric
bearings of Assign → Joint → Bearing.
