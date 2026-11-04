# ADR-0004: Steel design — AISC 360 members, stability, seismic and connections

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-04 |

---

## 1. Context

The application already checks steel frame members against AISC 360-16 with
LRFD and ASD: D2 yielding, E3/E4/E7 compression, F2/F3/F6 for I-shapes,
F7/F8/F9/F10 for HSS, tees, angles and channels, G2–G6 shear and the H1-1
interaction. The check envelopes load cases and combinations, samples 25
stations, derives `Cb` from the moment diagram and accepts K, Lb and shape
overrides.

That is a member *check*, not a complete steel design workflow. AISC 360 also
requires tension rupture and block shear, the F4/F5 flexural provisions for
noncompact and slender webs, torsion, Chapter C stability, Chapter J
connections and, for buildings, the seismic provisions of AISC 341 and the
prequalified connections of AISC 358. Sending a building to a permit office
needs all of those, not only member ratios.

The risk is trying to ship them at once: connection design alone needs new
model entities, geometry and validation, and AISC 341 is system-specific.

## 2. Decision

1. **Keep AISC 360 and the seismic provisions as separate layers.**
   - AISC 360-16 is the current code edition in `Project.design`; the engine is
     parameterised so AISC 360-22 can be added without changing equations.
   - AISC 341 (seismic systems, compactness, capacity design, protected zones)
     is a second layer that consumes AISC 360 results.
   - AISC 358 (prequalified moment connections) is part of the connection
     layer, not of the member check.
   - ASCE 7 supplies seismic combinations (including overstrength) and drift.

2. **Implement in phases, each one independently verifiable.**
   - **Phase 1 — Members:** complete D, E, F, G, H, serviceability and the
     section classification, with tests from the AISC *Design Examples*.
   - **Phase 2 — Stability:** Chapter C, Direct Analysis Method (notional
     loads, stiffness reduction, K = 1), Effective Length Method and
     first-order amplification.
   - **Phase 3 — Demands:** envelope each combination at the same station,
     include torsion and connection-face forces, and support capacity-limited
     seismic demands.
   - **Phase 4 — Seismic:** SDC and system selection, AISC 341 member and
     system checks, overstrength combinations, SMF and SCBF first.
   - **Phase 5 — Connections:** Chapter J, simple shear connections first,
     then AISC 358 moment connections and braced-frame gusset plates.
   - **Phase 6 — Workflow:** design groups, member selection, reports and
     schedules. Automatic sizing comes after the check is trusted.

3. **Keep the core headless.** The equations live in `core/design`; demand
   extraction stays in `services/steel_design.py`; Qt only presents settings
   and results. The imports follow the existing layer contracts.

4. **Every result is traceable.** A limit state reports the code edition, the
   equation, demand, capacity, ratio, load set and station, and any assumption
   (net area, unbraced length, Cb, K, seismic system). A ratio without its
   equation is not a design result.

5. **Validation is part of the feature.** Each limit state needs a unit test
   from an AISC example or a closed-form calculation, plus integration tests
   over OpenSees results. AISC 341 checks need AISC 341 examples; connection
   checks need AISC 358 examples. Commercial software is a cross-check, not an
   oracle.

## 3. First increment (this ADR)

The first implementation slice is deliberately narrow:

- D2-2 tension rupture with a user-supplied net area and shear-lag factor, in
  addition to D2-1 yielding;
- F4 for doubly symmetric I-shapes with noncompact webs;
- F5 for doubly symmetric I-shapes with slender webs;
- `Fu`, net area and shear lag in `DesignSettings` and the dialog;
- tests for every new equation and for the existing member paths.

D2-2 and F4/F5 close real gaps in the current check. Stability, connections and
AISC 341 remain separate phases so that the member engine stays reviewable.

## 4. Consequences

- The member check becomes more accurate for built-up and slender-web members
  and for members whose tension rupture governs.
- Users must supply connection information (net area and shear lag) before the
  software can claim D2-2; without it, the check still reports that rupture was
  not evaluated. It never silently assumes a net area.
- The design dialog and `.osmodel` gain optional fields; old projects load
  unchanged.
- AISC 341 and AISC 358 are not implied by an AISC 360 check. The report and
  help must say so.
- The software remains a checking aid: the engineer of record is responsible
  for the design, the code edition and the assumptions.

## 5. Verification

- AISC 360-16 *Design Examples* for D, E, F, G and H.
- Unit tests in `tests/unit/test_aisc360*.py` for each equation and for both
  LRFD and ASD.
- Integration tests in `tests/integration/test_steel_design_run.py` over real
  OpenSees results.
- GUI tests for the new fields and the existing report.
- The verification manual records the example, the expected value and the
  relative error.
