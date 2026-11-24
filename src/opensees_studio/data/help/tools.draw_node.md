---
title: Tools → Draw Node (F4)
group: Edit and tools
summary: Place nodes by clicking grid intersections.
see_also: define.add_node, define.grid
order: 780
---

Each click creates a node at the grid intersection under the cursor (or reuses
the node already there). The grid has to be visible: if the project has none,
Define → Coordinate System/Grids offers to create one, because a canvas that
rejects every click looks broken rather than empty.

- Snapping follows the **working plane** (the level chosen in View → Top/Front/
  Right): only that level's lines and intersections are active.
- The left-hand object-snap icons can also land the node on an existing member:
  its midpoint (amber) or the point nearest the cursor (green). Perpendicular
  needs a first point, so it is offered by the two-click draw tools.
- The nodes are created in one command each, so Ctrl+Z removes them one at a time.
- *F4*, not F1: **F1 is the contextual help** everywhere in the application.
