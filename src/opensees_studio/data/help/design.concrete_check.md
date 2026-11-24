---
title: Design → Concrete Frame Check (ACI 318-19)
group: Design
summary: Reinforced concrete members: axial force and bending, shear, torsion, minimum steel.
see_also: define.concrete_section, design.steel_check
order: 480
---

Checks every frame member whose section is a **fibre section of concrete and
bars** — the Concrete Section Wizard's, the Section Designer's or any other — or
the elastic section the wizard made next to it (`<name> (elastic, …)`): the
reinforcement is read from the fibres, so the analysis can run on the cracked
elastic section while the design uses the bars. Stations, load sets and
combinations are those of Design → Steel Frame Check (25 stations, every
combination or every static case).

# What it checks (ACI 318-19, SI expressions in consistent units)
- **Axial force and bending** — strain compatibility, εcu = 0.003 and the
  0.85 f'c stress block over a = β1 c (22.2), bars elastic-perfectly plastic,
  for a sweep of neutral-axis depths: the interaction curve about each axis. φ
  goes from 0.65 (tied) or 0.75 (spiral) to 0.90 with the net tensile strain
  (Table 21.2.2), and φPn,max = 0.80 φP0 (tied) or 0.85 φP0 (spiral). Each
  station's Mu is compared with φMn at its Pu, using the bars on the side the
  moment puts in tension.
- **Biaxial bending** — Bresler's reciprocal load method above 0.1 f'c Ag, the
  linear load contour below.
- **Shear** — Vc = (0.17 λ √f'c + Nu/(6 Ag)) bw d, Vs = Av fyt d / s with the
  stirrups given here (the same for every member), Vs ≤ 0.66 √f'c bw d, φ = 0.75.
  bw is the gross area over the depth: exact for rectangles, conservative for T.
- **Torsion threshold** — φ 0.083 λ √f'c Acp²/pcp (22.7.4.1); above it the
  member is flagged for torsion design, which is not done here.
- **Beams** — As,min (9.6.1.2) and εt ≥ 0.004 (9.3.3.1).

Not checked: slenderness (6.6.4: run P-Delta or a buckling analysis), crack
control, development and splices, and the seismic detailing of special moment
frames. **Show ratios on model** paints the members by their governing ratio.
Verified on a simply supported beam (flexure and shear by hand, Verification
Manual D-12) and the balanced point of a column (unit tests).
