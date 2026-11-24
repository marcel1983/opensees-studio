---
title: Assign → Frame → RC Wall (MVLEM)
group: Assign — frame
summary: Turn the selected vertical members of a 2D model into reinforced concrete wall segments.
see_also: assign.hinge, define.concrete_section, define.material_library
order: 1470
---

Replaces each selected **vertical** two-joint member with an OpenSees `MVLEM`
segment (Multiple-Vertical-Line-Element Model, Orakcal, Wallace and Conte):
vertical fibres across the wall length — concrete plus the steel at its ratio —
couple axial load and flexure, and one horizontal shear spring at height `c h`
carries the shear. Ids and joints are kept (bottom joint first); members that
are not vertical are left as they are. 2D models only.

# The section
- **Wall length L** and **thickness t**, split into **vertical fibres** of equal
  width; with a **boundary element length** > 0 each end is a boundary element
  with its own **steel ratio** (and fibres of about the web's width).
- **Concrete** and **steel** uniaxial materials (for example `Concrete02` and
  `Steel02`, or those of the Concrete Section Wizard).
- **Shear**: elastic with a shear modulus G (it starts at the concrete's initial
  modulus over 2.4) — one material per segment height is created with stiffness
  `G L t / h`, since the spring is a force-displacement spring of its own segment
  — or an existing uniaxial material for every segment (a nonlinear shear law).
- **Centre of rotation c** (0.4 is the usual value) and the **density** for
  the segment's mass.

# Modelling notes
- The rotation of a segment is lumped at `c h`: use **several segments per
  storey** (draw the wall's members split, or Edit → Divide Frames), and the
  curvature converges to the continuous one — 40 segments give the elastic
  cantilever's `P H³ / 3EI + P H / GA` to 1 %.
- Floors frame into the wall's joints; the wall has no width in the drawing.
- Shear and flexure are not coupled in `MVLEM`. gidopensees' `FiberInt` section
  (shear-flexure interaction) is not available in OpenSeesPy 3.8.
