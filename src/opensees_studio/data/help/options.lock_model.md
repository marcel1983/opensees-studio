---
title: Options → Lock Model
group: Options
summary: A locked model asks before it is changed, so results never go stale unnoticed.
see_also: analyze.clear_results, analyze.cases
order: 1920
---

The model **locks itself when an analysis has results** (a run, or stored
results loaded with the file). The padlock at the right of the status bar reads
*Locked*; click it, or use this command, to lock or unlock by hand.

While the model is locked:

- A change to the model the results depend on (a joint, a member, a section, a
  load, a restraint, an analysis case; also an Undo or a Redo of one) asks
  **Unlock Model**. *Yes* unlocks, discards the results held in this session and
  keeps the change; *No* takes the change back and leaves the results on screen.
- What no result depends on stays free: load combinations, design settings and
  overrides, RBS connections, gusset plates, column splices and Chapter J
  checks, display units, view and display options (also when Save writes the
  viewport into the file).
- Running an analysis again is always allowed.

Unlocking by hand asks the same question when there are results. The results
database beside the project (`<project>_results.sqlite`) is never touched by the
lock: Analyze → Delete All Results is the command that empties it.

You can also lock a model that has no results, to protect it from an accidental
edit; unlocking it then loses nothing.
