---
title: File → New Blank 3D Model
group: File
summary: An empty three-dimensional model: ndm = 3, ndf = 6.
see_also: file.new_2d_frame, define.grid
order: 190
---

Creates a new project with six degrees of freedom per node (Ux, Uy, Uz, Rx, Ry,
Rz) and nothing in it. Use it for a space frame, a building with slabs, or
anything where the out-of-plane behaviour matters.

- The project is **dirty** and unsaved until you save it; closing or creating
  another one asks first if it is.
- A never-saved project writes a **pre-run snapshot** next to the app data when
  an analysis starts, so a crash does not lose the model.
- A grid is not created for you: Define → Coordinate System/Grids, or start from
  File → New 2D Frame, which brings the wizard and its grid.
