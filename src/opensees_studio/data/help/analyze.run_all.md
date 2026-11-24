---
title: Analyze → Run All Cases
group: Analyze
summary: Run every analysis case of the model, one after another, in one child process.
see_also: analyze.run, analyze.run_selected, analyze.results_database
order: 1530
---

The batch door: every case defined in Analyze → Cases runs in a single child
process, in the order they are listed, and each one lands in the results
database as its own run. Log lines stream to the Console as they do for a single
run.

# While it runs
The right of the status bar shows which case is running and how many the run
has (*Running 'Dead' (2 of 5)*), a progress bar for the steps of that case, and
**Cancel**, which stops the child process. The project is not touched, and the
results of a cancelled run are discarded, those of the cases that had finished
included. The window stays usable meanwhile, so you can look at the model.

Use it before a report, or after changing something that invalidates every case
(a section, a material, the mass source). To run only some of them, use
**Run Selected Cases**.
