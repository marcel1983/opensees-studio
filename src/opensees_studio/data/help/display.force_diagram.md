---
title: Display → Force Diagram
group: Display
summary: Axial, shear, moment or torsion diagrams along the frame members.
see_also: display.deformed, assign.distributed_load, display.shell_contours
order: 1630
---

Draws the element force component you pick (N, V2, V3, T, M2, M3) as a diagram
along each member, at the analysis step you pick.

# Reading it
- The end-j sign is flipped internally so a diagram is continuous across an
  element: a jump at a joint means a real discontinuity (a hinge, a point load,
  or two members with different sections).
- A member under span loads (uniform, point, trapezoidal, self weight) is drawn
  with **intermediate stations**: the internal forces follow from the end forces
  and the loads by statics, so the moment is parabolic under a uniform load and
  piecewise linear under point loads, with the shear jumping at each point, and
  the largest value between the ends is labelled. A member without a span load
  stays a straight line between its ends. Stations are drawn for the results of a
  static case; a combination or envelope (whose cases are not at hand) draws
  straight lines between the ends.
- Diagrams are drawn **between the two ends of a line element**. Shells, quads
  and other face elements have no two-end station, so they are skipped rather
  than drawn wrongly; if no line element returned forces the log says so.
- The values come from the analysis results, not from a hand calculation: what
  you see is what the solver computed.

# A member in detail
- With a force diagram or a deformed shape on screen, **right-click a frame
  member**: a window opens with nine panels in a **3 x 3 grid** (three rows,
  three columns): axial force; shear V2; shear V3; torsion T; moment M2; moment
  M3; absolute and relative deformations; distributed loads wx/wy/wz; and point
  loads. The force panels draw both bounds of an envelope.
- Each panel **labels its extreme values**, the **Results** picker switches
  between the stored static cases and the load combinations without leaving the
  window, and the **Units** picker changes the display system.
- The **Distance** box places a vertical cursor on every panel and reports the
  value of every curve at that section.
- Without one of those views the right-click keeps its usual menu, as it does
  on empty space or on a shell.
- The **relative** deformation is the departure from the straight chord. For a
  linear-elastic section it integrates the member's moment diagram with its EI;
  otherwise it interpolates the end rotations.
- Applied loads are the span loads of the active static case (distributed,
  point and self weight). A combination bound has no single load pattern and
  says so.
