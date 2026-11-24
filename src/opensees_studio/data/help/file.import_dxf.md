---
title: File → Import → DXF Drawing
group: File
summary: Straight bars from a CAD drawing, as nodes and members.
see_also: define.portal_frame, edit.check_duplicates
order: 270
---

Reads `LINE`, `LWPOLYLINE` and `POLYLINE` entities and turns them into
beam-column elements. Everything else in the drawing — circles, text, hatches,
blocks — is **counted and reported**: a drawing that imports four members where
you drew two hundred has to say so.

# The values the dialog asks for
- **Layers** — tick the ones that are structure. Construction lines and axes
  usually are not.
- **Units and scale** — the file's own `$INSUNITS` is turned into a factor to
  the project's unit and shown. A drawing with no units gets factor 1 and a note
  saying nothing was converted; set it by hand if the file lies.
- **Read the drawing as** — a plan (XY), a front elevation (XZ, the default:
  that is how frames are usually drawn), a side elevation (YZ), or `3D` to keep
  the file's own X, Y and Z.
- **Plane level** and **origin** — where the drawing plane sits and where the
  drawing's own (0, 0, 0) lands.
- **Merge tolerance** — endpoints closer than this become **one node**. Drawings
  repeat coordinates instead of sharing vertices; the default is one part per
  million of the drawing's size, and the number of merges is reported.
- **Member section** — the section every imported member gets (a default one is
  created if the project has none).

# What it does not do
- No supports and no loads: a drawing cannot say what is fixed or loaded. They
  arrive free; restrain them with Assign → Joint → Restraints.
- Curved polyline segments (bulges) are imported as straight chords, and the
  count is reported. Circles and arcs are not imported at all.
- The whole import is one undo step, and the imported nodes are left selected.
