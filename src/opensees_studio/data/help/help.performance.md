---
title: Help → Performance monitor
group: Help
summary: Measure imports, analysis, rendering and UI stalls on large models.
see_also: help.contents
order: 2010
---

The performance monitor is **opt-in**: normal work pays essentially nothing.
Enable it in any of these ways:

- launch with ``opensees_studio --profile`` (frozen builds: ``OpenSeesStudio.exe --profile``);
- launch with ``--perf-json report.json`` to also write a report on exit;
- set ``OPENSEES_STUDIO_PERF=1`` in the environment;
- open this dialog and press **Enable profiling**.

The table lists every instrumented boundary with its last, total, count, p95 and
maximum milliseconds. Names are grouped by prefix: ``s2k.*`` for the SAP2000
importer, ``persistence.*`` for project I/O, ``analysis.*`` for the solver,
``render.*`` for scene construction, and ``command.*`` for undoable edits.

**Profile next action** runs the next instrumented operation under ``cProfile``
and shows the 30 functions with the largest cumulative time. **Save JSON** and
**Copy JSON** produce a report with the version, platform, model counts, memory
and timings, suitable for attaching to an issue.

For repeatable measurements of large synthetic models, run
``python tools/perf_bench.py --size large --profile``. See
``docs/performance-profiling.md`` for the full workflow.
