---
title: Tools → Measure Distance (F7)
group: Edit and tools
summary: Click two points — joints, grid intersections or member snaps — to copy the distance.
see_also: tools.select, tools.draw_node
order: 830
---

Pick the first point, then the second. A point is an existing joint, a grid
intersection, or a member snap (midpoint, perpendicular or on member) when
that OSNAP is on. The straight-line distance is taken from all three
coordinates (the X-Z plane in a 2D model), formatted without trailing zeros,
copied to the **clipboard** and shown in the status bar with the project's
length unit and its **dX, dY, dZ** components. The two joints stay selected,
and the tool stays armed for another measurement.

Joints and grid points are highlighted in yellow when the pointer is over
them: the joint OSNAP wins over the grid, and the grid wins over empty space.
The first pick keeps a red circle, and as the pointer moves a thin dashed line
with its length follows the snap under it, so the measurement can be read
before the second click. Both graphics are removed when the measurement
completes, is cancelled or the tool is left.

- Clicking an element or empty space away from a snap does not measure
  anything; the status bar says to click a joint or a grid intersection.
- With no grid defined, only joints and member snaps can be measured; define
  a grid in Define → Coordinate System/Grids.
- The measurement changes nothing in the model, so it is **not** an undo step.
- Esc cancels the first pick; Select (or another tool) leaves the measurement
  mode.
