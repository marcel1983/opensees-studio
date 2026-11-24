---
title: View → Show Local Axes
group: View
summary: Draw each member's local x/y/z axes beside its midpoint.
see_also: view.show_extruded, assign.local_axes, display.options
order: 1820
---

Three short lines at the middle of every frame member: **x red** (along the
member, node i to node j), **y green** and **z blue**. They are the exact axes
OpenSees uses for that member, including the geometric transformation and any
Assign → Frame → Local Axes rotation, so they answer the question a globally
entered load or a force diagram raises: which way is local y here?

The triads scale with each member (22 % of its length) and are not pickable.
Turn them off again in View → Show Local Axes, View → Visibility, or Display
Options. The toggle is per viewport and travels with the project.
