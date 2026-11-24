---
title: Assign → Joint → Springs
group: Assign — joints
summary: Elastic support springs to ground on the selected joints.
see_also: assign.support, assign.masses
order: 1150
---

A support spring ties a joint to the ground through a stiffness instead of a
fixed restraint: soil springs under a footing (Winkler), a flexible column base,
a bearing pad, or a lateral prop.

# Values
- One **k** per DOF of the model (a 2D frame: Ux, Uz, Ry), in force per length
  for a translation and moment per radian for a rotation, in the model's units.
  Zero means no spring. OK replaces the springs of every selected joint; all
  zero removes them.

# How it is analysed
- Each sprung joint gets a hidden ground node, fixed in every DOF, joined to it by
  a `zeroLength` element with one elastic material per sprung DOF, along the
  global axes.
- The spring force is reported as the joint's **reaction**, so the reactions
  still balance the loads. Springs also stiffen a modal analysis (a mass m on a
  spring k vibrates at √(k/m)).
- A DOF that is also restrained ignores its spring.
- The canvas draws a zigzag along each sprung translation (toward -X, -Y or -Z,
  ending on a hatched anchor) and a spiral around each sprung rotation, in the
  axis colours of the supports: X red, Y green, Z blue. A spring on a restrained
  DOF is not drawn. IFC export writes the stiffness into the support's boundary
  condition.
