---
title: Assign → Frame → Local Axes
group: Assign — frame
summary: Rotate a member's local y/z axes about its longitudinal axis.
see_also: assign.geom_transf, assign.insertion_point
order: 1260
---

# Values
- **Angle about local x** — degrees, positive by the right-hand rule about
  local x (from end i to end j). 0° keeps the default orientation from the
  member geometry.
- **2D models** — a 2D frame has one in-plane bending axis, so the angle is 0°.
  Use a 3D model when the section must turn.
- The rotation changes the axes that carry distributed and point loads, the
  force diagrams, the self weight, the end releases and the section extrusion;
  it does not change the section's A, Iy, Iz or J.
- **Inspect it** — turn on **View → Show Extruded Sections**: each member's
  section is drawn in its local axes.
- IFC export writes the rotation in the member placement and the
  `OpenSeesStudio_Frame` / `OpenSeesStudio_Member` property sets, so the
  section comes back turned.
- **SAP2000** — the S2K export writes the angle; the S2K import still maps it to
  the nearest section orientation, so the exact round-trip is IFC-only for now.

# Mechanics
The local x axis always runs from end i to end j. The angle turns the local y
and z axes about it; the section, its loads and its diagrams turn with them.
