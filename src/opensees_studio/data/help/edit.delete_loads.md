---
title: Edit → Delete Loads
group: Edit and tools
summary: Remove loads by type, by load pattern, from the selection or the whole model.
see_also: assign.load, assign.distributed_load, define.plain_pattern
order: 1940
---

# Values
- **Delete from** — the selection, or the entire model. A joint load goes with
  its joint, a frame or shell load with its element, a floor load when all four
  of its corner joints are selected.
- **Load types** — tick the ones to remove; the number next to each is how many
  the current choice would remove: joint forces and moments, imposed joint
  displacements, uniform / trapezoidal / point frame loads, frame temperature
  loads, shell pressures, floor loads, and the self weight (the pattern's
  self-weight multiplier is set to 0; only on the entire model, since it belongs
  to no joint or element).
- **Load patterns** — the patterns to remove them from (all, to start with).

Everything removed comes back with one Ctrl+Z. The log says what was removed.
