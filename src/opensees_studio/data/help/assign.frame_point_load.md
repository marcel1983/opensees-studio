---
title: Assign → Frame → Point Load
group: Assign — frame
summary: A concentrated force inside a member: global X/Y/Z by default, or local axes.
see_also: assign.distributed_load, define.plain_pattern
order: 1290
---

# Values
- **Default: global.** Enter **Fx, Fy, Fz**; each selected member projects the
  force onto its own local axes.
- **Use local axes** — tick the box to enter **Px, Py, Pz** directly in the
  element's local x (axial), y and z axes.
- **Distance from end i** — where the load acts, either **relative** (a
  fraction of the length, 0 at node i, 1 at node j) or **absolute** (a length).
  An absolute distance becomes a different fraction on members of different
  length; a member shorter than the distance is skipped and named in the log.
- Only frame (beam-column) elements take it: trusses, zero-length elements,
  bearings and faces in the selection are skipped.
- **Pattern** and **Existing loads** — as for the distributed load: Replace and
  Delete act on the members' point loads in that pattern only.

# Mechanics
It is emitted as `eleLoad -beamPoint`. An elastic beam-column takes the exact
fixed-end forces; a force- or displacement-based element resolves the load
through its integration points, so the end forces are approximate unless the
member is split at the load (Edit → Mesh keeps the load on the piece it falls
on). A force-based element only takes an element load into its forces after
a solve, so the runner follows each static step that loads one with a second
solve at the same load; any algorithm and test then gives the converged answer,
except a test relative to the first iteration (RelativeNormDispIncr), which is
refused for more than one step.
