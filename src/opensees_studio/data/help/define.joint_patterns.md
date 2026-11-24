---
title: Define → Joint Patterns
group: Define
summary: Named values per node that surface loads vary by (hydrostatic, earth pressure).
see_also: assign.joint_pattern, assign.surface_load
order: 1400
---

A joint pattern is a number at each node, as in SAP2000. On its own it does
nothing: a surface load *by joint pattern* applies, at each corner of a shell,
its multiplier times the pattern's value there.

# The dialog
- **Add / Delete** — a pattern a surface load uses cannot be deleted until the
  load is removed. Double-click a name to rename it.
- **The table** lists the nodes that have a value; edit a value in place. Every
  node not listed counts as zero.

Values are assigned with Assign → Joint → Joint Pattern Values. They follow the
model: meshing a shell gives its new nodes the values interpolated from its
corners, Edit → Replicate copies them with the joints, merging duplicates keeps
the remaining node's value, and deleting a joint deletes its values.

Joint patterns travel with File → Import/Export → SAP2000 Text (`JOINT PATTERN
DEFINITIONS`, `JOINT PATTERN ASSIGNMENTS`), and a pressure by pattern is written
to IFC as a discrete planar action with its corner values.
