---
title: Define → Section Cuts
group: Define
summary: The resultant force through a part of the model, defined by a group.
see_also: define.groups, display.select_results
order: 2150
---

A section cut, as in SAP2000, sums the end forces of a group's **elements** at
the group's **joints**, with the moments taken about the centroid of those joints
or about a point you type. Put in the group the elements the cut passes through
and the joints on the side you want the force at:

- the columns of a storey and their base joints: the storey (or pier) shear,
  axial force and overturning moment;
- a wall's shells and the joints of one edge: the force through that edge.

# Values
- **Name** — unique. **Group** — from Define → Groups.
- **Centre X, Y, Z** — the point the moments are about; leave all three empty
  for the centroid of the cut joints.

# Results
A static case gets a **Section cuts** tab in the Results panel: the six global
components Fx, Fy, Fz, Mx, My, Mz (a 2D model: F1, F3, M2) at the final step.
The sign is that of the loads on the elements' side of the cut: a cantilever
column with a lateral load P and a weight W at its top, cut at its base, reports
+P and -W. Checked against hand statics in 2D and 3D.

# Notes
- Re-run the cases after adding or changing a cut. Pushover, transient and
  response spectrum cases, and load combinations, do not report cuts yet.
- A group a cut uses cannot be removed; delete the cut first.
- An element of the group that touches no joint of the group adds nothing; two
  group elements meeting at a free group joint cancel.
