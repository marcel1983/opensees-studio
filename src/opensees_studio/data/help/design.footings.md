---
title: Design → Footings (ACI 318-19, Soil)
group: Design
summary: An isolated spread footing under every support: the soil and the concrete.
see_also: design.footing_pressures, design.base_plates, design.concrete_check
order: 430
---

One row per **support restrained in Uz**. Tick the first column to give the
support a footing (every support starts ticked the first time). AISC stops at
the base plate (Design → Steel Connections → Base Plates); the footing under it
is reinforced concrete and is checked after **ACI 318-19**.

# Geometry and materials
- **L** along global X, **B** along global Y, thickness **h**. The support sits
  at the given **offset** from the footing centre (a property-line footing).
- **Pedestal / column / plate** is what stands on the footing. With a
  **pedestal height** above 0 it is the pedestal: its weight and the lever arm
  of the horizontal force are added, and a steel base plate on it gets **A2**
  from the pedestal top. Under a steel column with no pedestal it starts as the
  base plate, and the moment is taken halfway between the column face and the
  plate edge (13.2.7.1).
- **Fill above the footing** adds soil weight. **X bars** are the bottom layer;
  **Y bars** sit on them.
- **qa** is the gross allowable soil pressure of the soil report: the footing,
  the pedestal and the fill weigh on it.

# Checks
Soil, with every alternative of the **service** load sets: largest pressure
against qa (compression only, one- or two-way eccentricity, partial contact
solved), at least 50 % of the footing in contact, overturning
FS = N (L/2) / M, sliding FS = μ N / H, and no net uplift.

Concrete, with the **strength** load sets and the column's factored reaction
only: d ≥ 150 mm (13.3.1.2); one-way shear at d from the face with the size
effect λs and ρw (22.5.5.1); punching at d/2 with αs 40, 30 or 20 by the sides
that fit (22.6.5.2) plus γv of the column moment on an interior perimeter
(8.4.4.2); flexure at the critical section, each direction and side;
0.0018 Ag minimum steel, spacing ≤ min(3h, 450 mm) and the short-direction
band of a rectangular footing (13.3.3); bearing of the footprint (22.8); and
the development length of straight bars (25.4.2.3).

A strength load that lifts the footing reads **Requires verification**: top
steel is not designed. Combined footings, strip footings, mats and piles are
not covered.

# Combined footings
Select two or more supports and press **Combine the selected supports**: one
rectangular footing under all of them, centred on them, its long side along the
line through the two farthest apart, 600 mm past the outer footprints and 1.5 m
wide. The **Combined** tab edits its centre, plan, slab, bottom bars both ways and
**top bars** along the long axis, and each column's footprint and pedestal.
Checks: the soil under the resultant of every column (same as an isolated
footing); the long direction as a beam — the pressure summed across the width,
each column's factored force and moment, sagging moment for the bottom bars and
hogging moment between the columns for the top bars (NG with no top bars), and
one-way shear at d from every column face; a transverse beam under each column,
c + d wide, as a cantilever from the face; punching and bearing of each column;
development of the long bottom bars past the outer faces with ld reduced by
As,req / As,prov (25.4.10.1). **Size the combined footing** keeps the length and
finds the width, thickness and bars. A support on a combined footing gets no
isolated one.

# Load sets
The service list starts with every combination whose name says ASD, service or
SLS; the strength list with the steel check's load sets without those. With no
service combination the soil is checked with the strength loads (conservative)
and a note says so. Changing the ticks saves them with the project.

# Editing
Select rows, change the form and press **Apply to the selected supports**.
**Size the selected footings** keeps the footprint and the materials and finds
the smallest plan (50 mm steps, same proportion), thickness and bars (12 to
32 mm, spacing in 25 mm steps) that pass everything. **OK** keeps the footings in
the project (`design.footings`), one undoable step. Editing them never asks to
unlock the model: they do not change the analysis.
