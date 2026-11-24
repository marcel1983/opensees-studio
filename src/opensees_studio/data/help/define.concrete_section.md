---
title: Define → Concrete Section Wizard
group: Define
summary: A reinforced concrete section, its concrete and steel materials, from a few inputs.
see_also: define.section_library, define.section_designer, define.material_library
order: 1010
---

Builds a reinforced concrete frame section the way it is drawn on a plan, and
adds the materials it needs, in one undo step. The drawing on the right shows the
concrete, the core inside the bar centrelines (dashed) and the bars at their true
size, with the centroid.

# Shape
- **Rectangle** (column or beam), **Circle** (column), **T-beam** (flange on
  top, centred on the web) and **L-beam** (edge beam, flange to +z).
- Depth h runs along local **y**, width b along local **z**: assign the section
  so local y is the direction the member bends in (Assign → Frame → Local Axes).

# Reinforcement
- Bar sizes **metric** (φ6 to φ40 mm) or **US** (#3 to #18).
- Top and bottom bars (at least two each) and intermediate bars on each side
  face; a circle takes its bars evenly around.
- **Clear cover** is to the outside of the ties: the bars sit at cover + tie +
  half a bar from the face.
- Tie size and spacing give the transverse ratio ρs (two legs each way for
  hoops, 4 Asp / (ds s) for a spiral), used for the confinement.

# Materials it adds
- **Cover concrete**: `Concrete02`, f'c at a strain 2 f'c / Ec (so its initial
  slope is Ec = 4700 sqrt(f'c) MPa, ACI 318-19), spalling to zero at 0.005,
  tension 0.33 sqrt(f'c) MPa.
- **Core concrete**: with **Confined core (Mander)** ticked, f'cc, εcc and εcu of
  Mander, Priestley and Park (1988) with ke = 0.75 for hoops and 0.95 for a
  spiral, εcu = 0.004 + 1.4 ρs fyh εsu / f'cc; otherwise the cover concrete.
- **Bars**: `Steel02` with fy, Es and 1 % hardening.
- **Concrete law** `ConcreteCM` (Chang and Mander 1994) instead of `Concrete02`
  for cyclic analyses: the cover peaks at εc = f'c^(1/4) / 1150 (MPa) with
  r = f'c / 5.2 - 1.9, the core at Mander's f'cc and εcc with
  r = Ec / (Ec - f'cc / εcc), which makes its envelope Mander's curve; tension
  0.33 sqrt(f'c) MPa at 1.2 ft / Ec with r = 1.2.

# Sections it adds
- **Fiber section** (default): core, cover strips, flange overhangs and bars as
  layers, for force- or displacement-based members. Its GJ is the gross elastic
  one (G = Ec / 2.4).
- **Elastic section with cracked inertia**: the gross area, Ec and I times the
  factor of ACI 318-19 Table 6.6.3.1.1 — **0.70 for a column, 0.35 for a beam** —
  for a linear model; change the factor if your code asks for another.

A column's longitudinal ratio outside ACI's 1 % to 8 % is noted. Edit the
materials afterwards in Define → Material Library, and the fibre layout in
Define → Section Library (double-click the section).
