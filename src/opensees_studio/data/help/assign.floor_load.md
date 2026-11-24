---
title: Assign → Area → Floor Load to Frames
group: Assign — areas
summary: A floor load handed to the beams around each bay, one-way or two-way.
see_also: assign.surface_load, assign.trapezoidal_load
order: 1420
---

For a floor modelled with beams only (no shells): select the floor's joints and
the load goes to **every rectangular bay** whose four corners are selected and
whose four sides are framed by beams. A beam meshed into pieces still counts as
one side; a joint in the middle of a beam is not a corner. The load acts
downward (-Z) and reaches the beams as trapezoidal loads in their own local
axes, drawn on the canvas like any other member load.

# Values
- **Load** — force per area, downward.
- **Distribution**
  - **Two-way** — 45° yield lines from the corners: an edge of length L takes
    q min(t, L - t, s/2) along its length (s the bay's short side), a trapezoid on
    a long edge and a triangle on a short one. The four edges carry q × area.
  - **One-way, spanning along X / Y** — the slab spans in that direction, so the
    two beams across the span each take q × span / 2, uniform.

# Limits
A bay must be horizontal, rectangular and axis-aligned to be found from a
selection; a sloped or irregular area is loaded with shells and a surface load.
A 3D model only (a 2D frame takes its beam loads directly).
