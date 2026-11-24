---
title: Define → Grid Wizard
group: Define
summary: A whole Cartesian or radial grid from a few numbers.
see_also: define.grid, tools.draw_frame
order: 850
---

For a regular grid you do not want to type line by line. One undo step.

# Values
- **Put it in** — a new coordinate system, or *Replace the grid of* an existing
  one (its origin and rotation are kept). A new project's empty Global grid is
  offered first.
- **New system name** and **Origin** — only for a new system.
- **Grid type** — *Cartesian* (X lines, Y lines, Z levels) or *Cylindrical*
  (rings by radius, radial lines by angle in degrees, Z levels). A 2D model is
  Cartesian in the X-Z plane, so its Y row is off.
- Per row: **Number** of lines (0 = none on that axis), **Spacing**, where the
  **First** line is, and the **Names**: `A, B, C …`, `1, 2, 3 …` or `X1, X2 …`.
- **Labels** — on/off, content (ID, ID + coordinate, coordinate) and position
  (Start, End, Both); size and colour are in the grid dialog.

The preview lists the lines before anything is created. Rings need radii of 0 or
more, and the radial lines cannot go past a full turn: 8 lines at 45° close the
circle, 9 would put two on top of each other.

Afterwards, Define → Coordinate System/Grids edits any line one by one.
