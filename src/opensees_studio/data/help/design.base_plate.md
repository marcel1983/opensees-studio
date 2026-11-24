---
title: Design → Connection Calculators → Base Plate & Anchors (DG1, ACI 318)
group: Design
summary: A column base plate and its anchor rods: bearing, plate thickness, rods, breakout, shear.
see_also: design.bolted_connection, design.chapter_j
order: 460
---

A calculator (LRFD, project units): it keeps nothing in the project. Enter the
column (d, bf), the plate (N along d, B, tp, Fy), the concrete (f'c and the
supporting area A2), the anchor rods (diameter, futa, how many on the tension
side and in all, the offset f of the rod line from the plate centre, their
spacing, edge distance and embedment) and the demands. With one support joint
selected, **Demands from the selected support** reads Pu, Mu and Vu from its
reaction in a solved static case.

# Checks
- **Concrete bearing** — fp,max = 0.65·min(0.85 f'c √(A2/A1), 1.7 f'c) (AISC J8).
- **Plate thickness** — Design Guide 1: concentric with l = max(m, n, λn');
  small eccentricity (e ≤ e,crit) with the bearing length Y = N - 2e; large
  eccentricity with Y from the quadratic of DG1 3.3.2 and the rod tension
  T = q,max·Y - Pu, the plate also bending over the rods.
- **Anchor rods** (ACI 318-19 Chapter 17, cast-in, cracked concrete) — steel
  0.75·Ase·futa in tension (Ase = 0.75 Ab), concrete breakout of the tension
  group 0.70·(ANc/ANco)·ψed·Nb with Nb = 10 λ √f'c hef^1.5; shear by friction
  0.75·0.55·Pu or by the rods 0.65·0.6·Ase·futa, the larger.

**Uplift (Pu ≤ 0), with a moment or not.** Rigid plate on two rod rows at ±f,
concrete in compression only: with every rod in tension the rows share the
uplift and the couple (plus a group breakout check of both rows); past that the
far row goes slack and the concrete bears at q,max, Y from DG1 3.3.2 with a
negative Pu and T = q,max·Y + U. The summary lists the tension of each row
(Mu > 0 pulls the row at +f) and the concrete's compression C. Rods in tension
with no diameter or futa read **Requires verification**.

Not checked: pullout and side-face blowout, anchor reinforcement, grout and the
column-to-plate weld. Verified against the DG1 and ACI expressions by hand
(unit tests).
