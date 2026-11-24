---
title: Design → Direct Analysis Method
group: Design
summary: AISC 360 Chapter C: every LRFD combination as one second-order analysis.
see_also: design.basis, design.steel_check, design.notional_loads
order: 360
---

A combination of separate results is a sum, and a second-order analysis cannot be
summed. So each **ASCE 7-16 LRFD combination** becomes **one static case** that
applies its patterns with their factors and is solved with:

- **P-Delta** in every frame member (Corotational members keep theirs). The
  member's own curvature (P-delta) is covered by **B1** in the member check.
- **Stiffness x0.8** on the elastic sections of the frames and the elastic
  materials of trusses (C2.3). τb is taken as 1.0 with the additional notional
  load **0.001 α Yi** in every combination (C2.3(c)), so no iteration is needed.
  Fibre sections and nonlinear materials are not reduced; the run log says which.
- **Notional loads 0.002 α Yi** (C2.2b) at every storey, Yi being the storey's
  factored gravity load *in that combination*: in the gravity-only combinations,
  in +X and -X (and +Y, -Y in 3D) as separate cases.

The model itself is never changed: the case applies all of it when it runs.

# Steps
1. Give each load case its **role** (dead, live, roof live, snow, rain, wind,
   earthquake). Names such as DEAD, LIVE, WX or EQ are recognised. Response
   spectrum cases cannot enter a second-order analysis; use an equivalent
   lateral force case.
2. **OK** replaces the cases made here before, sets the stability design to the
   Direct Analysis Method and makes these cases the load sets of the Steel Frame
   Check. Every lateral combination also gets a **first-order twin**.
3. Run them (**Analyze → Run All Cases**) and open this dialog again: the
   **Second-order check** tab lists **Δ2/Δ1** of every storey. Above **1.7** the
   notional loads must act in every combination (C2.2b(d)): tick the option and
   regenerate. Above 1.5 the Effective Length Method is not permitted.
4. **Design → Steel Frame Check** then checks every member with K = 1.
