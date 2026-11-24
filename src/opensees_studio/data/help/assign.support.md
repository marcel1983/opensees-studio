---
title: Assign → Joint → Restraints
group: Assign — joints
summary: Which degrees of freedom are fixed at the selected nodes.
see_also: mechanics.constraints, assign.zero_length_section
order: 1140
---

A restraint removes a DOF from the unknowns: a fixed DOF carries a reaction
instead of a displacement.

# Values
- **Ux, Uy, Uz** — translations; **Rx, Ry, Rz** — rotations. A 2D model lives in
  the X-Z plane (Z up): in a 2D frame only Ux, Uz and Ry exist, in a 2D truss only
  Ux and Uz.
- **Presets** — pinned (translations fixed), fixed (everything), roller (one
  translation free), and so on. The check boxes are what is actually applied;
  in a 2D model the dialog shows only the plane's Ux, Uz and Ry.
- The assignment **replaces** the restraints of the selected nodes.

# One click: the Restraints bar
The **Restraints** toolbar (left side, also Assign → Joint → Quick Restraint)
applies a preset to the selected joints without the dialog: **Fixed** (every
translation and rotation), **Pinned** (the translations), **Roller** (the
vertical translation only) and **Free** (removes the support). Each click is one
undo step; the buttons are grey until a joint is selected.

# Symbols on the canvas
The shape says what kind of support it is; the colour says which axis it holds,
in the origin triad's colours: **X red, Y green, Z blue**. A rotation takes the
colour of the axis it turns about (Ry, the rotation of a 2D frame, is green).
- **2D models** draw one textbook symbol in the X-Z plane: a block on a hatched
  floor when Ux, Uz and Ry are fixed (green block, red sides, blue floor), a red
  triangle on a blue floor when pinned, a blue triangle on wheels for a roller
  (Uz only), a red one against a wall for Ux only, a green plate on wheels for a
  guide (Uz + Ry, or Ux + Ry against a wall) and a green square for Ry alone.
- **3D models** draw one solid for the usual patterns: a box when everything is
  fixed (each face in the colour of its axis), a pyramid when the translations
  are fixed (its X faces red, its Y faces green), a blue pyramid on balls for a
  vertical roller, and a pyramid on rollers when it slides along one axis only
  (the red rollers of Ux + Uz roll along Y). A blue square at the joint adds Rz.
- Any other pattern shows the 2D symbol in each elevation plane: X-Z from
  Ux/Uz/Ry and Y-Z from Uy/Uz/Rx, plus the blue square for Rz. The exact DOFs
  are in this dialog and in the joint's tooltip.

# Mechanics
- Every unrestrained rigid-body direction has to be held somewhere or the
  stiffness matrix is singular and the run fails with a solver error. That is
  what "the model is unstable" usually means.
- A fixed rotation is a moment connection; leaving it free makes the connection
  a pin. In a portal frame that difference decides whether the frame sways like a
  frame or leans like a mechanism.
- A **spring support** is modelled with a zero-length element between the node
  and a fully fixed node, not with a restraint.
