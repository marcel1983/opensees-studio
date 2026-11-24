---
title: Define → Section Designer
group: Define
summary: Draw any cross-section, or import it from a DXF, and add it as an elastic or fibre section.
see_also: define.section_library, define.concrete_section, file.import_dxf
order: 1000
---

For a section no library has: a built-up girder, a shape with openings, a
precast profile, a section drawn in CAD. The section is a list of **regions** —
polygons and circles, each solid or a **hole** — in the local (y, z) plane: y up
the depth, z across, lengths in the project's unit.

# Drawing
Type a command and press Enter (the buttons type one for you; edit the numbers
before running it):

- `rect W H [Y Z]` — a rectangle W wide by H deep, centred at (Y, Z);
- `circle D [Y Z]`;
- `poly Y1,Z1 Y2,Z2 Y3,Z3 ...` — a polygon through its vertices;
- `ishape D BF TF TW`, `channel D BF TF TW`, `tee D BF TF TW`, `angle D B T`,
  `tube W H T`, `pipe D T`, each with an optional `Y Z`;
- `hole <shape> ...` — any shape as a hole (`hole circle 0.1 0 0.05`);
- `move N DY DZ`, `delete N` (N is the number in the list, or `last`),
  `center` (centroid to the origin), `clear`.

**Undo** steps back one command; **Solid / hole** flips the selected region.

# Import DXF
Reads the closed outlines of a drawing: closed polylines (arcs from bulges
included), circles, closed ellipses and splines; curves are flattened finely, a
circle stays exact. An outline inside another is a hole (inside two, solid
again). The drawing's X becomes z and its Y becomes y. `$INSUNITS` gives the
scale to the project's unit (a unitless file is taken as project lengths, and
the message says so); the section is then centred. Lines, open polylines and
text are counted and left out.

# Properties
Area, centroid, Iz = ∫y² dA and Iy = ∫z² dA about the centroid, the product
Iyz and the principal moments with their angle, elastic and plastic moduli,
radii of gyration, and the **torsional constant J**, solved for Saint-Venant
torsion on a grid (Prandtl stress function, hollow shapes included): within a
fraction of a per cent for compact and hollow shapes, a few per cent for thin
open ones. An unsymmetric section is noted: OpenSees' elastic section has no
Iyz, so its principal axes are not followed.

# What OK adds
- **Elastic section**: A, Iz, Iy, J and E with G = E / (2 (1 + ν)). Pick a
  material to copy its initial modulus, or type E.
- **Fiber section**: one uniaxial material on a grid of fibres (cells per side
  of the bounding box); each fibre sits at the centroid of the part of its cell
  inside the section, measured from the section's centroid, and the fibre areas
  add up to the exact area. GJ (for 3D members) starts at G J.
