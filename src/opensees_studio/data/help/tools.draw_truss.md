---
title: Tools → Draw Truss (F3)
group: Edit and tools
summary: Click points to draw a chain of pin-jointed bars.
see_also: tools.draw_frame, concepts.model
order: 800
---

Draws a `TrussElement`: it carries axial force only and has no moment
connection. Use it for bracing and for genuinely pin-jointed members. Like
Draw Frame, every click after the first closes a bar and starts the next one
there; **Esc**, or a second click on the last point, ends the chain. As in
Draw Frame, a dashed line previews the next bar from the last point to the
snapped point under the cursor.

- The bar points at a **material** and an area, not a section. If the project has
  no uniaxial material, a default elastic one is created with the bar.
- In a 3D model a truss contributes stiffness only along its axis; a node that
  only touches trusses needs its other DOF restrained or it will be a mechanism.
