---
title: Design → Steel Connections → Gussets (AISC 341-22)
group: Design
summary: SCBF gusset plates: Whitmore width, yielding and plate buckling.
see_also: design.steel_check, design.connections
order: 380
---

Lists, adds, edits and removes the gusset plates of an SCBF.

- Pick the **brace** frame element, then the plate thickness `t`, the plate
  width `b`, the Whitmore length `Lw` along the brace and the free length `Lc`
  for plate buckling. The fields start from the brace shape and can be edited.
- The plate is checked against the expected brace force `Ry Fy Ag`:
  **Whitmore width** `bw = 2 Lw tan(30) + t_brace`, **yielding**
  `Pn = Fy b t` and **buckling** with `r = t/sqrt(12)` and `K = 0.65`.
- The **brace connection** required strengths of F2.6c are reported for the
  same brace: tension `Ry Fy Ag / alpha_s`, compression equal to the expected
  brace compression of F2.3 divided by `alpha_s`, and flexure
  `1.1 Ry Mp / alpha_s` about the critical buckling axis. They are demands
  for the connection design, not a pass/fail check of the bolts or welds.
- Tick **Check gusset-to-flange weld** to check F2.6c.4: the weld must carry
  `0.6 Ry Fy tp / alpha_s` per unit length, compared with the fillet-weld
  shear strength of AISC 360 J2.4. Give the leg, whether it is on both sides
  and the electrode strength `Fexx`; the dialog suggests `0.74 t` for A572
  Gr. 50 plate and E70 electrodes. The plate and the weld use the design `Fy`
  of the check; a separate gusset-plate material is not modelled yet.
- OK stores the list as one undoable step; the report and the calculation
  memory show each plate with its demand, ratio and status, the F2.6c
  required strengths and the weld check.

The gusset interface, the bolts and the full AISC 341 connection design
procedure are not part of this dialog yet.
