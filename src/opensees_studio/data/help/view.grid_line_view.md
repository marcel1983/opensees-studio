---
title: View → Grid Line View
group: View
summary: Only the objects lying on one grid line, looked at face on.
see_also: view.grids, define.grid
order: 870
---

Pick a grid line by its label — `Global: X A (6)`, `Global: Z Z2 (3)`, or a ring
or radial line of a cylindrical grid — and the view keeps only the joints within
the **window** either side of it and the elements all of whose joints are kept.
Everything else is hidden from the view (not from the model: the analysis and
the tables still see all of it).

# Values
- **Grid line** — every line of every coordinate system, by system, axis, id and
  ordinate.
- **Window either side** — how far from the line a joint may be, in the model's
  length unit. Default **50 mm** (0.05 in a model in m, 50 in mm, converted for
  ft and in). The dialog remembers the last value and counts what will be shown.

# What the view does
- An X line is looked at from the Right (YZ), a Y line from the Front (XZ) and a
  Z level from the Top (XY), with that line as the working plane, so you can
  draw on it straight away. A ring or radial line keeps the isometric view.
- The filter follows the model while you work: a member drawn on the line
  appears, one moved off it disappears. The status bar says what is shown.
- **View → Show All Objects** (or the right-click menu) brings everything back.
  Opening another project does too.
