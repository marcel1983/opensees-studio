---
title: Define → Concrete Creep & Shrinkage (fib MC2010)
group: Define
summary: A time-dependent concrete material from the mix, the exposure and the cement.
see_also: analyze.cases, define.material_library
order: 1440
---

Builds a `TDConcreteMC10` material (OpenSees, after Tosic): creep by
superposition of the stress history and shrinkage, both with the equations of
the fib Model Code 2010 (5.1.9.4). Enter, in the Model Code's units:

- **fcm** — mean compressive strength at 28 days, MPa;
- **relative humidity** (40 to 99 %) and the **notional size h0 = 2·Ac/u** in mm
  (Ac the section area, u the perimeter exposed to drying);
- the **cement class** (32.5N; 32.5R/42.5N; 42.5R/52.5N/R) and the age at which
  **drying starts** (end of curing);
- the **analysis time of casting**: give each pour its own material, cast when
  its stage builds it.

The window previews the creep coefficient φ(t, t0) and the shrinkage εcs at a
few ages. Stresses are stored in the project's unit; the modulus is
Eci = 21500·(fcm/10)^(1/3) MPa.

# Using it
Use the material in fibre sections or bars, and run a **staged construction**
case marked **time-dependent**: its time is the concrete age in days, each stage
applies its loads at once and then holds them for its duration (creep on), with
geometrically spaced time steps. Elastic sections do not creep. A column loaded
at 28 days follows the Model Code's eps = stress/Eci·(1 + phi) + eps_cs within 2 % over
ten thousand days (integration test). A member that only shrinks, with nothing
compressing it, cracks in this material as it would in reality: give the
analysis enough time steps (the creep and shrinkage of a step are computed from
the state at its start).
