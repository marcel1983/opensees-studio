---
title: Analyze → Check Model
group: Analyze
summary: Find loose nodes, unconnected elements and static instability before running.
see_also: edit.check_duplicates, analyze.run, assign.support
order: 1510
---

OpenSees does not explain a model it cannot solve: a node nobody connects to, a
member that points at a deleted node or a frame missing one support all end as a
singular stiffness matrix, a warning the solver prints and moves past, and
displacements that are really the load vector. **Check Model** finds these
*before* the run, names the nodes and elements involved and says what to look at.
It never changes the model. **Run** performs the same check on its way in.

# What it finds
- **Loose nodes** — a node no element and no constraint touches. Free, it is an
  *error*; fully restrained, only a *warning* (it does nothing).
- **Broken members** — an element that refers to a node that no longer exists,
  lists the same node twice, or has zero length (two nodes at the same point). A
  zero-length element or bearing whose nodes are *apart* is a warning.
- **Separate parts** — a part with no support is a rigid body (*error*). Several
  supported parts are a *warning*; when two nodes of different parts sit at the
  same point the message names them, because that is nearly always a node that
  was never merged (see Edit → Check Model for Duplicates).
- **Mechanisms** — groups of nodes that can move *without deforming any element*:
  a square of bars with no diagonal, two bars in a line, a beam pinned at one end,
  a truss modelled with free rotations. Each is reported with the nodes and the
  DOF (Ux, Uy, Rz …) that are free to move, and how many independent motions there
  are.

# What each motion is, and what to do
Every independent motion is described on its own (up to six), and named:

- **Slides as a rigid body** — the whole structure, or a group of joints, moves
  along an axis without deforming: a support direction is missing, or the group
  hangs on the rest through hinges or bars in line.
- **Turns as a rigid body** — about an axis near a named joint: the supports hold
  only a point or a line, or a group is joined by hinges on one line.
- **Rotates freely** — a joint turns while nothing around it moves: only bars
  reach it, every member end there is released, or a member spins about its own
  axis between ball joints (restrain its torsion at one end).
- **Joint moves alone** — the members that reach it line up with the motion.
- **Sways** — joints move sideways at their level while the members turn: the
  frame has no lateral stiffness in that direction (add bracing, fix the bases or
  make the joints rigid).

Pick a mechanism row and press **Show the motion**: the window closes (before a
run, the run is not started) and the *Mechanism* panel animates each motion on
the model, with the joints and elements involved selected and the advice in the
status bar. **Back to model** ends it.

# How stability is decided
Each element is replaced by its independent deformation modes with unit stiffness
(a bar has one, a 3D frame six, a shell eighteen) and the stiffness matrix is
assembled over the DOF that are not restrained. A zero eigenvalue is a mechanism.
Because nothing about E, A or I enters, the answer does not depend on units or on
how stiff one member is next to another, and it does not run OpenSees.

# What it cannot see
It is a **linear, small-displacement** test of the *connectivity*:

- A structure that is stable only through its deformation (a cable) or through a
  gap, a slider or a hinge that locks, is outside it.
- Geometry that is *almost* degenerate (bars a hair out of line) passes; the
  solver will then give large displacements instead of failing.
- A model with more than 3000 free DOF in one connected part is skipped with an
  information line (set `OPENSEES_STUDIO_STABILITY_MAX_DOF` to raise the limit).

# Run anyway
If the check finds errors, Run stops at the list and offers **Run anyway**. A
modal analysis of a free-floating structure is a legitimate reason to; the
default button is Cancel. Warnings do not interrupt: they are written to the
console.
