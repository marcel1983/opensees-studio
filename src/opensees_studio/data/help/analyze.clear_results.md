---
title: Analyze → Delete All Results
group: Analyze
summary: Forget every stored result: the session's and the project's database.
see_also: analyze.results_database, analyze.run
order: 1550
---

Removes the results of this session from memory (what Display can show and what
the reports use) and deletes the project's `<project>_results.sqlite` file. The
model, its analysis cases and its load combinations are untouched, so the next
run starts from a clean slate.

It asks first: there is no undo. A different project's database is never
touched, because the file lives beside its own model.

To replace one case's numbers, just run it again — a case keeps one run, which
is overwritten (see *Analysis results database*).
