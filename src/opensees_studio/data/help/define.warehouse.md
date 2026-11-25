---
title: Define → Create Warehouse
group: Define
summary: A 3D steel warehouse from a few numbers: loads, wind, earthquake, ash or snow.
see_also: define.section_library, define.portal_frame, define.truss, define.building, file.new_model
order: 930
---

Builds a warehouse (bodega, nave industrial) into the open 3D frame model as one
undoable step: portal frames in X-Z planes repeated along Y, with rafters or
with roof trusses, the purlins, girts and X bracing between them, the end wall columns, the supports, a group per kind
of member and section, a grid on the column lines, the roof loads, the wind and earthquake
cases and the load combinations of a design code.
File → New Model → **Warehouse** starts a new model with it. The preview on the
left follows every field.

# Geometry
- **Roof** — two slopes (gable), one slope, or flat, with its **slope**.
- **Nave span** and **number of naves** — naves stand side by side with a
  column line between them; a gable roof covers them all, with the ridge at
  mid-width.
- **Number of frames** and **distance between frames** — the building's length
  is their product, less one bay.
- **Eave height** and **column bases** (fixed or pinned).
- **Roof structure** — rafters, or roof trusses (see below).
- **Eave overhang** (alero) and **Overhang on** — how far the roof goes on past
  the side walls, measured in plan from the wall, over both side walls or one;
  0 builds none. At each frame a cantilever goes on from the eave along the
  slope of the roof (down on a gable, up past the high wall of one slope), with
  its own section, and purlins on it at the purlin spacing, the last one at the
  tip. The roof loads, snow and ash take it as roof (the snow at the eave's
  value), and so does the roof's mass. Under wind it takes the roof's pressure
  at the eave on top and the pressure of the wall below on its underside
  (EN 1991-1-4 7.2.1 (3)): the wind against a wall lifts its overhang. The
  steel check takes the cantilever as unbraced along its whole length (its
  bottom flange is in compression and the purlins hold the top one).

# Roof trusses
With **Roof trusses** each frame carries the roof on a truss instead of a
rafter:

- The **top chord** follows the roof line, with a panel point under every
  purlin line, so the purlin spacing is also the panel of the truss.
- **Bottom chord** — *horizontal*, at one level below the eave, or *parallel to
  the roof*. **Truss depth** is measured plumb: at the eave for a horizontal
  chord (the truss is deeper towards the ridge by the rise of the roof), and
  everywhere for a parallel one. The eave height stays the top of the roof
  line, so the clear height under the truss is the eave height less the depth.
- **Truss web** — a vertical under every purlin line, and one diagonal per
  panel: **Pratt** (down towards the middle of the nave: in tension under
  gravity next to the columns), **Howe** (up towards the middle) or **Warren
  with verticals** (alternating from each column line). Each nave has its own
  pattern.
- The chords are **continuous** and run into the columns, and a column goes on
  up to the top chord: the truss and its columns work as a frame, which is what
  holds a building on pinned bases against the wind across it. Verticals and
  diagonals are **pinned** at both ends.
- **Bottom chord tie every** — the bottom chord is tied to the next frame at
  the column lines and at the ridge, and besides at every n-th panel point. In
  the braced bays each tie line gets a vertical X between the two chords (sway
  bracing) that takes it up to the roof bracing; at the side walls the wall
  bracing does that, and a girt line at the level of the chord is the tie.
- An end wall column passes through the bottom chord of the end truss and is
  its vertical there. Where a horizontal bottom chord lies on a girt line of
  the end wall, the chord carries that strip of cladding.

A purlin is fixed to the top chord itself, so **every purlin braces the top
chord** and the stabilising angle setting of the purlins does not apply. The
**bottom chord is braced only at its tie lines**: it is the chord in
compression when the wind lifts the roof, and the wizard writes the distance
between tie lines as its unbraced length. A column is braced where the bottom
chord meets it.

