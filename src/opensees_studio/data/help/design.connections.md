---
title: Design → Steel Connections → Connections (AISC 358-22)
group: Design
summary: AISC 358-22 reduced beam section (RBS) connections.
see_also: design.steel_check, file.calc_memory
order: 370
---

Lists, adds, edits and removes RBS connections of the project.

- Pick the **beam** and **column** frame elements, then `a` (start of the cut),
  `b` (cut length) and `c` (cut depth). The fields start at the midpoints of
  the Section 5.7 limits for the chosen beam.
- The cut is checked when added: `0.5 bf <= a <= 0.75 bf`,
  `0.65 d <= b <= 0.85 d`, `0.1 bf <= c <= 0.25 bf`. An invalid cut is refused
  with the reason.
- OK stores the list as one undoable step; the report and the calculation
  memory show each connection with its `Z_RBS`, `Sh`, `Mpr` and protected zone.

The connection check reports the AISC 358 5.7 steps: the face moment
`Mf <= phi_d Mpe` (step 8), the beam shear `Vh <= phi Vn` (step 9) and the
clear span-to-depth prequalification (step 1, 7 for SMF and 5 for IMF). The
optional **web connection (5.5)** stores the CJP or bolted single-plate type,
the plate thickness and height, the bolt count, diameter and `Fnv`, and the
fillet weld leg and `Fexx`. For a bolted plate it checks the 3/8 in. minimum
thickness, plate shear yielding and rupture, bolt shear, the `5/8 tp` minimum
leg and the fillet weld; for a CJP it checks the backing-plate thickness and
notes that the demand-critical CJP capacity is not computed. The net area
assumes one vertical bolt line; bolt bearing, block shear and slip resistance
are reported as not checked. Continuity plates and panel zones are in the SMF
joint table.
