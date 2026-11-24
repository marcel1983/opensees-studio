---
title: Assign → Frame → Material
group: Assign — frame
summary: Give the selected truss or zero-length elements a material.
see_also: define.material_library, assign.section
order: 1240
---

Trusses and zero-length elements point at **materials**, not sections: a truss
has an area and a uniaxial material; a zero-length element has one material per
DOF or a list of them.

- Assigning a material to a beam-column does nothing: its stiffness comes from
  its section (which in turn points at materials if it is a fibre section).
- The element's own parameters (the truss area, the zero-length DOF list) are
  set when the element is created or in the property dock.
