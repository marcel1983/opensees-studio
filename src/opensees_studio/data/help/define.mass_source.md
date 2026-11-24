---
title: Define → Mass Source
group: Define
summary: Turn self weight and load patterns into nodal mass (W / g).
see_also: assign.masses, mechanics.buildings
order: 2180
---

The mass source is SAP2000's and ETABS': instead of typing a mass at every
joint, the solver gets **W / g** of what you choose. Masses typed with Assign →
Joint → Masses always count on top.

# Values
- **Element self mass** — frames and shells whose section has a unit weight,
  lumped half on each end of a frame and by tributary area on a shell's corners.
- **Load patterns** — tick a pattern and give its factor (the usual D + 0.3 L
  is DEAD 1.0, LIVE 0.3). Only the **downward** part of its nodal, uniform,
  distributed (trapezoidal) and point loads counts, plus its floor panels and
  its self-weight multiplier; element loads go to the element's ends, a
  distributed load by its resultant. A node whose total comes out upward gets
  nothing.
- **Also on the vertical translation** — by default the mass goes on the
  lateral translations only, so the model has no vertical modes.
- **Lump at the retained node** — each rigid diaphragm's in-plane mass and its
  rotational inertia sum(m r²) move to the retained node, where the storey table
  and mass participation report them.

# Mechanics
Lumping is exact only when the retained node sits at the centre of that mass;
otherwise the rigid-body mass couples translation and rotation, which a lumped
mass cannot express, so such a diaphragm keeps its mass on the joints (the
constraint carries it exactly). The periods are the same either way. A restrained
DOF gets no mass: it never moves, and it would only dilute the mass ratios.

A pattern that carries self weight together with **Element self mass** counts
the self weight twice; the dialog warns about it.
