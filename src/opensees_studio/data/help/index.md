---
title: OpenSees Studio — how to use it
group: Getting started
summary: The workflow: define, assign, analyse, look at the results.
see_also: start.menu_map, annex.index, concepts.units, concepts.model
order: 10
---

# The workflow
1. **Define** the model: grids and nodes, then members (draw tools, the portal
frame wizard, or File → Import for a DXF drawing), then materials and sections.
2. **Assign** the properties: restraints and masses on joints, sections,
materials, geometric transformations and beam integration rules on frame
elements, loads in a load pattern.
3. **Analyze**: Analyze → Check Model Stability finds mechanisms before
anything is solved; then create one or more cases (Analyze → Cases) and run them
(Analyze → Run). The solve happens in a separate process, so a crash in the
solver cannot take the interface with it.
4. **Display** the results: deformed shape, mode shapes, force diagrams, time
histories, hysteresis, pushover curves and response spectra.

# Axes
**Z is the elevation axis of every model.** A 3D model uses X, Y and Z; a 2D
model lives in the **X-Z plane** (every node at y = 0, Z up), so its joints move
in Ux and Uz and turn in Ry, and gravity acts along -Z in both. OpenSees itself
solves a 2D model in its own x-y plane; the application translates on the way
in and out, so you never see that plane. A 2D project saved by an earlier build
(X-Y plane, Y up) is turned into the X-Z plane when it is opened, loads and
supports included, and is saved that way.

# Where things are
- The **3D viewport** is the model; clicking selects, dragging orbits.
- **Hovering** a joint or a member shows what it is without selecting it: a
  joint's coordinates, restraint, mass, members and nodal loads; a member's
  joints, length, section or material and its loads in each pattern (a bearing
  shows its stiffness and strength instead).
- Everything is a command on an undo stack: Ctrl+Z undoes one model edit.
- The **Properties** panel follows the selection; with several joints or elements
  selected it edits what they share in one step.
- A **greyed-out** command waits for something: most Assign commands for a
  selection, the Display commands for a result. Its tooltip, and the status bar
  while the pointer is on it, say what (*Select one or more elements first.*).
- The **status bar** shows the model coordinates under the pointer (X, Y, Z,
  or X, Z in a 2D model, in the project's length unit) and what they come from:
  the **grid** intersection or member snap (**midpoint**, **perpendicular**,
  **on member**) a click would use while a draw tool is armed, or the point on
  the working **plane**. Seen edge-on, the plane has no point and the readout
  is empty.
- Every dialog that takes numbers has a help page: **press F1** while the menu
or the dialog is open.
- The **Console** dock keeps a log of what the application did, including the
commands it emitted to OpenSees.

# What is not here
Nothing is unit-aware behind your back: see **Units and the solver**. Nothing is
solved until you ask: editing the model never starts an analysis.

# Finding your way
- **Where is each command?** — the menu map lists every menu entry with one line.
- **I know the OpenSees command, where is it?** — the annex lists every command of
the OpenSeesPy manual and where it lives (a form, automatic, or a custom block).
