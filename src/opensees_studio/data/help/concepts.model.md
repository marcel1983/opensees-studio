---
title: The model: nodes, elements, sections, materials, patterns
group: Getting started
summary: How the pieces fit, and which one a given property belongs to.
see_also: concepts.units, mechanics.static
order: 30
---

- **Node** — a point with coordinates, a restraint (which DOF are fixed), a
lumped mass and a name. Nodes are shared: two members meeting at a corner use
one node, which is why the duplicate checker exists.
- **Element** — what connects nodes. A frame member (`ElasticBeamColumn`,
`ForceBeamColumn`, `DispBeamColumn`, `BeamWithHinges`) points at a **section**;
a truss points at a **material** and an area; a zero-length element or a bearing
points at materials, one per DOF; a shell points at a **plate section**.
- **Section** — the geometry and stiffness of a cross-section (elastic
properties, or fibres). A section carries its own modulus for elastic sections.
- **Material** — a constitutive law (`Steel02`, `Concrete04`, `Elastic`, …) with
its parameters. Fibre sections point at materials; trusses and zero-length
elements too.
- **Load pattern** — a time series plus the loads applied with it (nodal forces
and moments, distributed element loads). The same pattern can be used by several
analysis cases.
- **Analysis case** — what to solve: static, modal, pushover, transient or
response spectrum, with the numberer, system and convergence options it needs.

A member with a missing section, or a load on a node that does not exist, is
refused when the case runs: the model is validated before anything is emitted.
