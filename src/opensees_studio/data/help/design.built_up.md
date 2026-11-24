---
title: Design → Built-Up Shapes
group: Design
summary: Welded I-shapes and plate girders defined from their plates.
see_also: design.steel_check, design.basis
order: 410
---

A doubly symmetric I-shape welded from three plates: its **name**, the depth
**d**, the flanges **bf × tf**, the web **tw** and, for a plate girder, the
clear spacing **a** of its transverse web stiffeners (0 = none). The table
shows the area, Ix, Zx and the flange and web classes as you type.

# Using it
A section whose name is a built-up shape's name — or a member's shape override
in the Steel Frame Check — is checked with the shape's properties. With
**Add an analysis section…** ticked, OK also adds an elastic section with those
properties (E = 29 000 ksi, G = 11 200 ksi, oriented as a rolled shape's) for
every shape no section is named after yet; assign it to the members.

# What is different from a rolled shape
- The flanges' slenderness limits take `kc = 4 / sqrt(h/tw)` (0.35 to 0.76):
  `0.64 sqrt(kc E/Fy)` in compression (E7) and `0.95 sqrt(kc E/FL)` in
  flexure (F3), Table B4.1 cases 2 and 11.
- Flexure follows F2/F3, F4 (noncompact web) or F5 (slender web: a plate
  girder, with Rpg).
- Web shear (G2.1) has no rolled-shape exception (φ = 0.9 always) and takes the
  stiffeners: `kv = 5 + 5/(a/h)²` for `a/h <= 3`, else 5.34. Tension field
  action (G2.2) is not counted, which is conservative. A web over F13.2's
  proportion limit, or with `h/tw > 260` and no stiffeners, gets a note.
- The steel is the **Built-up I** family's grade of Design → Design Basis
  (A572 Gr. 50 by default in the Manual defaults).

Properties neglect the welds: `A = 2 bf tf + h tw`, `Ix = (bf d³ - (bf - tw) h³)/12`,
`J = (2 bf tf³ + (d - tf) tw³)/3`, `Cw = Iy ho²/4`. Double angles, boxes and
laced or battened columns are not covered yet.
