---
title: File → Export → Calculation Memory
group: File
summary: Calculation memory of the steel checks with formulas and numbers.
see_also: file.export_report, design.steel_check, design.connections, design.gussets, design.column_splices, design.chapter_j
order: 530
---

Exports the steel design as a document:

- **Cover**: project, author, company, date, program version and revisions
  (File → Project Information).
- **Index** of every member with its shape, ratio and status.
- **One sheet per member**: governing check, load set and station; the
  geometric properties of its shape; every limit state with demand, capacity
  and ratio; and the calculation steps (formula, substitution, value).
- **Seismic joints and connections**: the SMF joint table (E3.4a, panel zone
  J10.6 and continuity plates E3.6f), the AISC 358-22 RBS connections and
  their 5.5 web connection checks, the SCBF protected zones, gussets and
  F2.6c brace connections, the F2.6b beam-to-column joints, the F2.6d column
  splices, the AISC 360 Chapter J checks and the F2.3 capacity design, each
  with its demand, capacity, ratio and status; the Chapter J checks also carry
  their calculation steps.
- **Language**: English or Spanish, chosen in the dialog.
- **Formats**: HTML, Markdown, LaTeX, OpenDocument text (ODT) and PDF.
- **Members**: all designed, the current selection, or only the NG members.

The memory reproduces the checks run in this session; run the load sets first.
