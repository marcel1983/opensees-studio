---
title: File → New 2D Frame (and the portal frame wizard)
group: File
summary: An empty 2D frame project, then the wizard that fills it, then its grid.
see_also: define.portal_frame, file.new, mechanics.static
order: 200
---

Creates a planar frame project (ndm = 2, ndf = 3: Ux, Uz, Ry per joint) and
immediately opens the **Portal Frame Wizard**. The frame is built on the XZ
plane (Z up), which is the only plane a 2D model has, and the wizard also writes the
**grid** it used, so you can keep drawing on the same lines. Cancelling the
wizard leaves the empty project.

# The wizard's values
- **Number of bays** and **bay width** — the columns sit at each bay line; the
total width is their product.
- **Eave height** — the height at which the roof starts, at the outer columns.
- **Roof** — one slope (mono-pitch), two slopes (gable) or flat; the **slope**
is a percentage. A gable rises to eave + slope × span/2 at the ridge; a
mono-pitch rises across the whole width.
- **Sections** — one for the columns, one for the rafters. If the project has
none, a default elastic section is created in the same undo step.
- **Column bases** — fixed (rotations restrained) or pinned (rotations free).
- **Plane and origin** — where the frame sits. Column tops follow the roof line,
so an interior column comes out as tall as the roof above it.
- **Restrain the out-of-plane DOF** — on for a frame analysed on its own (a
plane frame in a 3D model is a mechanism otherwise). Turn it off when you are
going to copy the frame and tie the copies together.

# Mechanics
Eave and ridge heights, the slope and the bay width are pure geometry: they
decide the member lengths, not the analysis. What changes the behaviour is the
**support condition** (a fixed base adds rotational restraint, which is what
makes a portal frame stiff) and the **sections** (bending stiffness).
