---
title: Buildings: storeys, diaphragms and the storey table
group: Mechanics
summary: Storey displacement, drift ratio, storey shear and base shear.
see_also: define.storeys, assign.diaphragm, define.mass_source, mechanics.response_spectrum
order: 2220
---

With storeys defined, the Results panel shows a **Storeys** tab (exported to CSV
at full precision like every table): top storey first, the base last.

# What each column is
- **U** — the storey's lateral displacement: the retained node of its diaphragm,
  or the mean of its joints when it has none.
- **Drift** — (U of the storey - U of the level below) / storey height.
- **Shear** — static case: the force the members cut just above the level below
  carry, from their global end forces. Base row: minus the sum of the lateral
  reactions, the base shear.
- **Response spectrum** — each mode's displacement, drift and storey shear (its
  inertia forces w² m u above the cut) is combined by the case's SRSS or CQC
  rule. A peak drift is not the difference of two peak displacements.
- **Modal** — the storey values of each mode shape, as OpenSees normalises it.
- **Pushover** — the last step's displacements and drifts.

# Building a building
Define → Storeys (from the Z grid lines), Assign → Joint → Diaphragm on each
storey with a new node at the centre of mass, Define → Mass Source, then a
modal and a response spectrum case. The example
`building_3storey_diaphragm.osmodel` is all of this, checked against a
hand-built OpenSeesPy model.
