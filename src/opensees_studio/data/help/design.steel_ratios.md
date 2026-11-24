---
title: Design → Display Steel Ratios on Model
group: Design
summary: Paint every frame member by its governing AISC 360-16 or AISI S100-16 ratio.
see_also: design.steel_check, file.export_report
order: 500
---

Runs the steel frame check with the settings saved in the project (or the
defaults: LRFD, 50 ksi, every combination) over the results of this session, and
draws each member in the colour of its governing demand/capacity ratio, with the
ratio written at mid-length to three decimals, as the check's table, the report
and the calculation memory print it:

- blue up to 0.5, teal up to 0.7, green up to 0.9 and orange up to the ratio limit
  (the steps are those fractions of the limit, so a limit of 0.95 keeps the reading);
- **red above the limit**;
- grey for a member the check does not cover (no AISC shape, a section name
  that is not one, or a cold-formed profile outside the AISI check).

The panel on the right shows the legend, the summary and the notes (load sets
skipped because a case has no result yet). **Select failing members** selects
the red ones; **Back to model** (or Display → Back to Model) removes the colours.

Nothing is stored: change the settings in Design → Steel Frame Check, then display
the ratios again.
