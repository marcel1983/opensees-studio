---
title: Edit → Extrude
group: Edit and tools
summary: Sweep joints into frames, or frame members into shells, along an offset.
see_also: edit.replicate, tools.draw_frame
order: 740
---

What the selection holds decides what is made:

- **Frame members selected** → **shells**. Each member sweeps a strip of
  `ShellMITC4` shells, one per step: a beam line extruded down by a storey height
  becomes a wall, a row of beams extruded sideways a slab strip. Choose the
  **plate section**.
- **Only joints selected** → **frames**. Each joint sweeps a line of members, one
  per step: the base joints extruded up by the storey height become a column
  stack. Choose the **frame section** (a fibre section gives force-based
  members).

# Values
- **dX, dY, dZ** — the offset of one step, in the project's length unit.
- **Number of steps** — how many times it is repeated.

A point of the sweep that falls on an existing joint **uses that joint**, so an
extrusion that reaches the model connects to it. The new members or shells
become the selection; Extrude is one undo step. Supports, loads and frame
options are not copied: assign them to the new objects.
