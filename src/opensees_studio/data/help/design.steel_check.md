---
title: Design → Steel Frame Check (AISC 360-16)
group: Design
summary: Demand/capacity ratios of steel members over the results of this session.
see_also: design.steel_ratios, design.drift_check, design.connections, design.gussets, design.column_splices, design.chapter_j, define.load_combinations
order: 490
---

Checks every frame member whose section is an AISC shape of a covered family
against ANSI/AISC 360-16, by LRFD or ASD: **W, M, S, HP** (I-shapes), **C, MC**
(channels), **WT, MT, ST** (tees), **L with equal legs**, **rectangular and
square HSS**, **round HSS** and **pipes**. The section's **name** says which shape it is
(sections from Define → Section Library are named that way); type another shape
in the overrides to check a member with it.

# What is checked
- **Tension** D2-1 yielding of the gross section and, when you give a net area,
  D2-2 rupture of the effective net section `Ae = U An`.
- **Compression** E3 flexural buckling about both axes, E4 torsional buckling,
  and the E7 effective area when the flange or the web is slender.
- **Major-axis flexure** F2 yielding and lateral-torsional buckling (with Lp, Lr
  and Cb) and F3 flange local buckling for a compact web; F4 for a noncompact
  web; F5 for a slender web.
- **Minor-axis flexure** F6, **shear** G2.1 along the web and G6 along the flanges.
- **Interaction** H1-1a / H1-1b of the axial force and both moments.

The other families use their own sections of the Specification:
- **Channels**: E4 flexural-torsional buckling about the axis of symmetry, F2
  with c from F2-8b, F6, G2.1(b) and G6 with the full flange width.
- **Tees**: E4 flexural-torsional buckling, the stem as an unstiffened element
  (E7), F9 yielding, lateral-torsional buckling, flange and stem local buckling.
  The sign of the moment is not tracked, so the strength is the smaller of the
  stem in tension and the stem in compression.
- **Equal-leg angles**: E3 about the minor principal axis z, E4, F10 about the
  geometric axes without lateral-torsional restraint (0.8 My, toe in
  compression), G3. Unequal-leg angles are not designed (their flexure is about
  the principal axes).
- **Rectangular HSS**: E7 walls, F7 flange and web local buckling (the effective
  section modulus of F7-3 for a slender flange) and lateral-torsional buckling
  of a deep tube, G4. **Round HSS and pipes**: E7-6, F8, G5 with Lv half the
  member length.

HSS walls use the design thickness 0.93 tnom. The default Fy is 50 ksi and Fu
65 ksi: set them for the material (A500 Grade C round HSS 46 ksi, A53 pipe 35
ksi). Torsion is not checked. The base member check does not by itself satisfy
the seismic provisions of AISC 341 or the connection provisions of Chapter J:
the **Seismic system** field adds the AISC 341 checks described below, and the
connection checks live in their own dialogs.

The clear web height is taken as `d - 2 tf` (the table has no `k`), which is
slightly conservative.

# Cold-formed members (AISI S100-16)
A member whose section comes from Section Library → Add Cold-Formed (AISI) is
checked by **AISI S100-16** with the **Direct Strength Method**, LRFD or ASD, in
place of AISC 360: a **lipped channel**, a **plain channel** or a **lipped zee**.
Hats, angles and the box and back-to-back pairs are reported as not checked. Fy
and Fu are those of the **section's material** (the A653 sheet steels of the
default materials carry them), unless the member has a grade of its own; a
material without Fy takes the dialog's values, and the member note says so.

- **Elastic buckling.** The local and distortional buckling loads (Pcrl, Pcrd,
  Mcrl, Mcrd) come from the finite strip signature curve of the section
  (Appendix 2 allows a rational analysis). When the curve has no distortional
  minimum, its value at the half-wavelength Lcrd of the closed-form flange
  model is taken, and the member note says so.
