---
title: Analysis results database
group: Analyze
summary: Every run is appended to a SQLite file with all node and element results, for later queries.
see_also: analyze.run, analyze.run_all, display.select_results
order: 1560
---

Each finished case is written to **`<project>_results.sqlite`**, next to the
project file (a never-saved project writes to the app data directory as
`untitled_results.sqlite`). SQLite is used because a static case on a 500-joint
model writes thousands of rows and a time history writes far more: one file,
indexed, readable by a notebook, a spreadsheet or the `sqlite3` CLI, and safe to
interrupt.

There is **one run per case**: re-running a case replaces its previous rows, so
the file always reflects the latest run of each case. Different cases coexist;
**Analyze → Delete All Results** removes both the session's results and the
file.

| Table | One row per |
|---|---|
| `runs` | run: case id and name, kind, timestamp, step count, `dt`, HDF5 path |
| `node_disp` / `node_reaction` | node × step: `ux, uy, uz, rx, ry, rz` |
| `element_forces` | element × step: `c1 … c12` (local forces) |
| `element_stresses` | element × step: shell resultants `n11 … v23` |
| `storey_shear`, `section_cut_forces` | storey / cut × step |
| `modal`, `mode_shapes` | mode, and mode × node |

Load combinations are stored as two runs (`combination:max`, `combination:min`);
a response spectrum is one pseudo-step of peak values; a transient run records
the HDF5 path and indexes its node displacement history (velocity, acceleration
and element state stay in the lossless HDF5 file).

Query it without the application:

```sql
SELECT r.case_name, d.node_id, d.step, d.ux
FROM node_disp d JOIN runs r USING (run_id)
WHERE r.run_id = 3 AND d.node_id = 12 ORDER BY d.step;
```

If the file cannot be written, the run still succeeds and the console says so:
results are never lost because the database failed.
