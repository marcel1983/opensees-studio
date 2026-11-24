---
title: Define → Add Path TimeSeries
group: Define
summary: A load or displacement read from a file or a record.
see_also: define.linear_ts, define.ground_motions, mechanics.transient
order: 1100
---

A path time series takes its values from a file (a ground-motion record, or any
two-column time series) and can be scaled by a factor.

- **File and column** — which file, and which column holds the values.
- **dt** — the file's time step, used when the file has no time column.
- **Factor** — multiplies every value; this is where a record's `g` becomes the
  project's acceleration unit, or where a scale factor is applied.
- Ground-motion records from the catalog are stored as path series with the file
  kept outside the project.
