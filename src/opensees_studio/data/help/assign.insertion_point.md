---
title: Assign → Frame → Insertion Point
group: Assign — frame
summary: Which point of the cross section sits on the line between the joints.
see_also: assign.end_offsets
order: 1320
---

# Values
- **Cardinal point** 1-11, as in SAP2000: 1-3 bottom left/center/right, 4-6
  middle, 7-9 top, 10 centroid, 11 shear center (taken at the centroid). Bottom
  and top are -/+ local 2 (local y), left and right -/+ local 3 (local z),
  looking from end i towards end j. Point 8 puts the top of a 2D beam at the
  joints.
- **Offset along 2 / 3** — a further offset of the member at both ends; a 2D
  frame cannot be offset along 3 (out of its plane).
- The section size comes from an elastic section's shape (or the rectangle with
  its A, Iz and Iy) or a fibre section's patches.

# Mechanics
Realised with the same rigid joint offsets as end offsets: the member's flexible
length is unchanged, and an axial force along the offset axis bends it.
