---
title: Assign → Frame → Property Modifiers
group: Assign — frame
summary: Multipliers on a member's section properties, e.g. 0.35 Ig for cracked beams.
see_also: assign.frame_releases
order: 1330
---

# Values
- **Area, Torsional constant, I22, I33** — multiply A, J, Iy and Iz of the
  member's elastic section (or the elastic interior of a BeamWithHinges). The
  run builds a derived elastic section for every distinct combination.
- **Shear areas 2 / 3** — multiply the section's shear areas As2 / As3, so they
  change a result only when the elastic section defines them (the member is then
  an `ElasticTimoshenkoBeam`, see Define → Section Library). On a section
  without shear areas the member is Euler-Bernoulli and they have no effect.
- **Mass** — scales an elastic beam-column's mass per length.
- **Weight** — scales the member's self weight.
- A fibre section has no property to scale: stiffness modifiers other than 1 on
  a fibre member stop the run with a message.
