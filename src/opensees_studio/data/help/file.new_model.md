---
title: File → New Model (Ctrl+N)
group: File
summary: Pick the units and a template: blank, grid, beam, truss, frame, warehouse or building.
see_also: file.new, file.new_2d_frame, define.grid_wizard, define.warehouse, define.building
order: 180
---

The way SAP2000 starts a model: the **units** first (the last ones you chose are
offered again), then a **template**. Double-click a template or press OK.

- **Blank** — an empty 3D model (ndm 3, ndf 6) with the Dead load case, the
  same as File → New Blank 3D Model.
- **Grid Only** — an empty 3D model, then the Grid Wizard to lay out the lines
  you will draw on.
- **Beam** — a continuous beam in a 2D frame model: the number of spans and
  their length; a pin at the left end and rollers on the other supports, with a
  grid line on each support.
- **2D Truss** — a 2D truss model (Ux, Uz per joint), then the Truss Wizard.
- **2D Frame** — a 2D frame model, then the Portal Frame Wizard and its grid
  (File → New 2D Frame).
- **3D Frame** — bays along X and Y, storeys, the two bay widths and the storey
  height: columns fixed at the base and beams both ways on every floor, on a
  grid with a line at every column and floor.
- **Warehouse** — a 3D model, then the Warehouse Wizard: portal frames,
  purlins, girts, bracing, roof loads and the combinations of a design code
  (Define → Create Warehouse).
- **Building** — a 3D model, then the Building Wizard: a multi-storey frame
  with its storeys, rigid diaphragms, floor loads, the earthquake and the
  combinations of a design code (Define → Create Building).

The Beam and 3D Frame members take a default elastic section, created with
them; assign the real ones with Assign → Frame → Section. Everything the
template creates is one undo step. A model with unsaved changes asks before it
is replaced.
