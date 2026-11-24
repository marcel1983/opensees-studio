---
title: Analyze → Run
group: Analyze
summary: Run the selected cases in a separate process and collect the results.
see_also: analyze.cases, analyze.check_model, display.deformed, analyze.results_database
order: 1520
---

The solve happens in a **child process** (`python -m opensees_studio.run`, or
the bundle re-entering itself), not in the interface:

- the GUI stays responsive, and a case can be cancelled;
- a solver crash cannot take the model with it — the child's exit code and its
  last error are reported;
- the child speaks one JSON object per line, so progress and log lines stream
  back while it runs.

Before starting, a **pre-run snapshot** of the project is written next to the
file (or into the app data directory for a never-saved project): that is the
crash-recovery path, and it is removed on a normal save or close.

Results go to an HDF5 file plus a manifest, losslessly, and are what the Display
commands read. An early stop (a transient that stops converging) is a *result*:
the log records the step reached and the results keep what was computed.

# The Run dialog
Pick a case or a load combination and press **Run**; the log shows what the
solver does. The dialog does not block the window: the model can be orbited,
selected and inspected while a case runs, and pressing **F5** again brings the
same dialog to the front. When the case has finished, the log ends with the case
and its kind (*Done: Tip-Load · Static*) and **Show Results** closes the dialog
onto the results, which the window already shows. Closing it while a case runs
does not stop the run: the status bar keeps its progress and its **Cancel**.
