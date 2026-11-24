---
title: Edit → Check Model for Duplicates
group: Edit and tools
summary: Find — and merge — nodes that sit on top of each other and members defined twice.
see_also: edit.replicate, file.import_dxf
order: 760
---

A model that has been copied or imported twice accumulates coincident nodes and
repeated members, and neither is loud: the analysis runs, the deformed shape
looks right (a copy doubles the stiffness **and** the load), and only the
reactions and the member forces are wrong.

# What it reports
- **Coincident nodes** — groups at the same point, with the tolerance you set
  (default: one part per million of the model's size, so metres and millimetres
  need no different numbers).
- **Duplicate elements** — the same type, the same nodes and the same
  properties. These are the ones that double a stiffness.
- **Parallel elements** — the same nodes with different properties. That can be
  deliberate, so it is reported and not touched.

# What it refuses to touch
The two nodes of a **zero-length element or a bearing**, and nodes tied by an
**equalDOF** constraint, are deliberate coincidences: merging them would delete
every isolator and every modelled hinge. They are listed with the reason.

# What the repair does
- Merges into the lowest node id, **combining restraints** (a support is never
  released by accident) and keeping equal masses once (a copy must not weigh
  twice) while adding masses that differ.
- Repoints element nodes, equalDOF constraints, nodal loads and imposed-support
  node lists to the node that stays.
- Removes duplicate members and the ones left with no length, and drops loads
  that were copies instead of doubling them.
- Recomputes element duplicates **after** merging the nodes, because merging two
  nodes can turn two members into the same member.

One undo step takes the whole repair back.
