---
title: Assign → Frame → Section
group: Assign — frame
summary: Give the selected frame members a section.
see_also: define.section_library, assign.material
order: 1230
---

Point the selected `ElasticBeamColumn`, `ForceBeamColumn`, `DispBeamColumn` or
`BeamWithHinges` elements at a section from the library.

- An **elastic** section carries E and the geometric properties; a **fibre**
  section carries materials and needs a non-linear case.
- A `BeamWithHinges` additionally needs a hinge section at each end, which the
  Assign → Frame → Hinge command sets.
- A plate section cannot be assigned to a frame member: it has a thickness, not
  a bending stiffness.
