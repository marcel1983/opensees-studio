---
title: Design → Generate Notional Loads (DAM)
group: Design
summary: The AISC 360 C2-1 notional loads of the Direct Analysis Method.
see_also: design.direct_analysis, design.steel_check, define.mass_source, define.plain_pattern
order: 330
---

Creates a **Plain load pattern** with a lateral force at every storey:

- **Ni = 0.002 α Yi** (AISC 360 C2-1), where `Yi` is the storey gravity load and
  `α` is **1.0 in LRFD** and **1.6 in ASD** (the ASD analysis runs at 1.6 times
  the service combinations).
- The dialog picks the **design method** (which sets `α` and the factor), the
  direction **X**, **Y** or **both** (Y only in a 3D model), and lets you
  override the factor (C2.2b(c) permits adjusting the 0.002 coefficient when a
  different out-of-plumb tolerance is justified). The storey weight comes from
  the project's mass source; without one, it is the self weight plus the Dead
  and Live patterns, and typed masses are the last resort.
- Each storey's force is shared between its joints in proportion to their
  gravity weight, as C2.2b(b) requires.

The generated pattern is a normal load pattern: add it to the static cases
that represent the Direct Analysis Method, together with the reduced stiffness
`0.80 τb` on the frame property modifiers (C2.3). The command is one undo step
and the existing cases are not changed automatically.

C2.2b(d) permits applying the notional load only in gravity-only combinations
when the second-order/first-order drift ratio is at most 1.7 in every storey;
otherwise apply it in all combinations. This action does not run the analysis
and does not by itself make a case AISC 360 Chapter C compliant. It gives the
engineer the notional loads with the right code values and a traceable name.
For the whole method in one step (combinations solved to second order, reduced
stiffness and each combination's own notional loads) use Design → Direct
Analysis Method instead.
