---
title: Edit → Interactive Table Editing
group: Edit and tools
summary: Joints, elements and joint loads as spreadsheets: edit, paste, add, delete.
see_also: edit.select_all, select.menu
order: 640
---

The model as tables, SAP2000's interactive database editing (Ctrl+T). Nothing
changes until **OK**, which checks every cell and every reference and applies
all the tabs as one undo step. A bad cell keeps the window open and names its
table, row and column.

# Tabs
- **Joints** — ID, name, coordinates, restraints and masses. Only the DOFs the
  model has are columns: a 2D frame shows X, Z, Ux, Uz, Ry. Restraints are **1**
  (fixed) or **0** (free); yes/no and x also work. A new row with an empty ID
  gets the next free joint number.
- **Elements** — name, joints (space separated, i then j), section and material.
  The type is read only, and elements are not added here (draw them or use a
  wizard); rows can be deleted.
- **Joint Loads** — one row per load: the Plain pattern (its name or id), the
  joint and the force components. Add rows to load more joints.

# Spreadsheet keys
- **Ctrl+C** copies the selected cells as tab-separated text, **Ctrl+V** pastes
  a block from Excel or LibreOffice at the current cell and adds the rows it
  needs (Joints and Joint Loads). Read-only columns are skipped.
- **Delete** clears the selected cells; **Delete Rows** removes whole rows.
- A decimal comma is read as a point.

# Notes
- Deleting a joint that an element, a constraint or a load still uses is refused
  at OK; delete those first or delete the joint from the canvas (which takes its
  elements with it).
