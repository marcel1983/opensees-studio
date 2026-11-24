---
title: View → Visibility
group: View
summary: Show or hide model categories in this viewport.
see_also: view.colors, view.grid_line_view
order: 1830
---

One checkbox per category: grids, nodes, frames, shells, restraints, footings,
constraints, frame assignments, releases, loads, node and element labels, and
extruded sections. A change is **per viewport** - the model keeps every entity, so the
tree, the analysis and the other views are unaffected.

**Releases** draws a colored dot on each released member end: violet for
torsion, orange for M2, red for M3, and yellow for partial fixity. A release
with more than one action shows one staggered dot per action. It is separate
from **Frame Assignments**, which draws the rigid end-offset bars.

- **Hide Selected** (Ctrl+H) hides what is selected now, adding it to what is
  already hidden.
- **Isolate Selected** (Ctrl+Shift+I) shows only the selection: selected
  elements keep their joints visible, and every other object is hidden. It is
  also in the right-click menu.
- **Invert Visible** swaps the two sets: what is drawn disappears and what was
  hidden comes back.
- **Show All Objects** restores everything. A box selection never picks what is
  hidden in this viewport.

**Footings** draws the footings and pedestals of Design → Footings (isolated and
combined) as translucent concrete boxes under the supports, so the top view is
the foundation plan.

Hiding is how to look inside a dense model (the framing under a slab, the inside
of a wall of shells) without deleting or filtering anything.
