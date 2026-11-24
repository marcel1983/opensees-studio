---
title: Tools → Draw Frame (F2)
group: Edit and tools
summary: Click points to draw a chain of beam-columns, with the section you choose.
see_also: tools.draw_truss, assign.section
order: 790
---

The first click starts the frame and every next click ends it **and starts the
next one there**, so a beam line or a column stack is drawn without lifting the
pen. **Esc**, or a second click on the last point, ends the chain. Each point
may be an existing node or a grid intersection (a node is created if there is
none there). Each frame is its own undo step.

- **Section** — while the tool is armed, the Tools toolbar shows a Section box
  with the project's frame sections (shell sections are left out); the frames
  take the one chosen, and the choice is kept for the next time. An elastic
  section draws an `ElasticBeamColumn`, a fibre section or an aggregator a
  force-based `ForceBeamColumn`, and a nonprismatic section is subdivided as it
  is assigned. With no section in the project, a default elastic section is
  created with the first member, in the same undo step.
- The left-hand object-snap icons target existing members: **midpoint**
  (amber), **perpendicular** (blue) and **nearest point** (green). From the
  last point, the perpendicular snap drops the next point on the foot of the
  perpendicular to the member under the cursor.
- **Preview** — once the first point is set, a dashed line in the frame colour
  runs from it to the point the next click would use (the joint, grid crossing
  or member snap under the cursor, all highlighted), so you see the member
  before it is created. It disappears with Esc or when the tool is left.
- Releases, hinges or another element type: Assign → Frame afterwards.
