---
title: Assign → Frame → Line Springs
group: Assign — frame
summary: A spring bed along the selected frames (beam on elastic foundation), per unit length.
see_also: assign.area_springs, assign.edge_springs, assign.springs
order: 1390
---

Rests the selected frame members on springs to ground: a **stiffness per unit
length** (force / length²) along the member's local 1, 2 or 3 or a global axis.
Each end takes half of stiffness × length — a grade beam on soil, a rail on its
bed, a pile's lateral support.

# Direction and side
Every spring acts along one **direction** and the **supporting medium** sits on
one **side** of it: on the *negative* side for soil under a spring along +Z, on
the *positive* side for soil above. For the shell normal, positive is the local 3
side (SAP2000's *Top* face). The side is what gives *compression* its meaning:
the structure moving into the medium.

# Behaviour
- **Linear** — resists both ways.
- **Compression only** — lets go when the structure lifts off (soil, a pad).
- **Tension only** — a tie that slackens when pushed.

The one-sided springs are nonlinear: a case they take part in with the *Linear*
algorithm is solved by **Newton** instead, every spring starting engaged, and the
log says how many let go and where. If the load lifts the structure off every
spring that holds it in a direction, there is no equilibrium and the case stops
with that explanation. Modal and spectrum cases take the springs as engaged.

# How the stiffness reaches the model
It is lumped at the nodes by tributary length or area (as SAP2000 does), so the
support is only as smooth as the mesh: mesh the shells and divide the frames
finely. Meshing carries the springs to the pieces (an edge spring to the edges
that lie on the original edge), Replicate copies them, deleting the element
deletes them, and the model check counts them as supports.

SAP2000 text: `FRAME SPRING ASSIGNMENTS` (simple springs along an object axis,
`Dir` 1, 2 or 3, negative for the opposite sense, with the medium on the side
opposite that sense) are read and written. A spring along a global axis is
written on the SAP2000 local axis it lies on; one on no local axis is reported.
