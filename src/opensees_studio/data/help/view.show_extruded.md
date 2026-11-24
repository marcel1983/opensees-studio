---
title: View → Show Extruded Sections
group: View
summary: Draw each member with the true shape of its section.
see_also: display.options, assign.geom_transf
order: 1810
---

Sweeps each frame element's cross section along its axis, semi transparently,
with the outline drawn at both ends and along every corner. What is drawn:

- **AISC shapes** (Define → Sections → AISC) — the real profile: an I for W, HP,
  M and S, a channel for C and MC, a tee for WT, MT and ST, a rectangular or
  round tube for HSS and Pipe, an angle for L. Fillets and corner radii are left
  out. A section added before this version has no profile stored: add the shape
  again to see it.
- **Fibre sections** — their rectangular and circular patches as they are
  (a reinforced concrete column shows its cover and core).
- **Rectangular concrete sections** from the wizard — the rectangle.
- **Anything else** whose size is known — the rectangle with the same area and
  second moments (an elastic section typed in by hand, a beam with hinges, a
  fibre section made of single fibres). A truss with only an area is the round
  bar of that area.

The section stands in the member's own local axes, the ones OpenSees uses, and
sits on its insertion point (Assign → Frame → Insertion Point). Two things become
visible that are hard to see otherwise:

- the **physical footprint** — whether members overlap or fit;
- the **orientation** — which way the strong axis of each member bends, which is
  what the distributed load components and the diagram signs refer to.
