---
title: Design → Steel Connections → Column Splices (AISC 341-22)
group: Design
summary: SCBF column splices: required moment and shear of F2.6d.
see_also: design.steel_check, design.gussets
order: 390
---

Lists, adds, edits and removes the column splices of an SCBF.

- Pick the **splice node**, the **top** and **bottom** column elements that
  meet there, and the clear height `Hc` between beam connections. The dialog
  lists only column elements connected to the node and suggests `Hc` from the
  first column length.
- The splice must develop at least 50% of the lesser plastic moment of the
  two segments, divided by `alpha_s`: `0.5 min(Mp_top, Mp_bottom) / alpha_s`.
  Its required shear is `(Mp_top + Mp_bottom) / (alpha_s Hc)`, with
  `Mp = Fy Z` of each segment.
- OK stores the list as one undoable step; the report and the calculation
  memory show each splice with its node, members, `Hc`, required moment and
  shear.

The splice detail (CJP groove weld or bolted splice) is not modelled; the
dialog reports the required strengths for its design.
