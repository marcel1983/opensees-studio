---
title: Assign → Frame → Trapezoidal Load
group: Assign — frame
summary: A load varying linearly over part or all of a member: global by default.
see_also: assign.distributed_load, assign.end_offsets
order: 1350
---

# Values
- **Default: global.** Enter **Fx, Fy, Fz** at the **start** and the **end**;
  each selected member projects both end vectors onto its own local axes.
- **Use local axes** — tick the box to enter **wx, wy, wz** directly in the
  element's local frame; the values vary linearly in between.
- **x/L start / end** — where the load starts and ends, as fractions of the
  joint-to-joint length from end i. Equal start and end values give a partial
  uniform load.
- **Pattern** and **Existing loads** — as for the distributed load: Replace and
  Delete act on the members' trapezoidal loads in that pattern only.

# Mechanics
On an elastic or displacement-based element each linear piece is emitted as
three `-beamPoint` loads at its Gauss points, which give exactly the fixed-end
forces of the linear load (OpenSees 3.8's 3D elastic element ignores the end
values of a native trapezoidal load, and `dispBeamColumn` drops it with a
warning). A force-based element takes the native
`-beamUniform wa ... aL bL wb ...`, integrated at its integration points (exact
for a full-length load on an elastic section). A part on a rigid end zone goes
to the joint.
