---
title: Define → Add Default Materials
group: Define
summary: The steels, concretes and masonry every new project starts with.
see_also: define.material_library
order: 950
---

File → New and New Model start every project with these materials, so a section
can be given one without a trip to the library. This command adds the ones an
older project lacks (by name); the materials it already has are not touched.

| Name | Material | E | Strength | Weight |
|---|---|---|---|---|
| A36 | ASTM A36 | 29000 ksi | Fy 36, Fu 58 ksi | 490 lb/ft³ |
| A572Gr50 | ASTM A572 Gr. 50 (the default) | 29000 ksi | Fy 50, Fu 65 ksi | 490 lb/ft³ |
| A992 | ASTM A992 | 29000 ksi | Fy 50, Fu 65 ksi | 490 lb/ft³ |
| A500GrB | ASTM A500 Gr. B, rectangular HSS | 29000 ksi | Fy 46, Fu 58 ksi | 490 lb/ft³ |
| A653SSGr33 | ASTM A653 SS Gr. 33 sheet (cold-formed) | 29500 ksi | Fy 33, Fu 45 ksi | 490 lb/ft³ |
| A653SSGr50 | ASTM A653 SS Gr. 50 Class 1 sheet | 29500 ksi | Fy 50, Fu 65 ksi | 490 lb/ft³ |
| 4000Psi | Normal-weight concrete | 57000 √f'c = 3605 ksi | f'c 4000 psi | 150 lb/ft³ |
| 3000Psi | Normal-weight concrete | 57000 √f'c = 3122 ksi | f'c 3000 psi | 150 lb/ft³ |
| CMU-Grouted1500 | Fully grouted concrete block masonry | 900 f'm = 1350 ksi | f'm 1500 psi | 140 lb/ft³ |

Poisson's ratio is 0.3 for steel, 0.2 for concrete and 0.25 for masonry
(TMS 402: Ev = 0.4 Em). The values are converted to the project's units when
they are added.

They are *ElasticIsotropic* materials: E, ν and the mass density are what an
elastic section and a shell need, and the strengths (Fy, Fu, f'c) are kept as
design data that OpenSees never sees. For a nonlinear fibre section, take a
Steel02 or Concrete01 from Define → Material Library.

A572Gr50 is the application's default material: a section or a drawn member
with nothing else chosen gets it. A new 3D project also gets the slab section
**Slab 20cm** (an elastic plate of 4000Psi, 20 cm thick), so Draw Shell works at
once.
