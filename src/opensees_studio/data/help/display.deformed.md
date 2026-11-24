---
title: Display → Deformed Shape
group: Display
summary: The structure displaced by the results, with a scale slider.
see_also: display.mode_shape, display.back_to_model
order: 1580
---

Draws the model in its deformed configuration from a static, pushover or
transient case. The scale slider exists because real displacements are usually
invisible next to the structure's size.

- The automatic scale takes a fraction of the model's size, so the shape is
  visible without reading numbers.
- The deformed shape is what actually happened; a shape that looks wrong (a member
  straightening, a joint separating) is usually a modelling error, not a plotting
  one.
- Members bend along their length, as SAP2000 draws them, not only between their
  displaced joints. A beam-column takes the cubic of its end translations and
  rotations; an end with an M2 or M3 release does not follow the joint's
  rotation. A member on an elastic section with span loads draws the elastic
  curve of its moment diagram, so a simply supported beam under a uniform load
  sags even though its joints do not move. A load combination draws the cubic
  (its span loads are not read back). Trusses, links and bearings stay straight.
  Display → Mode Shapes and the time-history animation bend the members the same
  way, from the end rotations.
- Hover a joint while the shape is on screen: the tooltip is a box with the
  joint's label and its displacements in the case drawn (Ux, Uy, Uz in the
  display length unit, rotations in radians, the bound picked for an envelope),
  instead of the joint's model summary. Members show no tooltip here, so the
  pointer reaches the joints easily.
- Right-click a member while the shape is on screen to open its member diagram
  window (see Display → Force Diagram).
- Display → Back to Model returns to the undeformed view.
