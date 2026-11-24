---
title: Assign → Area → Area Springs
group: Assign — areas
summary: A spring bed under the selected shells (Winkler), per unit area.
see_also: assign.edge_springs, assign.line_springs, assign.springs
order: 1370
---

Rests the selected shells on springs to ground: a **stiffness per unit area**
(force / length³ — the modulus of subgrade reaction), along the shell normal or a
global axis. Each corner takes the stiffness times its tributary area
(`∫N_i dA`), so a shell of area A on a stiffness k is supported by k·A in all.
Choose whether OK replaces, adds to or deletes the springs of the selection.

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

SAP2000 text: `AREA SPRING ASSIGNMENTS` (simple springs normal to the Top or
Bottom face, both directions, compression or tension only) are read and written.
