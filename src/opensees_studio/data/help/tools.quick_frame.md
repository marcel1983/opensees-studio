---
title: Tools → Quick Draw Frame
group: Edit and tools
summary: Click a grid line between two crossings to draw the member there.
see_also: tools.draw_frame, tools.draw_shell, define.grid
order: 810
---

The fast way to lay out a regular frame: one click per member, on the grid
line itself rather than on its two ends. The click is read where it meets the
**working plane** (the level chosen in the View toolbar, or the plan at Z = 0),
and the member goes between the two grid crossings on either side of it along
the nearest line, with joints created where there are none.

- A click counts as on a line within a quarter of the smallest grid spacing;
  a click in the middle of a bay, or outside the grid, draws nothing and says so.
- A member that already joins those two crossings is not drawn twice.
- The **Section** box of the Tools toolbar applies, as for Draw Frame, and the
  choice is shared between the two tools.
- In elevation (Front or Right view with a level) the vertical lines give the
  columns and the horizontal ones the beams.

The tool needs grid lines: define them first in Define → Coordinate
System/Grids.

# Tools → Quick Draw Shell
The same for panels: a click **inside a grid bay** of the working plane draws a
`ShellMITC4` on the bay's four corners, with the plate section of the Section
box (shared with Draw Shell). A bay that already has a shell is not filled
twice. It needs grid lines; a project without a plate section gets the default
**Slab 20cm** (see Draw Shell).
