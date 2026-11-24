---
title: Assign → Frame → Distributed Load
group: Assign — frame
summary: A uniform load along a member: global X/Y/Z by default, or local axes.
see_also: define.plain_pattern, display.force_diagram, assign.frame_point_load
order: 1280
---

# Values
- **Default: global.** Enter **Fx, Fy, Fz**, the force per unit length along
  the global axes. Each selected member projects that vector onto its own
  local axes, so a gravity load `Fz = -q` is vertical on beams and columns
  alike.
- **Use local axes** — tick the box to enter **wx, wy, wz** directly in the
  element's local frame (the old behaviour). OpenSees still receives local
  components either way.
- **Pattern** — which load pattern it belongs to (DEAD, LIVE, …); the one used
  last is offered first. With no pattern yet, a default one is created.
- **Existing loads** — **Add** sums the load with the uniform loads the members
  already have in that pattern; **Replace** removes those first, so assigning
  twice does not double the load; **Delete** only removes them. Point and
  trapezoidal loads, and other patterns, are not touched.
- The local axes come from the geometric transformation and the member's
  orientation; the same physical load can be a different local component on
  members running in different directions.

# Mechanics
The load is applied as equivalent nodal forces and moments by OpenSees for a
linear transformation. The diagram it produces is the member's own bending
moment, which is what Display → Force Diagram draws.