# Purlins, girts and bracing
- **Model the roof purlins** and **Model the wall girts** — untick either to
  leave those members out of the model, each on its own. Without purlins the
  roof loads (cladding, live load, snow and ash, wind, the roof's mass) go on
  the rafters (or the top chords, and the overhangs) of each frame as a
  distributed load, half the bay to either side; only **roof struts** tie the
  frames, at the eaves, the ridge, the column lines and wherever the roof
  bracing meets the rafters, so the bracing still has its load path. The purlin
  spacing still places the nodes of the rafter (the panel points of a truss),
  and the rafter counts as unbraced from the eave to the ridge. Without girts
  the wind on the walls goes on the columns, half the way to their neighbours.
- **Purlin spacing** — the largest distance between purlin lines, on the roof
  surface. Each stretch of roof between a column line and the next (or the
  ridge) is divided into equal parts no longer than it. The eave and ridge
  purlins are also the eave strut and the ridge tie.
- **Girt spacing** — the same on the two side walls; 0 builds no girts.
- **End wall column spacing** — the largest distance between the columns of
  the two end walls; 0 builds none. Each nave is divided into equal parts and
  each column goes under the nearest purlin line, so its top reaction enters a
  purlin and reaches the roof bracing. An end wall column is pinned at its base
  and at the rafter, with its web along Y to span against the wind; it also
  props the end rafter. With end wall columns the end walls get girts too, at
  the girt spacing, up to the roof line.
- **Stabilising angle every** — see below.
- **Sag rod lines per bay**, for the purlins and for the girts: lines of rods
  that hold every purlin (or girt) sideways, 1 at mid-span, 2 at the third
  points. They are not modelled: with **Set the unbraced lengths of the steel
  check** ticked, each purlin and girt gets the distance between them as its
  minor-axis and lateral-torsional lengths.
- **Sheeting screwed to the purlins and girts** — a through-fastened roof and
  wall sheeting braces the flange it sits on. The steel check (AISI S100-16)
  then takes a purlin under gravity, or a girt under pressure, as braced along
  its length; under uplift or suction the free flange is in compression and
  the member counts on its sag rods, or on the R factor of I6.2.1 where the
  section is within its limits. Untick it for a standing seam roof. See
  Design → Steel Frame Check.

# A purlin does not brace the rafter by itself
A purlin sits on the rafter's top flange. It holds that flange, but not the
bottom one, which is the compression flange near the eaves under gravity and
along most of the rafter under wind uplift. Only a **stabilising angle** (fly
brace) from the purlin down to the bottom flange makes the purlin a bracing
point. So:

- with **None**, the rafter's unbraced length for the steel check is the whole
  length from the eave (or an interior column) to the ridge;
- with **1**, every purlin has an angle and the length is the purlin spacing;
  with **2**, every second purlin, and so on.

The girts follow the same rule for the side columns and for the columns of the
end walls. With **Set the unbraced
lengths of the steel check** ticked, the wizard writes these lengths as the
minor-axis and lateral-torsional overrides of every rafter and of those columns
(Design → Steel Frame Check → member overrides); without them the check would
take every purlin as a bracing point. The major-axis length stays as modelled.

In the analysis model the purlins, girts and braces are **pinned at both ends**
(no bending moments; a purlin's torsion is held at one end only), so they bring
their load to the frames and add no bending or torsional restraint to them.
They also stay **one piece**: their Auto Mesh is off (Assign → Frame → Auto
Mesh), so Run does not cut the two diagonals of an X where they cross, nor a
purlin or girt where a diagonal passes over it. A purlin spans from rafter to
rafter and a brace from corner to corner.

# Bracing
The roof and the side walls are braced on their own page, each with its own
bays, so the whole roof can be braced and only two bays of each wall.

- **X bracing in the roof** and its **braced bays** (bay numbers separated by
  commas; bay 1 is between the first two frames; empty means the first and the
  last).
- **X panels per roof slope** — how many X each slope of roof has across the
  building in a braced bay (a slope is the roof between a column line and the
  ridge, or the next column line). The panels end on purlin lines, so there are
  at most as many as purlin spaces. **Automatic** makes each panel about as
  long as the bay, so the diagonals stay near 45 degrees.
- **X bracing in the side walls** and its **braced bays**; empty means the
  bays the roof has.
- **Roof braces work in tension only** and **Wall braces work in tension
  only**, each on its own (both ticked by default). With roof trusses the
  sway bracing between the chords follows the roof.
- **Roof stiffeners** — *beams* or *trusses* along the building, from frame to
  frame and framed into the rafters: one at mid-span of each nave and
  **Stiffener lines each side of mid-span** more, evenly between it and the
  columns, each on the nearest purlin line. Each takes the place of the purlin
  on its line, and its load. A stiffening truss has that beam as its top chord,
  a bottom chord **Stiffening truss depth** below it, a vertical at every frame
  and one diagonal per bay (only on a roof with rafters). With stiffeners the
  roof X braces are cut at their lines: each X lies within a space between two
  of them, and **X panels per roof slope** then counts the panels of each space.
- **Bracing of a braced bay** of the side walls — one **X from the base to the
  eave**; a **double X with a strut at mid-height** (two X one above the other;
  the strut is the girt line nearest mid-height when the wall has girts, which
  then has the strut's section and keeps its wind); or a **moment frame**, whose
  eave member in that bay is a beam framed into the two columns, which hold the
  wall along the building by bending about their minor axis.

**Work in tension only** is for rods and slender
angles, which buckle as soon as they are pushed: each X then holds with the
diagonal the load stretches. The braces become tension-only members (Assign →
Frame → Tension Only), and since which diagonal works depends on the whole load,
the results of separate cases cannot be added: **each combination is analysed
as a case of its own**, named "Comb: " and the combination's name, under its
factored patterns, by Newton iteration. The combinations keep their names and
each one reads its case, so the envelopes and the steel check work as before.
Untick it for braces that also take compression (the two diagonals of an X then
share the load and the combinations add the cases).

# Sections
One section per kind of member. Choose one the project has, or let the wizard
create the default. **Section Library…** opens Define → Section Library over the
wizard: add shapes of the AISC library (Add from AISC…), a cold-formed
profile (Add Cold-Formed (AISI)…) or a section of your own, close it, and the
new sections are in every list of the page. Each one is added as its own
undoable step, so it stays in the project even if you cancel the wizard.

The defaults are **W14X48** columns, **W16X40** rafters, **L3X3X1/4**
braces, **W8X31** end wall columns, **W8X18** overhangs and stiffener beams,
**HSS4X4X1/4** stiffening truss chords and wall struts, **HSS3X3X3/16**
stiffening truss webs and **W12X26** wall moment frame beams from the AISC library, and a cold-formed
lipped channel **C 150 × 50 × 15 × 2.38 mm** for purlins and girts, of the
project's default steels. A roof truss takes **HSS6X6X1/4** chords,
**HSS3X3X3/16** verticals and diagonals and **HSS4X4X3/16** bottom chord ties;
the page lists only the members the roof structure has. Change them afterwards
with Assign → Frame → Section on the groups the wizard creates, one per kind of
member and section, named after both ("Columns W14X48"): Columns, Rafters,
Purlins, Girts, Roof bracing, Wall bracing, End wall columns, Overhangs, Roof
struts, Roof stiffeners, Stiffening truss web members, Wall bracing struts, Wall
moment frame beams; with trusses also
Truss top chords, Truss bottom chords, Truss web members, Bottom chord ties and
Truss sway bracing. A purlin's web stands normal to the
roof and a girt's lies flat. The defaults are a starting point, not a design:
run the cases and the steel check, and size the members from them.

# Loads and design code
- **Roof dead load** — cladding and fixings, per area of roof surface; it goes
  into the dead load case, which already carries the self weight of the steel.
- **Roof live load** — per area of horizontal projection, in its own case.
- **Live load at mid-span** — a concentrated load at mid-span of each nave of
  every frame, in the same case.
- **Design code** — sets the defaults of the two live loads and the
  combinations: **RNC-07** (Art. 11 a, light roofs: 10 kg/m² plus 200 kg at
  mid-span of the main members; the roof live case is the code's CV),
  **NSCM Managua** (the same gravity loads, as roof live CVT), **ASCE 7-16**
  LRFD or ASD (Table 4.3-1: 20 psf, before any reduction), or **EN 1990**
  (the Eurocodes: a roof of category H of EN 1991-1-1, 0.4 kN/m²; its 1 kN
  concentrated load is a separate local check and is not created). The
  Eurocode values are the recommended ones: check them against the National
  Annex of the country. The steel check of the app stays AISC 360.

The area loads are applied to the purlins as uniform loads over their tributary
width, in the purlin's local axes. With **Generate the load combinations of the
code** the combinations of the gravity, wind and earthquake cases the wizard
creates are added with their envelope; the **Load combinations** page, the
last one, shows them before Finish.

**Direct analysis method (AISC 360 Chapter C)** — ticked, every combination
(the code's, or those of the Load combinations page) is solved to second
order under its factored loads together, since a P-Delta analysis does not
superpose: P-Delta in every frame and Newton iteration in 10 steps, the
stiffness times 0.8 (C2.3; τb = 1 with the extra notional load 0.001 Yi of
C2.3(c) in every combination) and the notional loads 0.002 Yi of C2.2b,
Yi being the factored gravity load at each level. A gravity-only combination
becomes four cases, `DAM <name> N+X`, `N-X`, `N+Y` and `N-Y`, and the
combination the envelope of the four; a combination with wind or earthquake
is one case, `DAM <name>`, its notional load along its main lateral load. The
combinations keep their names, and the steel check takes these cases with
K = 1 (Design → Design Basis gets the direct analysis method). This holds
while the second- to first-order drift ratio stays at or below 1.7
(C2.2b(d)): check it, or use Design → Direct Analysis Method, which adds the
first-order twins. LRFD codes only; it replaces the per-combination cases of
tension-only braces, which it covers.

**AISC 341 system across (X)** and **along (Y)** — the lateral system of the
portal frames and of the bracing, written to Design → Design Basis: an AISC
341 system the steel check covers adds its width-to-thickness and capacity
design checks; *None* leaves the AISC 360 check alone.

The load cases the wizard creates use the sparse solver **UmfPack** (Define →
Load Cases → System). A warehouse has hundreds of pinned members, each with its
own released rotations, and the band solver a new case has by default takes
tens of seconds per case on it for the same result. A case the project already
had keeps its solver; the log says so when the model is large.

# Wind
With **Create the wind load cases** the wizard adds one load case per wind
direction ticked under **Wind towards** (the wind blows towards +X, -X, +Y or
-Y; X is across the ridge), with the net pressures of the main structure on the
four walls and the roof.

- **Procedure** — follows the design code; it can be changed.
- **RNC-07 Título IV** (static method, Type 1 structures; NSCM 7.2 sends the
  wind loads here too). **Wind zone** fills the regional velocity VR of Tabla 5
  (zone 1: 30 m/s, zone 2: 45, zone 3: 56 for Group B, 50 years; 36, 60 and 70
  for Group A, 200 years); type another one in **Wind speed**. **Exposure** is
  the terrain roughness R1 to R4 (Tabla 6) and **Topography** T1 to T5 (Tabla
  7). The pressure is pz = 0.0479 Cp VD² kg/m² with VD = FTR Fα VR, and Cp of
  Tabla 8: windward wall 0.8, leeward wall -0.4, side walls -0.8, flat roof
  -0.8, leeward slope -0.7, windward slope 0.04 θ - 1.6 between -0.8 and 1.8.
  With the wind along the ridge the roof takes -0.8 (a surface parallel to the
  flow; Tabla 8 has no row for it). One case per direction: `WIND +X`, …
- **ASCE 7-16**, chapter 26 and the directional procedure of chapter 27.
  **Wind speed** is the basic wind speed V of the risk category, an *ultimate*
  speed: a 50 year velocity such as RNC-07's is multiplied by 1.26 (√1.6)
  first. **Exposure** B, C or D, **Kzt** the topographic factor; Kd = 0.85 and
  G = 0.85. qz = 0.613 Kz Kzt Kd V² on the windward wall and qh, at the mean
  roof height, everywhere else; Cp of Figure 27.3-1. Two cases per direction:
  **A** takes the most negative roof coefficients with positive internal
  pressure (the largest uplift), **B** the other roof coefficients with
  negative internal pressure (the largest downward load and the largest push on
  the windward wall): `WIND +X A`, `WIND +X B`, …
- **EN 1991-1-4**, section 7.2, recommended values. **Wind speed** is the
  basic wind velocity vb of the National Annex, a *10 minute mean* (a 3 second
  gust such as RNC-07's is about 1.5 times larger). **Exposure** is the terrain
  category 0 to IV (Table 4.1) and **Topographic factor** the orography factor
  co. The peak velocity pressure qp = [1 + 7 Iv] ρ vm² / 2 (Expression 4.8) is
  taken at the height of the ridge for every surface, and w = qp (cpe - cpi).
  Walls by Table 7.1: windward D and leeward E by h/d, and A, B, C (-1.2, -0.8,
  -0.5) *along* the walls parallel to the wind, from the windward corner. Roof
  by Tables 7.2 (under 5°), 7.3 and 7.4: the zones F and G along the windward
  edge, F at its corners, then H, I and J, so the members near the windward
  edge and its corners take more than the rest. Where the tables give a
  negative and a positive value for a slope, each is a case: across the ridge
  of a duopitch roof **A** (all negative, +0.2 inside), **B** (all positive,
  -0.3 inside), **C** (windward slope positive, leeward negative) and **D**
  (the opposite); a direction with one set of values gets **A** and **B**, with
  +0.2 and -0.3 inside.
- **Openings** — a closed building has no internal pressure in RNC-07 and
  ±0.18 in ASCE 7. Openings spread over the four walls: -0.3 (RNC-07 Art. 55)
  and ±0.18. Openings mainly in one wall (more than 30 % of it): 0.75 when
  that wall faces the wind, -0.6 when it is to leeward and -0.5 when it is
  parallel to the wind (RNC-07), or ±0.55, a partially enclosed building
  (ASCE 7). EN 1991-1-4 takes +0.2 and -0.3 for a closed building or openings
  spread over the walls (7.2.9 (6), Note 2), and for a dominant wall 0.90 of
  the external coefficient at that wall (openings three times the others').

Where the pressures go: the roof to the **purlins**, each taking half the strip
to its neighbours, normal to the roof. A wall with girts to its **girts**; the
top half strip of a side wall goes to the eave purlin, the strip under the roof
line of an end wall to the end rafter, and the lower half of the lowest strip
straight into the ground (it is not applied). A wall without girts loads its
**columns** directly, each with the wall half way to its neighbours.

In the combinations each wind case enters with **its own sign only**: a case
already has its direction and its suctions, and reversing it is not another
wind. Define → Load Combinations → Generate treats a static wind case as acting
both ways, so delete the reversed ones if you regenerate there.

The wizard's wind is that of the main structure. Purlins, girts and cladding
also need the local pressures of the code (RNC-07 Art. 58, ASCE 7 chapter 30,
cpe,1 of EN 1991-1-4), which are larger near the edges; the envelope procedure
of ASCE 7 chapter 28, open buildings, the minimum wind load of ASCE 7 27.1.5
and the torsional load cases are not created either. For EN 1991-1-4 the
structural factor cs cd is 1 (a building under 15 m), and neither the 0.85
factor of 7.2.2 (3) nor friction (7.5) is applied.

# Earthquake
With **Create the earthquake load cases** (off until you tick it: the ground
acceleration, the soil and the reduction factor belong to your site and your
structure) the wizard adds one static load case per direction ticked under
**Earthquake along**: `EQ X`, across the ridge, on the frames, and `EQ Y`,
along the building, on the bracing.

The base shear is **V = c W**, and each direction has its own coefficient
**c**. **Seismic coefficient from** says where it is read:

- **Plateau of the spectrum (no period)** — the plateau of the design
  spectrum: the period of the building is not computed and not used, which is
  the simplification the codes allow for a low building and is on the safe side.
- **Spectrum at the period of each direction** — the design spectrum at the
  period of that direction. **Period along X** and **Period along Y** take the
  period you have (from a modal case, say); left at *Empirical*, the code's
  empirical period of the **System along X** or **Y** at the mean roof height
  (half way between the eaves and the ridge): Ta = Ct hn^x of ASCE 7-16
  Eq. 12.8-7 (NSCM too), T1 = Ct H^(3/4) of EN 1998-1 Expression (4.6). The
  system starts as a steel moment frame across (the portal frames) and as all
  other systems along (the bracing). ASCE 7 and NSCM cap the period at Cu Ta
  (Table 12.8-1, Tabla 8.2.1), and ASCE 7 needs **SD1** for the descending
  branch, Cs = SD1 / (T R / Ie) (Eq. 12.8-3). RNC-07 gives no empirical
  period: type the period of each direction (Art. 32 b, Ec. 13).

The summary on the page shows c of each direction and the clause it comes from.

- **RNC-07 Art. 32** — c = S (2.7 a0) / (Q' Ω), not less than S a0 (Ec. 3),
  times 1.5 for Group A. **a0** is the ground acceleration of Art. 24 (zone A
  0.1, B 0.2, C 0.3 g, or the map of Anexo C), **Soil** the type I to III of
  Art. 25 (the factor S depends on the zone too), **Reduction factor** the
  ductility Q of Art. 21, reduced by the **Regularity** of Art. 23 to Q', and
  Ω = 2.
- **NSCM Managua 8.2.1** — the plateau β A0 / Ro of its spectrum, with **a0**
  of Tabla 14.2 (Managua 0.36667 g), the **site class** A to D, the **risk
  category** I to IV and **Ro**, which cannot be below 1.
- **ASCE 7-16 12.8** — Cs = SDS / (R / Ie) (Eq. 12.8-2): **SDS**, **R** and
  the **importance factor Ie**.
- **EN 1998-1 4.3.3.2** — the lateral force method on the design spectrum of
  Expressions (3.13) to (3.16), the plateau Sd = 2.5 ag S / q (3.14) without a
  period, with λ = 1 (one storey) and β = 0.2:
  **a0** is the reference acceleration agR of the National Annex, the
  **importance class** I to IV gives γI (0.8, 1.0, 1.2, 1.4; ag = γI agR),
  **Soil** the ground type A to E with the soil factor S of the Type 1 spectrum
  (1.0, 1.2, 1.15, 1.35, 1.4) and the corner periods TB, TC, TD of Table 3.2
  (a region of low seismicity uses the Type 2 spectrum, which is not offered),
  and **Reduction factor** the behaviour factor q (1.5 for low dissipative
  steel).

Each direction has its own lateral system, so its own reduction factor: the
**Reduction factor along X** is that of the portal frames across the building,
the **Reduction factor along Y** that of the bracing along it (*Same as along
X* when you leave it at 0). The values the page starts with are not a
recommendation.

**Seismic weight W** — the self weight of the steel (as the dead case counts
it), the roof dead load, and the **roof live load in the seismic weight**:
10 kg/m² of horizontal projection by RNC-07 Art. 11 a (the reduced live load of
light roofs), 0.3 CV by NSCM 9.6 b (warehouses and storage: W = CM + 0.3 CV, so
3 kg/m² of that roof), none by ASCE 7-16 12.7.2 nor by EN 1998-1 3.2.4 (ψ2 = 0
on a roof). Wall cladding is not in the model: add its weight to the roof dead
load if it matters.

**Where the forces go** — each joint of the warehouse gets
Fi = c Wi hi ΣW / ΣWi hi, with Wi the weight gathered at the joint and hi its
height above the bases (RNC-07 Art. 32; ASCE 7 Eq. 12.8-12 with k = 1), as
nodal loads. So the roof takes almost all of it, and a joint half way up a wall
its smaller part.

In the combinations an earthquake case acts **both ways**. RNC-07 (Art. 32 f),
NSCM and EN 1998-1 (4.3.3.5.1) take each direction with 30 % of the other, in
every sign; the ASCE 7
combinations here take the two directions one at a time (12.5 asks for the
100 % + 30 % rule only in some seismic design categories: Define → Load
Combinations → Generate has the option). NSCM's vertical component
Ev = 0.2 a0 Fas CM (Ec. 7.8-4) goes into the dead load factor with the a0 and
the site class of this page. **Accidental torsion** is
not included, nor the vertical component, the redundancy factor ρ and the
overstrength combinations of ASCE 7. Check the drifts with the rules of the
code: the displacements of these cases are those of the reduced forces.

For a response spectrum or other buildings use Define → Seismic Loads
(Equivalent Lateral Force) and the response spectrum cases.

# Ash and snow
With **Create the ash or snow load cases** (off until you tick it) the wizard
adds what settles on the roof, as a load per area of **horizontal projection**
on the purlins. The **Rule** follows the design code and can be changed:

- **Volcanic ash** — RNC-07 Art. 14 and NSCM 7.3: one case, `ASH`, uniform over
  the roof. The load starts at 20 kg/m², the wet ash both codes recommend when
  there is no local record; it is mandatory in León, Chinandega, Carazo,
  Ometepe and Masaya and wherever ash can fall. NSCM has a load of its own for
  it in the combinations (CCV); RNC-07 has none, so there the ash goes with the
  live load (CV), "in addition to the live load" as Art. 14 says.
- **ASCE 7-16 chapter 7** — from the ground snow load **pg**:
  pf = 0.7 Ce Ct Is pg (Eq. 7.3-1) and ps = Cs pf, with the slope factor Cs of
  Fig. 7.4-1 (a **slippery roof** sheds snow from a lower slope) and, under
  15°, not less than the minimum of 7.3.4. `SNOW` is that balanced load. A
  gable roof between 1/2 on 12 and 7 on 12 also gets `SNOW +X` and `SNOW -X`
  (7.6.1), the drift on the side the wind blows to: 0.3 ps to windward, ps to
  leeward and a surcharge hd γ / √S over 8 hd √S / 3 from the ridge.
- **EN 1991-1-3** — s = μ Ce Ct sk (5.1) with the shape coefficients of Table
  5.2: `SNOW` with μ1 everywhere, and on a duopitch roof `SNOW +X` and
  `SNOW -X` (5.3.3), half the snow on one slope and all of it on the other, the
  one named.

Several naves stand under **one roof** (one ridge, or one slope, over the whole
width), so the roof has no valleys and the cases are those of that one roof.

**Ce**, **Ct** and **Is** are typed as numbers: the tool tips list the tables.
Untick **Also the unbalanced arrangements** to keep the balanced case only.
The summary on the page names the cases and the load on the roof.

In the combinations the snow cases are **alternatives**: a balanced and an
unbalanced case never enter the same one. A code without a snow load (RNC-07)
gets the balanced case only, as a live load.

Not included: the build-up against a parapet or a taller wall, the snow that
slides onto a lower roof, the ash that gathers in valleys and gutters (both
Nicaraguan codes ask you to estimate it), rain on snow, ponding, and the part
of the snow that ASCE 7-16 12.7.2 counts as seismic weight.

# Load combinations
The last page plans the warehouse as the other pages describe it and shows the
combinations of the code on the load cases it creates: one row per combination,
one column per case, the factor of that case in the cell (empty is 0). The
**Set** is the group whose envelope takes the combination.

- Change a factor: double-click the cell. A negative factor reverses the case.
- Untick a combination to leave it out, or double-click its name to rename it.
- **Add Combination** adds one after the selected row, in its set; give it its
  factors.
- **Restore the Code's Combinations** takes back every edit.

The page says when the combinations differ from the code's, and Finish waits
while a factor is not a number, two combinations share a name or a ticked one
has no factor. When an earlier page changes the load cases (another code, the
wind turned on) the table starts again from the code's combinations. An
envelope is made over the ticked combinations of each set, and with the braces
in tension only each one is analysed as a case of its own, as before. Without
**Generate the load combinations of the code** the page has nothing to show.

# Not included yet
Haunches, and trusses with a Warren web without
verticals. RNC-07 Art. 11 also asks
each purlin for 100 kg at mid-span: check the purlins for it separately.
