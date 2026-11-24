---
title: Constraints: equalDOF and imposed support motion
group: Mechanics
summary: Tying degrees of freedom together, and driving supports with a record.
see_also: assign.equal_dof, assign.support, assign.diaphragm, mechanics.constraint_handlers
order: 150
---

# equalDOF
`equalDOF` makes a node's chosen DOF follow another node's. Uses: a rigid floor
in a 3D model (tie every node of a level to a master node in the horizontal
DOF), a hinge modelled as two coincident nodes, or a rigid link between two
points. The DOF are given as numbers, 1-based, in the order the case uses them.

Two coincident nodes tied by `equalDOF` are a **deliberate** coincidence: Edit →
Check Model for Duplicates lists them and does not merge them.

# Imposed support motion
A multiple-support case drives chosen supports with a displacement record. The
nodes must be **restrained** in the driven DOF: in the static and modal cases
they behave as ordinary supports, and the runner swaps the fix for the imposed
motion when the pattern is emitted, so the ground is at rest until the transient
starts.

The velocity series is derived from the displacement by central differences
rather than left to OpenSees. That matters when elements use `-doRayleigh`:
the damping force depends on the element's velocity, and an imposed motion
without a matching velocity loses part of the input.