- **Tension** D2 yielding and, with a net area, D3 rupture.
- **Compression** E2 global buckling (flexural, torsional or flexural-torsional,
  with the section's own xo, ro, J and Cw), E3.2 local buckling interacting with
  it and E4 distortional buckling. Twisting takes the minor-axis unbraced length.
- **Flexure** F2 lateral-torsional buckling with Cb (a zee as held to bend about
  the axis perpendicular to its web), F3.2 local and F4 distortional buckling,
  about both axes. The sign of a minor-axis moment is not tracked: the strength
  is the lower of the flange tips and the web in compression.
- **Shear** G2.1 of a web without stiffeners (kv = 5.34).
- **Interaction** H1.2 `P/Pa + Mx/Max + My/May`, H1.1 with tension, and H2
  bending with shear, `sqrt((M/Mao)² + (V/Va)²)`.
- **P-δ (B1)** follows C1.2.1.1, with `Pe1` on `0.90 τb EI`.

The factors are φ = 0.90 / Ω = 1.67 in tension and flexure, 0.85 / 1.80 in
compression, 0.95 / 1.60 in shear and 0.75 / 2.00 in rupture. They hold within
the limits of **B4.1** (Table B4.1-1, Direct Strength Method): flat width to
thickness of the web up to 300, of an edge-stiffened flange up to 160 and of a
lip or a plain channel's flange up to 60, inside bend radius up to 20 times the
thickness, lip up to 0.7 of the flange width (out to out) and Fy up to 95 ksi
(655 MPa). A member outside them takes φ = 0.80 / Ω = 2.00 in compression,
flexure and shear (A1.2 (c), as B4.2 (a) allows), and its note says which
limit it misses; tension keeps its factors. The equations, factors and limits
were checked against the text of S100-16 (reaffirmed 2020, with Supplement 2).

**Sheeting.** A purlin or girt with a sheeting screwed to one flange gets
**Sheeting on the flange** in the member overrides: the + or the - side of the
local axis the member bends along about its major axis (local z in a 3D model;
View → Show Local Axes draws it, z in blue). Where the moment puts that flange in
compression (gravity on a purlin, pressure on a girt) the member is braced
against lateral-torsional buckling along its length. Where it puts it in
tension (uplift, suction) the free flange is the one in compression: the
strength is `R Mno` of **I6.2.1** (R = 0.70, 0.65, or 0.40 for a channel and
0.50 for a zee, by depth, simple span) when the section is within the limits of
that clause, and never less than lateral-torsional buckling over Lb; outside
them it is lateral-torsional buckling over Lb, and the member note says which
limit is not met. With the material's Fu, Fu/Fy must also be at least 1.08.
The span (33 ft), the panels, their fasteners and the laps of I6.2.1 are not
checked, and R is taken without insulation: with a glass fibre blanket of
thickness ti on a simple span it is R times `1 - 0.01 ti` (ti in inches). Sheeting does not hold a member under
**axial compression** here (I6.2.3 is not applied): the minor-axis length is
what the sag rods or the model give. Without the setting, a sheeting is not a
brace. The Warehouse Wizard sets the flange and the sag rod lengths of its
purlins and girts, and gives each one its own span as the major-axis length.

**Not checked**: web crippling (G5, H3), holes, the inelastic reserve, and the
seismic provisions (the Seismic system field does not act on a cold-formed
member).

# Where the demands come from
The dialog uses the results of the cases already **run in this session**; it runs
nothing. Tick the load sets to envelope (by default every combination, or every
static case when there is none). A combination is expanded into sums of cases:
Linear Add adds its terms, Envelope keeps each term, and a response spectrum
case enters as plus and minus its peak. Absolute Add and SRSS combinations have
no signed demands and are skipped with a note.

Each member is read at 25 stations along its length, span loads included. Every
station is checked with its own axial force, moments and shears, so the interaction
uses forces that act at the same place; the governing station is reported. Cb comes
from the major-axis moment diagram (F1-1) of the whole laterally unbraced
segment unless you set it. **Set Cb = 1.0 for a cantilever**: F1-1 assumes both
ends braced.

# Members and unbraced lengths
The check works on **physical members**, not analysis elements: collinear
elements of one section, end to end, are one member (Design → Member
Classification lists them). Lx and Ly run between the joints that hold the
member along each of its local axes, and Lb is the minor-axis one; see that page
for what counts as a brace. A beam meshed into four elements is therefore
checked with its whole unbraced length, not a quarter of it.

# The values the dialog asks for
- **Method** LRFD (φ) or ASD (Ω); **Fy** and **Fu** (50 and 65 ksi by default,
  in the project's stress unit); **ratio limit** above which a member is
  reported **NG**.
- **Overrides for the selected members**: the AISC shape, K about each axis, the
  unbraced length of the compression flange Lb (0 = between the lateral bracing
  points), Cb (0 = from the diagram), the net area An (0 = D2-2 rupture
  unchecked) and the shear-lag factor U in `Ae = U An`. The buckling lengths are
  the unbraced lengths times K. **Sheeting on the flange** is for cold-formed
  members (see below); **Unchanged** leaves each member's as it is. Apply keeps
  what the dialog does not show: a member's role, its grade and the major- and
  minor-axis lengths a wizard wrote.
- **Amplify P-δ (B1)**: multiplies the moments of members in compression by
  `B1 = 1 / (1 - α Pr / Pe1) >= 1` (AISC 360-16 C2.1b; A-8-3 in the 2022
  edition) with the conservative `Cm = 1.0` and `Pe1` on `0.8 τb EI` (C2.3).
  Use it when the analysis includes P-Δ but not the member's own curvature
  (P-δ); leave it off for a full second-order analysis, which already captures
  both. The member note shows the two B1 values.
- **Seismic system** (AISC 341-22): `none` leaves the AISC 360 check alone. With
  SMF or IMF the webs of I-shapes and channels use case 11; with SCBF or OCBF
  they use case 13; braces use Table D1.1a. Members are classified by their
  direction (column within 20% of vertical, beam within 20% of horizontal,
  otherwise a brace). The **Ry** field (1.1 default) gives the expected yield
  stress `Ry Fy` of the limits and of `Ca = Pr/(αs Ry Fy Ag)`, with `αs` 1.0
  LRFD / 1.5 ASD. With **SMF**, each beam-to-column joint of a 2D frame is
  also checked for E3.4a: the report shows `ΣM*pc/ΣM*be`, which must be greater
  than 1.0, with `Pr` and the beam shear from each load set and
  `Mpr = Cpr Ry Fy Zb`. The E3.4a exception for light top-story columns is not
  applied (conservative). The same joints get the **panel-zone** check of
  AISC 360-22 J10.6 (J10-11/J10-12, the inelastic case AISC 341 requires):
  `Vr = Sum Mf/(db - tbf) - Vc`, with the beam face moments reduced by the
  shear over `dc/2` (or `Sh` for an RBS), and
  `φRn = 0.90·0.60Fy dc tw (1 + 3bcf tcf²/(db dc tw))` adjusted for column
  axial force. The joint table also reports the **continuity-plate** condition
  of E3.6f (`tcf` against `tlim = 0.6 sqrt(bbf)`). With **SCBF**, diagonal
  braces also check `Lc/r <= 200` (F2.5b) and `Ae >= Ag` (F2.5b(c)); the notes
  give the expected brace strength `Ry Fy Ag` for the connections.
  The check also runs the **F2.3 capacity design** for columns and beams: when
  a load set contains a case named as an earthquake (`E`, `EQ`, `EX`, ...), it
  computes each brace's expected strength (tension `Ry Fy Ag`, compression the
  lesser of that and `(1/0.877) Fne Ag`), takes the largest
  `expected / analysis` ratio and scales the seismic terms of the load set by
  it; gravity terms are not scaled. The factor is never below 1.0 and is
  conservative with respect to both F2.3 analyses: every brace reaches at
  least its expected strength, and the compression brace is checked at its
  expected strength (more severe than the 0.3 post-buckling value). Braces
  with no seismic force are left out of the factor and listed in the note. The
  report and the memory show the governing brace, its state, the analysis and
  expected forces and the factor; the capacity checks appear in the member
  ratios with the `SCBF capacity` prefix. The check does not identify which
  members belong to the braced frame: it applies the factor to every column
  and beam of the model, which is conservative for members outside it. Each
  joint where a brace ends and at least one beam and one column frame in also
  reports the **F2.6b** required moment: the lesser of `1.1 Ry Mp` of the beam
  and `1.1 Σ Ry Fy Z` of the columns, divided by `αs`. When an RBS connection
  is modelled at the joint its `φd Mpe` gives the ratio; otherwise the joint
  is reported as a simple connection to verify (0.025 rad rotation, B3.4a).
  The connection design of Chapter J and AISC 358 is not implied.
  With **OCBF**, diagonal braces check `Lc/r <= 4 sqrt(E/Fy)` (F1.5b); the
  member notes state that the limit is for V and inverted-V configurations
  and that the check applies it to every OCBF brace (conservative for other
  layouts). The check also reports whether the **O0 overstrength
  combinations** are among the selected load sets (F1.5c): when they are, the
  beam and connection ratios envelope them; when they are not, the note says
  the beam is not checked for F1.5c. Beams with a brace framing in away from
  a beam-column connection are flagged with the F1.4a continuity and lateral
  bracing requirement. The gusset notes state that the connection demands
  are the F1.6a exception caps (`Ry Fy Ag/alpha_s` tension and expected
  compression/`alpha_s`) and that the overstrength seismic load may govern.
  The check does not create the overstrength combinations and does not
  verify the beam continuity or the lateral brace of F1.4a. K-braced frames
  are not permitted (F1.4b) and the multi-tiered OCBF rules of F1.4c are not
  checked; the braces use the moderately ductile D1.1 limits of F1.5a.

Results: one row per member with its governing ratio, the check and equation
that govern and the load set that produced them; **Select failing members**
closes the dialog with them selected, and **Show ratios on the model** closes it
and paints every member by its ratio (Design → Display Steel Ratios on Model).
The settings are saved with the project, and File → Export → Report and File →
Export → Calculation Memory print the check when they are.
