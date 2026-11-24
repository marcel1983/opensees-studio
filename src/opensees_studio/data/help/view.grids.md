---
title: View → Show Grids / Show Grid Labels
group: View
summary: Hide or show the grids and their labels, also from the right-click menu.
see_also: define.grid, define.grid_wizard
order: 860
---

- **Show Grids** — draws (or hides) every coordinate system's grid. A hidden grid
  is not snapped to either, so the draw tools then land on the working plane.
  It is the same switch as *Hide All Grid Lines* in the grid dialog, it is saved
  with the model and Ctrl+Z undoes it.
- **Show Grid Labels** — the line ids/coordinates at the ends of the lines.
- **Right-click** on the model view (a click, not a drag: a right drag zooms)
  with **nothing selected** opens the same switches, plus *Grids by system* to
  hide one coordinate system and keep the others, the grid dialogs, Grid Line
  View and the standard views.
- With **something selected** the right-click lists what can be done to it
  instead: the line at the top says what is selected; joints get the
  Assign → Joint options (restraints, masses, springs, constraints, loads,
  links…), frames the Assign → Frame options (section, releases, offsets,
  modifiers, member loads, hinges), shells the Area loads — directly when only
  one kind is selected, in a submenu per kind when several are — then Assign to
  Group, Move, Replicate, Mirror, Delete and Clear Selection. Press Esc or click
  empty space to clear the selection and get the grid menu back.

The menu ticks show whether at least one grid (label) is visible.
