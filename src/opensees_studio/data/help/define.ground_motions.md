---
title: Define → Ground Motions
group: Define
summary: The record library: files, formats, units and metadata.
see_also: mechanics.spectra, mechanics.ground_motions, define.linear_ts
order: 990
---

Records are stored in the project **by reference** (a path and a content hash),
so a project stays small and a changed file is detected. Everything a case needs
about a record is computed once, here.

# Values
- **File and format** — PEER `.AT2`, two-column (time, acceleration) or
  single-column (with the time step supplied).
- **Acceleration unit** — `g` or the project's acceleration unit; the factor is
  stored with the record.
- **Metadata** — PGA, PGV, PGD, Arias intensity and the 5-95 % significant
  duration, computed from the samples: useful to choose and to document records.
- **Scaling** — by PGA or by Sa(T1) of a chosen period; a response-spectrum case
  can also compute the factors that match a target spectrum over a period range.
