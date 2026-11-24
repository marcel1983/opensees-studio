---
title: Assign → Frame → Releases/Partial Fixity
group: Assign — frame
summary: Pin a member end about a local axis, or make it partially fixed.
see_also: assign.end_offsets, assign.insertion_point, assign.diaphragm
order: 1300
---

# Values
- **Torsion (T), M2, M3** at **end i** and **end j** — a released action carries
  no force at that end. M3 is the moment about local 3 (local z), the in-plane
  moment of a 2D frame; M2 the moment about local 2 (local y). A 2D frame
  releases M3 only.
- **Spring** — a partial-fixity stiffness (moment per radian) on a released
  action; 0 is a full release. The end then carries `k × relative rotation`.
- Torsion released at both ends leaves the member free to spin about its own
  axis and is refused unless one end has a spring.
- A joint where every member releases the same rotation and nothing restrains
  it is unstable: the run stops and names the joint and DOF.

# Mechanics
OpenSees has no release option on force- or displacement-based elements, and
the 3D elastic element's `-releasez/-releasey` gets the end moments of a
`-beamPoint` load wrong, so the member end is connected to a hidden node at the
joint instead: `equalDOF` ties the translations and every kept rotation, a
`zeroLength` element along the member's axes carries the springs. A member whose
local axes are skewed to the global axes and that keeps torsion while releasing
both moments gets a penalty spring 10^8 times its own rotational stiffness for
the torsion (an elastic member only; a fibre member is asked to release torsion
too). The hidden nodes' reactions are added to the joint's.

A release at an end that also has an end offset or an insertion point acts at
the face of the rigid zone, as in SAP2000: the hidden node hangs off the joint
with `rigidLink beam`, and such a model runs with the Transformation constraint
handler even if the case asks for Plain (Plain ignores a rigid link).

At a joint that a rigid diaphragm, an equalDOF or a rigid link constrains, a
hidden node tied by `equalDOF` would chain through that constraint, which
OpenSees solves wrong without an error; there the release is made inside the
element or with penalty springs instead (see Assign → Joint → Diaphragm).
