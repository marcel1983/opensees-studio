---
title: Define → Seismic Loads (Equivalent Lateral Force)
group: Define
summary: Base shear by the code, shared between the storeys, written as load cases.
see_also: define.mass_source, define.storeys
order: 2170
---

Computes the equivalent lateral force (ELF) loads of ASCE/SEI 7-16, TBDY 2018,
RNC-07 (Nicaragua) or NSCM (Managua) and writes them as load patterns with linear static cases, one per direction:
`EQ X`, `EQ Y` and, with accidental eccentricity, `EQ X +e`, `EQ X -e`,
`EQ Y +e`, `EQ Y -e`. A Plain pattern already named that way (for instance the
empty `EQ X` the combination generator creates) gets its nodal loads replaced, so
the cases and combinations that use it keep working. Everything is one undo step.

# Values
- **Code** — ASCE/SEI 7-16 §12.8, TBDY 2018 §4.7, RNC-07 Art. 32 or NSCM 8.2. The
  spectrum values are taken from the project's design spectrum (Ground Motions →
  Target spectrum) when it has one.
- **RNC-07**: a0, soil type, group, regularity and Q (Art. 21). Without
  **Use the period** the coefficient is Ec. 3, c = S 2.7 a0 / (Q'Ω) ≥ S a0 (Art.
  32 a); with it, Ec. 13, a(T) / (Ω Q'(T)) with a ≥ S a0 (Art. 32 b). Forces are
  shared as W h (Fi = c W wi hi / Σ wj hj); group A multiplies by 1.5. The
  accidental eccentricity defaults to 10 %. RNC-07 has no approximate period
  formula.
- **NSCM**: a0, site class, risk category and Ro = R ΦP ΦE. Cs of Ec. 8.2-2 with
  the minimum FSTc β A0 / (2Ro); the period used is at most Cu Ta (Tabla 8.2.1)
  when Ta is given (**Approximate** fills it with Ct hn^x), and the forces follow
  the ASCE k exponent. The preview warns when the static method is out of its
  height limit (12 m, 6 m if irregular; 24 m and 12 m in zone Z1).
- **SDS, SD1** (g) — the design spectral accelerations. **S1** (ASCE) only drives
  the near-fault minimum of Eq. 12.8-6. **TL** — the long-period transition.
- **R** and **Ie** (ASCE) or **R**, **I** and **D** (TBDY) — the structural system's
  coefficients. They are yours to choose; the generator only applies the formulas.
- **Period T** — typed, or **Approximate**: ASCE Ta = Ct hn^x (Table 12.8-2) or
  TBDY T = Ct H^(3/4) for the chosen system, with the height of the model. A
  modal period can be typed in; ASCE limits it to Cu Ta, which is left to you.
- **Directions** — X and/or Y (a 2D model lives in the X-Z plane: X only).
- **Accidental eccentricity ±** — the storey force moved by ± the ratio (5 %)
  times the floor's extent across the load (3D).

# How it is computed
- **ASCE 7-16**: Cs = SDS / (R/Ie), at most SD1 / (T R/Ie) (or SD1 TL / (T² R/Ie)
  past TL), at least max(0.044 SDS Ie, 0.01) and, for S1 ≥ 0.6 g,
  0.5 S1 / (R/Ie). V = Cs W, and Fx = V wx hx^k / Σ wi hi^k with k = 1 up to
  0.5 s, 2 from 2.5 s and linear between. The preview names the clause that
  governs.
- **TBDY 2018**: Vt = W SaR(T) with SaR = Sae(T) / Ra(T), Ra = R/I past TB and
  D + (R/I - D) T/TB below it, and Vt ≥ 0.04 I SDS W. ΔFN = 0.0075 N Vt acts
  at the top; the rest is shared as Fi = (Vt - ΔFN) wi Hi / Σ wj Hj.
- **Weights** are the masses the analysis uses (typed masses, Define → Mass
  Source, diaphragm lumping) times g, at the storeys (Define → Storeys) or, with
  none defined, at every elevation above the base that carries mass. Heights are
  from the base. Mass that lies off the storey levels is left out of W, and the
  preview says how much.
- **Where the force goes**: to a horizontal diaphragm's retained node when that is
  where the floor's mass is (with the eccentricity as a torque F e about Z), else
  to the floor's joints in proportion to their mass (tilted so that the resultant
  acts e off the centre of mass).

Run the `EQ X` / `EQ Y` cases like any other static case, and combine them with
Define → Load Combinations (the code generators take them as Earthquake loads).
