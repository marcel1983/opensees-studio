# ADR-0005: Cold-formed steel design — AISI S100 by the Direct Strength Method

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-22 |

---

## 1. Context

Define → Section Library → Add Cold-Formed (AISI) already builds lipped and
plain channels, zees, hats and angles (`core/sections/cold_formed.py`) with
their gross properties by the linear method. The steel frame check
(`services/steel_design.py`, ADR-0004) only covers AISC v16 hot-rolled shapes:
a member made of a cold-formed section is not checked at all.

Cold-formed members fail by local and distortional buckling of their thin
flats long before they yield, so the AISC 360 equations do not apply. AISI
S100-16 (reaffirmed 2020) is the specification. It gives two routes to member
strength: the Effective Width Method (Appendix 1 and the element rules) and the
Direct Strength Method (DSM, Chapters E and F), which needs the elastic local
and distortional buckling loads of the whole section from a rational analysis
(Appendix 2).

## 2. Decision

1. **AISI S100-16 is a second specification inside the steel frame check, not
   a separate check.** A member whose section carries a `ColdFormedShape` is
   checked by AISI; every other steel member keeps AISC 360. Demands, load
   sets, physical members, unbraced lengths, `Cb`, `MemberCheck`,
   `LimitStateCheck`, the ratio dock, the 3D ratio view and the calculation
   memory are reused as they are.

2. **DSM first; the Effective Width Method later.** DSM treats every profile
   with the same equations, includes distortional buckling, and reports a
   result that can be traced from the buckling loads. Effective widths are a
   later alternative for comparison.

3. **The elastic buckling loads come from our own finite strip solver**
   (`core/design/fsm.py`): the semi-analytical finite strip method with simply
   supported ends, solved over a range of half-wavelengths (the signature
   curve). It is written from the published theory (Cheung 1976; Schafer and
   Ádány 2006). No code is taken from CUFSM, so the solver has no licence
   obligations and stays pure NumPy in `core`.

4. **Hand formulas check the solver** (`core/design/aisi_buckling.py`): the
   plate buckling stress and the element model of local buckling. They are a
   cross-check and a fallback, not the method.

5. **Material comes from the section.** A cold-formed section is linked to a
   material (A653 SS Gr. 33 or Gr. 50 sheet from the default library), which
   gives `Fy`, `Fu` and `E`. The AISC grade table (`steel_grades.py`) is not
   extended with sheet steels, because its `Ry` values are AISC 341's and the
   AISI seismic standard (S400) is out of scope.

6. **Same rules as ADR-0004.** `core` stays headless; every limit state reports
   its equation, demand, capacity and assumptions; LRFD and ASD; each equation
   enters with a test against a published example or a closed-form solution.

## 3. Phases

| Phase | Content | Gate |
|---|---|---|
| 1 | Missing section properties (principal axes, `j`, `ro`); finite strip solver and signature curve; hand-formula cross-check; this ADR | Plate buckling, global flexural-torsional and lateral-torsional buckling reproduced by the solver |
| 2 | `core/design/aisi_s100.py`: D tension, E2–E4 compression, F2–F4 flexure, G2 shear, LRFD and ASD; distortional buckling where the signature curve has no clear minimum; the finite strip model of the double-C box and back-to-back I, and the built-up compression rules of I1.2 (modified slenderness from the fastener spacing) | AISI Design Manual DSM examples within 1 % |
| 3 | Dispatch in `steel_frame_check`, H1.2 and H2 interaction, torsional unbraced length `Lt`/`Kt`, signature-curve panel, calculation memory, help, example model | Unit, GUI and integration suites; example pinned in the results snapshot |
| 4 | Web crippling (G5, H3), purlins by the R-factor method (I6.2), other built-up sections, inelastic reserve, Effective Width Method, local catalogue by gauge, screw connections (J4) | Per item |

**Built-up pairs.** Two equal channels joined toe to toe (box) or back to
back (I) are a section option from phase 1 (`ColdFormedShape.assembly`), so
they can be modelled and analysed now. Their design was planned with phases 2
and 3 and moved to phase 4 (section 6): the steel frame check reports a pair as
not checked.

## 4. Consequences

- Phase 1 changes no behaviour: it adds properties and the solver, and nothing
  calls them from the GUI yet.
- `ColdFormedProperties` gains `jx` and `jy` (defaulted fields) and the
  derived `x0`, `y0`, `ro`, `I1`, `I2` and `principal_angle`. The `.osmodel`
  format does not change.
