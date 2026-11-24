---
title: Edit → Move
group: Edit and tools
summary: Translate the selected nodes or members in place by (dx, dy, dz).
see_also: edit.replicate, edit.mirror
order: 700
---

Moves the selection, and with it every element that uses those nodes: this is
the transform that changes the model rather than copying it.

Selecting a member is enough: its joints move with it, so you do not have to
pick the nodes first. A joint shared with a member you did not select moves as
well, and that member follows its joint.

# Values
- **dX, dY, dZ** — the displacement, in project units. Positive X is to the
  right, positive Z is up.
- **Measure…** — picks two joints in the viewport (F7 works too once the
  viewport has the focus) and fills dX, dY and dZ with the vector between
  them; the window shows the distance it measured. The window is modeless, so
  the viewport stays usable and the measurement can be repeated.

Moving a node changes the geometry of every member that touches it, and no
property follows it — the section, the material and the loads stay where they
were. To repeat a part of the model somewhere else, use Replicate.
