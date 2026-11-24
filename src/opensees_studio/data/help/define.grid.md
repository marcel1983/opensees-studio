---
title: Define → Coordinate System/Grids
group: Define
summary: The reference lines, and the coordinate systems they live in.
see_also: tools.draw_node, file.new_2d_frame, define.grid_wizard, view.grids
order: 840
---

Grids are drawing aids: they snap the draw tools and give you levels to work at.
They do not create nodes by themselves (unless you ask the dialog to).

# Values
- **Coordinate system** — a name, an origin and a rotation. `Global` is at the
  world origin with identity rotation and cannot be deleted.
- **System type** — *Cartesian* (X, Y and Z lines) or *Cylindrical* (radial):
  the three tabs become **R** (rings: radii about the system's local Z axis),
  **T** (radial lines: angles in degrees from local +X towards +Y) and **Z**
  (levels). Rings close into full circles when the radial lines go all the way
  round (e.g. 8 lines at 45°), otherwise they are arcs between the first and
  last angle. The draw tools snap to the ring × radial-line crossings.
- **Grid lines per axis** — each line has an id (its label), an ordinate,
  Primary/Secondary, visibility, the end its label is shown at (**Start**,
  **End** or **Both**) and a colour. The ordinates are what the tools snap to; a
  line whose Visibility is off is neither drawn nor snapped to.
- **Add Row** continues the grid: the new line goes one *last spacing* beyond
  the last line (lines at 0, 6, 12 → 18) and takes the next id (X3 → X4, C → D,
  Z → AA). Edit it if that is not where you want it.
- Lines are per axis: X lines are planes of constant X, and so on.
- **Hide All Grid Lines** — the system is neither drawn nor snapped to (the same
  switch as View → Show Grids and the right-click menu).

# Grid labels
- **Show grid labels** — the bubbles at the ends of the lines.
- **Content** — `ID` (A, 1, X3), `ID + coordinate` (`A (6)`) or `Coordinate`.
  A radial line shows its angle with a degree sign.
- **Size** (points) and **Colour** of the label text.
- **Position** + *Apply to all lines* — put every label at the Start, the End or
  Both ends at once (each row can still be changed on its own).
- Z levels are labelled once, beside the first corner of the plan.

# Working plane
- View → Top (XY), Front (XZ) or Right (YZ) chooses which pair of axes is the
  drawing plane, and the Level combo chooses which level of the third axis is
  active. A cylindrical grid offers its Z levels in plan (Top) only.
