---
title: Display → Shell Contours
group: Display
summary: A colour map of the shell faces: deformations, forces, moments and their principals.
see_also: display.deformed, display.force_diagram, mechanics.fiber_sections
order: 1640
---

Paints one quantity on the shell faces, with a colour bar, on the results of the
last static analysis.

# What can be shown
- **Deformation** — `|u|`, `ux`, `uy`, `uz`. These warp the mesh, so the colour
  and the shape say the same thing; the scale box multiplies the displacement
  (`0` paints the undeformed model).
- **Membrane** — `N11`, `N22`, `N12` and the principal values `N1`, `N2`
  (force per unit length).
- **Bending** — `M11`, `M22`, `M12` and `M1`, `M2` (moment per unit length).
- **Shear** — `V13`, `V23` and their magnitude `V`.

# Principal values and directions
`N1`/`N2` and `M1`/`M2` are the eigenvalues of the symmetric 2×2 membrane and
bending tensors — Mohr's circle, computed in `core.shell_results`. They do not
depend on the element's local axes, which is why they are the right thing to
read a design from: the frame of the mesh is arbitrary, the principal value is
not. Turning on **Draw principal directions** adds one segment per element
through its centroid, along the major principal axis, with a length proportional
to the spread between the two values — where the two are equal there is no
direction, and nothing is drawn.

# Limits worth knowing
- A field is painted on the **shell faces** (`ShellMITC4`, quads). Bars are not
  part of the map, and a model without shells cannot show one.
- Values are the **section stress resultants** OpenSees reports, averaged over
  the element's gauss points and onto the nodes for a continuous picture. They
  are per unit length, so a membrane force reads `N/m` (or `kip/in`) and a
  moment `N·m/m` (or `kip·in/in`).
- A **frame model has nothing to paint**: bars have no section resultants, so
  the contour needs at least one shell or quad. The command says so instead of
  showing an empty map.
