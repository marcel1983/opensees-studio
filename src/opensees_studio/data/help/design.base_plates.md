---
title: Design → Steel Connections → Base Plates (Column Bases)
group: Design
summary: Every column base of the model, checked over the design load sets.
see_also: design.base_plate, design.steel_check, design.direct_analysis, design.footings
order: 450
---

One row per **column base**: a support joint with one column framing up into
it, whose section is an AISC I-shape, rectangular HSS or round HSS / pipe.

# What decides the check
- **Support type** from the joint's restraint: both bending rotations free is a
  **pinned** base, checked concentric (bearing, plate thickness with λn', shear);
  both fixed is a **fixed** base, checked with the axial force and the reaction
  moment about the column's **major axis** (DG1 3.3, small or large
  eccentricity, anchor rods in tension); one fixed is **partial**, checked as
  fixed with a note.
- **Column kind**: the plate's cantilevers are `m = (N - 0.95 d)/2` and
  `n = (B - 0.8 bf)/2` for an I-shape, `0.95 B` for a rectangular HSS, and
  `0.8 D` both ways for a round one. N runs along the column depth d.
- **Demands**: the joint's reactions under **every alternative** of the design
  load sets the steel check uses (the direct analysis cases when they exist,
  else the combinations), so the largest compression, the largest M / P, uplift
  and the largest shear are all checked. Only static results enter.
- A moment about the column's **minor axis** is reported, not combined: Design
  Guide 1 has no biaxial method.
- **Uplift, with or without a moment** (Pu ≤ 0): a rigid plate on two rod rows
  at ±f, the concrete in compression only. While every rod stays in tension the
  rows share the uplift and the couple (T = U·nt/n ± |Mu|/(2f) with symmetric
  rows), and both rows' breakout is also checked as one group. Past that the far
  row goes slack and the concrete bears at q,max on the other side: the DG1
  3.3.2 bearing length with a negative Pu, T = q,max·Y + U. The plate is checked
  for bending over the tension rods and over the bearing block. The sign of the
  reaction moment picks the row; one axis only.
- An alternative the check cannot cover (rods in tension with no data) is never
  passed: the base reads **Requires verification** (warning colour) even when
  every other alternative is under the limit, with its load sets, Pu and Mu in
  the tooltip. **NG** still wins over it.

# Editing
Select one or more rows, change the plate (N, B, tp, steel), the concrete (f'c,
A2 / A1) or the rods (diameter, F1554 grade, count, offset f, spacing, edge
distance, embedment) and press **Apply to the selected bases**. **Size tp**
picks the thinnest standard plate (1/2 in to 4 in) whose thickness checks pass
(bearing side and tension side); a base that requires verification is not
sized. A base starts from a plate 3 in larger than the column all round, 1 in thick,
A36 on f'c 4 ksi, with four 3/4 in F1554 Gr. 36 rods. **OK** keeps the plates
in the project (`design.base_plates`); a base left at the starting plate is not
saved.

When the support also has a footing (Design → Footings), A2 of the bearing check
is the top of its pedestal, or the footing plan without one, instead of the
A2 / A1 typed here. When the rods carry both tension and shear (friction short
of the shear) the interaction of ACI 318-19 17.8.3 is checked too.
