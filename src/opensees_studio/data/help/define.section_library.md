---
title: Define → Section Library
group: Define
summary: Elastic, nonprismatic, fibre, aggregated and plate sections, plus the AISC shapes.
see_also: define.material_library, mechanics.fiber_sections, mechanics.shells, define.cold_formed
order: 1040
---

Sections are what frame, shell and zero-length-section elements point at.

# Types
- **Elastic section** — **Material**, E, A, Iz, Iy, G, J, As2, As3, γ. What a
  linear frame analysis needs. As in SAP2000 the section is **made of a
  material** (A572Gr50 by default, when the project has it): E, G = E / 2(1 + ν)
  and the unit weight γ = ρ g are the material's, shown greyed out, and they
  follow the material when it is edited in the library (undo included). An
  *ElasticIsotropic* material gives all three; an *Elastic* or *Steel01/02* one
  gives E only. *(no material)* keeps the three typed in, as older projects had
  them; a material with no modulus (a concrete model) is not offered.
  The **shear areas As2 / As3 are required**; 0 means rigid in shear in that
  direction. The AISC picker fills them from the profile with common
  approximations, not yet checked against a published reference (web d·tw along the depth, 5/3·bf·tf across it for I-shapes and channels,
  2·d·t and 2·b·t for tubes, A/2 for pipes, 5/6·A for a rectangle); the depth is
  local y in a 2D model and local z in a 3D one, so the web area is As2 in 2D
  and As3 in 3D.
  A positive shear area adds shear deformation: an elastic
  beam-column on such a section runs as an `ElasticTimoshenkoBeam`
  (needs G; a 0 in one direction is sent as a rigid area). OpenSees 3.8 loads that element with
  full-length uniform loads (and self weight) only, and PyNite has no shear
  deformation: a member that carries a **point, partial or varying load** is therefore
  analysed with **As2 = As3 = 0** (Euler-Bernoulli). A static case looks only
  at its own load patterns, so such a load in another pattern leaves this
  case's shear deformation alone (the other case types look at every
  pattern). The run log and the results say which members ("…analysed with
  As2 = As3 = 0"). The other members of the same section keep their shear
  deformation. A Timoshenko member takes no `-release`: a released end
  uses the hidden-node route instead. The member deflects by
  `P L³ / (3 E I) + P L / (G As)` on a cantilever; the Property Modifiers' shear
  areas scale As2 / As3, and a multiplier of 0 turns shear deformation off.
- **Nonprismatic (tapered) section** - a table of segments, each running from one
  **elastic** section to another over an absolute length or a fraction of the
  member, with a linear, parabolic or cubic variation. Assigning it splits each
  member into its **Subdivisions** pieces (minimum 12, default 12) of ordinary
  elastic beam-columns; the section at each piece is interpolated from the
  segment's start and end sections (the drawn rectangle/I/pipe/tube dimensions
  are interpolated, so a rectangular depth taper follows its true cubic inertia).
  The pieces keep the frame's end releases, end offsets, insertion and
  modifiers, and every element load is split across them. Editing the template
  refreshes the section properties of members already built from it; changing
  the subdivision count keeps their existing piece count, so set the count
  before assigning the section (or re-import the model) when the topology must
  change.
- **Fibre section** - patches and rebar layers tied to uniaxial materials. It
  yields and cracks where the material does, and needs a non-linear case.
- **Section aggregator** — several responses (axial, bending, shear, torsion)
  combined into one section, each with its own material or section.
- **Plate section** (shell) — E, ν, thickness h and density ρ.
- **LayeredShell** (shell) — a table of layers, each a plate material and a
  thickness, from one face to the other: concrete layers (`PlateFromPlaneStress`
  of `PlasticDamageConcretePlaneStress`, or `PlateFiber`) and rebar layers
  (`PlateRebar` at 0° or 90°, thickness = bar area per unit width). At least three
  layers. OpenSees integrates each layer at its mid-plane, so n equal layers give
  1 - 1/n² of the bending stiffness: use several thin layers (10 or more) through
  a concrete wall or slab.
- **PlateFiber** (shell) — one plate material through the thickness h.

# AISC v16 shapes
"Add from AISC…" picks a shape by name (1,660 of them, 13 families). The values
are the published US-customary ones; the dialog shows the published value *and*
the converted one, and E and G remain your choice, because a shape is geometry,
not a material. The data comes from Steel Construction Manual values and was
cross-checked against an independent source before being committed.

Which inertia is strong depends on the project. A 2D frame bends in the x-y plane
about local z, so the table's strong-axis `Ix` becomes **Iz**. A 3D beam stands
with its depth along local z (local z is vertical for a horizontal member), so
gravity bends it about local y and `Ix` becomes **Iy**, with the table's `Iy` as
Iz. A fibre profile is turned upright the same way in 3D. The dialog's preview
shows the values it will insert. Sections inserted by builds before 0.0.11 into a
3D project have the two swapped: re-insert them, or swap Iy and Iz by hand.
