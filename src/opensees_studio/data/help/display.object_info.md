---
title: Right-click → Object Information
group: Display
summary: Everything the model holds about one joint or one element.
see_also: display.load_assigns, display.options
order: 1720
---

Right-click a joint or a frame member in the model view: the first entry of the
menu, **Object Information: Joint 5…** (or **Element 12…**), opens this window.
With nothing under the pointer it is offered for the one object selected, which
is how a shell is reached. The window is read-only and stays open while you
work, so two objects can be compared side by side.

- **Location** — the id and name; a joint's coordinates and the elements that
  meet at it; an element's type, its joints with their coordinates, its length
  and its local x, y and z axes (the ones the analysis and the loads use).
- **Assignments** — a joint's restraints, mass and groups; an element's section,
  material, local axis angle, end releases (with partial-fixity springs) and
  groups.
- **Loads** — every load on the object, one row each, under its load pattern:
  joint forces and moments, uniform, point and distributed member loads in the
  member's local axes with their position, shell pressures and their direction.

Values are written in the display units (the picker at the bottom right), as on
the canvas with Display → Show Load Assigns.

While a deformed shape or a force diagram is on screen, a right-click on a
member opens its diagram window instead; Display → Back to Model View returns to
this menu.
