---
title: Define → Create Truss
group: Define
summary: A simply supported plane truss from a few numbers.
see_also: define.portal_frame, mechanics.static
order: 920
---

Builds the nodes and the `truss` bars of a plane truss into the open project,
as one undoable step, and leaves it selected.

# Values
- **Type** — **Pratt** (verticals, diagonals running down towards mid-span:
  in tension under gravity), **Howe** (diagonals running up: in compression),
  **Warren** (no verticals, diagonals zig-zag to top nodes at mid-panel) or
  **Warren with verticals**.
- **Span**, **Panels** and **Depth at mid-span**.
- **Top chord** — parallel to the bottom chord, **pitched** to a ridge at
  mid-span (with its own depth at the supports), or **triangular** (closed at
  the supports). A pitched truss needs an even number of panels so a panel
  point sits at the ridge; a pitched Warren an odd number, so a top node does.
- **Material** and the **chord** and **web** areas. With no uniaxial material
  in the project, a default elastic steel is created with the truss.
- **Plane**, **Origin**, and whether to restrain the out-of-plane translation.

# Mechanics
The left end is pinned and the right end on a roller, so the truss is
statically determinate externally. A truss bar has no bending stiffness, so in
a frame model (ndf 3 or 6) the rotations of every truss node are restrained;
connect it to frames afterwards only through nodes you free again. The bars
take the **unit weight** on the Members page (steel by default), so the DEAD
case carries them: half of each bar's weight goes to each of its joints.
