---
title: File → Run Batch
group: File
summary: Solve many project files unattended and keep each one's results.
see_also: file.open, analyze.run, analyze.results_database
order: 240
---

Runs the analysis cases of many `.osmodel` files one after another (or a few at
a time) without opening them. Nothing in the project open in the window
changes; each file is read from disk as it was last saved.

- **Add Files… / Add Folder…** build the list. A folder adds every `.osmodel`
  directly inside it (not its subfolders); pre-run snapshots are left out.
- **Cases**: *All cases* runs every case of each project, in its own order.
  *Cases named* takes names or ids separated by commas (`Dead, Modal, 3`),
  ignoring upper and lower case; a project with none of them is *skipped*.
- **Parallel jobs**: how many projects solve at the same time. Each one is its
  own analysis process, so use at most one per processor core, fewer for big
  transient models (each holds its own model in memory).
- **Run custom Python blocks**: off by default, so a project with enabled
  Define → Custom OpenSees Commands blocks is *skipped*, since their code runs
  on this computer. Tick it only for files you trust.
- The table shows each file's status, the case running with its step, the time
  taken and, for a failure, the reason. **Cancel Batch** stops the running
  processes and drops the ones not started; the window cannot be closed while
  the batch runs.

The engine is the one chosen in Options → Solver, exactly as for Analyze → Run:
a case it does not run fails that file with the reason.

# Where the results go

Beside each project, `model.osmodel` keeps:

- `model_batch_results/`: the lossless result store (`case_<id>.results.h5`,
  `manifest.json`), `batch.json` (which model the results belong to) and
  `analysis.stderr.log` (the solver's own output);
- `model_results.sqlite`: the results database, one new run per case.

When the batch ends, `batch_summary.json` and `batch_summary.csv` (file,
status, time, cases, exit code, message) are written in the folder of the first
file.

Opening a solved project later (File → Open) offers to load the stored results
while the model is still the one they were computed on; after an edit to the
model they are not offered, since they would describe another model.

# From a terminal

`python -m opensees_studio.batch models/*.osmodel --cases all --jobs 4` does the
same without the window (`--engine` picks another engine, `--summary` another
summary name). A packaged build runs it as `OpenSeesStudio --batch …`.