- **Distortional buckling without a minimum.** A signature curve shows a
  distinct distortional minimum for many lipped sections in bending, but in
  compression it is often only a shoulder (the 9CS2.5x059 channel is one).
  The solver then reports no distortional load instead of guessing one.
  Phase 2 closes that gap with the closed-form flange model of Appendix 2
  (Schafer): it gives the half-wavelength `Lcrd`, and the distortional load is
  the **finite strip value at `Lcrd`** (0.271 `Py` for that channel, 0.27 in
  the DSM Design Guide). A minimum of the curve is local up to
  `sqrt(size × Lcrd)` and distortional beyond; when there is a distortional
  minimum it is used as it is.
- A signature curve of 90 half-wavelengths takes about a second for a
  20-node section; the check will compute it once per section and cache it.

## 5. Verification

- `tests/unit/test_fsm.py`: plate supported on both edges (k = 4), one edge
  free (k = 6(1 − ν)/π² + (b/a)²), plate in bending (k = 23.9), long lipped C in
  compression (flexural-torsional buckling) and in bending (lateral-torsional
  buckling) against the closed forms from the section's own properties, mesh
  convergence, and the element model as a lower bound of the local load.
- `tests/unit/test_cold_formed.py`: the 9CS2.5x059 properties (A, Ix, Iy, J,
  Cw, xo, j, ro) against the AISI Cold-Formed Steel Design Manual, the
  monosymmetry constant of a sharp channel in closed form, and the principal
  axes of a zee.

## 6. Status

**2026-11-24: phases 2 and 3, single profiles.** `core/design/aisi_s100.py`
and the dispatch in `steel_frame_check` cover the lipped channel, the plain
channel and the lipped zee: D2/D3, E2 (flexural, torsional and
flexural-torsional), E3.2, E4, F2 (major axis with `Cb`; minor axis with the
monosymmetry constant, the lower of the two senses of bending), F3.2, F4, G2.1,
H1.1, H1.2, H2 and the B1 of C1.2.1.1; the calculation memory and the help page
follow.

- **Gate.** The flexure example of the DSM Design Guide (CF06-1, 9CS2.5x059,
  Fy = 55 ksi: `Mcrl`/`My` 0.67, `Mcrd`/`My` 0.85, `Mnl` 94, `Mnd` 93, `φMn` 84,
  `Mn/Ω` 56 kip-in) is reproduced within 1 % on the strengths
  (`tests/unit/test_aisi_s100.py`). The closed forms of global buckling agree
  with the finite strips within 0.5 % (column, major-axis and minor-axis
  lateral-torsional buckling).
- **Source of the equations.** No copy of S100-16 was at hand: the equations,
  limits, factors and clause numbers were written from memory and then pinned
  by the example above and by the closed forms. They need a pass against the
  specification.
- **Simplifications.** Twisting takes the minor-axis unbraced length (no
  `Lt`/`Kt` yet). A zee takes half the channel's lateral-torsional stress
  (F2.1.3). The sign of a minor-axis moment is not tracked. Shear across the
  depth of the section treats each flange as a web.
- **Moved to phase 4.** The built-up pairs (the finite strip model of the box
  and the I, and I1.2), `Lt`/`Kt` overrides and the signature-curve panel. Hats
  and angles are reported as not checked.

**2026-11-24: sheeting and sag rods (from phase 4).**
`SteelMemberDesign.sheeted_flange` names the flange a sheeting is screwed to,
by the side of the local axis the member bends along. The check evaluates each
station with the sign of its own moment: with that flange in compression the
member is braced against lateral-torsional buckling (local and distortional
buckling stay); with it in tension the strength is `R Mnlo` of I6.2.1 where the
section is within the clause's limits (edge-stiffened flanges, depth, depth to
thickness, depth to flange width, flange width, flat width to thickness), and
never less than lateral-torsional buckling over `Lb`. The Warehouse Wizard
writes the flange from the outward normal of the roof or wall, and the sag rod
lines as design lengths.

- **Not applied.** I6.2.3 (compression of a member with one flange fastened to
  sheeting): the minor-axis length is what the sag rods give. The rotational
  restraint of the sheeting on distortional buckling. Continuous (lapped)
  purlins: the wizard's are simple spans. The span, panel, fastener and
  insulation limits of I6.2.1 are stated in the member note, not checked.
- **Source.** The R values and the limits of I6.2.1 were also written without
  the specification at hand.
- **Found on the examples.** The 50 mm flange of the wizard's default purlin
  is below the 2.125 in of I6.2.1, so under uplift it counts on its sag rods.
