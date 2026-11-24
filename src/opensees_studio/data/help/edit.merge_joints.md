---
title: Edit → Merge Joints
group: Edit and tools
summary: Joints closer than a tolerance become one.
see_also: edit.check_duplicates, edit.divide_frames
order: 660
---

For a drawing whose joints are a few millimetres apart where they should be one
(an imported DXF, two frames drawn separately): they look connected and are
not, and the model solves as two pieces.

# Values
- **Tolerance** — joints closer than this merge. It starts at a thousandth of
  the model's size; Check Model for Duplicates uses a millionth, for joints that
  are meant to be exactly coincident.
- **Apply to** — the selected joints only (only they merge, among themselves),
  or the entire model.
- The summary says how many groups merge and how many joints go before you
  accept, and which groups are left alone.

# What happens
- The lowest id of a group stays, at its own position. Elements, loads,
  constraints and groups that used the others move to it; a DOF restrained on
  any of them stays restrained, and different masses are added.
- Members that become repeated (two beams on the same two joints) are removed,
  and their loads move to the one that stays.
- A group joined by a zero-length element, an equalDOF, a rigid link or the
  retained joint of a diaphragm is meant to be coincident and is left alone.
- One undo step.
