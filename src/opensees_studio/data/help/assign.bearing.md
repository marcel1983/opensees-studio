---
title: Assign → Joint → Bearing (isolator)
group: Assign — joints
summary: An elastomeric or sliding isolator between two coincident nodes.
see_also: define.friction_library, mechanics.isolators
order: 1220
---

# Elements
- **elastomericBearingPlasticity** — bilinear shear with return-mapping
  plasticity.
- **elastomericBearingBoucWen** — smooth Bouc-Wen shear.
- **flatSliderBearing** — friction, no restoring stiffness.
- **singleFPBearing** — single friction pendulum, with the radius R_eff.

# Values — elastomericBearingPlasticity / elastomericBearingBoucWen
- **Kinit** — initial shear stiffness.
- **Qd** — characteristic strength (the loop's flat part).
- **alpha1, alpha2** — post-yield stiffness ratios; **mu, eta, beta, gamma** for
  the Bouc-Wen shape.

# Values — flatSliderBearing / singleFPBearing
- **Friction model** — a named model from Define → Friction Models, plus its
  coefficient.
- **R_eff** — the pendulum radius (single FP), which sets the isolated period
  T = 2π√(R_eff/g).
- **Kinit** — the initial stiffness before sliding.

# Modelling notes
- The two nodes must be **coincident**: the isolator *is* the relative movement
  between them, and one of them is normally restrained to the ground.
- A bearing in 2D and 3D differ in which DOF are mobilised; a 3D bearing
  restrains the vertical and the two rotations it does not slide in.
- The property dock shows the derived yield displacement and force, and the
  isolated period, so the numbers can be sanity-checked before running.
