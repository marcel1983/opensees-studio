---
title: Display → Display Options
group: Display
summary: Labels, masses and the on-screen size of model markers.
see_also: view.show_extruded, options.units
order: 1700
---

Toggles the annotations and the heavy overlays:

- **Node labels** and **element labels** — the name, or `N#`/`E#` when there is
  none. **Label height** sets their text size separately, in pixels.
- **Joint masses** — a purple diamond at every joint with a non-zero lumped
  mass. Off by default because most models carry mass on many joints.
- **Nodes, Supports, Load arrows, Reactions, Masses, Releases** — each marker
  can be a percentage of the viewport height. The renderer converts that
  percentage to world units with the camera, so the marker keeps the same size
  on screen at every zoom level. Release dots are screen-space points like the
  nodes. The values are per viewport and travel with the project. Distributed
  member loads (uniform and trapezoidal) use this size for their line diagram:
  a top line through the arrow tails, offset against the load, with V-shaped
  heads on the member.
- **Local axes** — a small red/green/blue x/y/z triad beside the midpoint of
  every frame member, using the same axes as the analysis and the global→local
  load conversion. It is also the View → Show Local Axes toggle.
- **Section extrusions** (View → Show Extruded Sections) — each member's real
  cross section (I, channel, tee, tube, pipe, angle, fibre patches) swept along
  it, so the physical footprint and the local axes are visible.
- The **reference triad** at the origin (coloured X, Y and Z arrows) is not a
  toggle: it is small, scaled to the model, and it is what tells you which way
  the elements run in an isometric view.
