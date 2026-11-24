---
title: Define → Storeys
group: Define
summary: Name the floor levels of a building and their elevations.
see_also: assign.diaphragm, mechanics.buildings
order: 2130
---

A storey is a floor level: a name and an elevation along the vertical axis, Z
(in 2D and in 3D). The storey table, the "every joint of storey N" diaphragm and the
drift ratios all read them.

# Values
- **Name**, **Elevation** — one row per floor. Everything below the lowest
  storey is the **base**, whose elevation is the lowest node of the model.
- **From Z grid lines** — one storey per Z line of the chosen coordinate system,
  the lowest line being the base (Story1, Story2... as ETABS names them). Rows
  already there keep their ids, so diaphragms that follow a storey keep it.

# Notes
- A storey's **height** is the distance to the storey (or base) below it: the
  inter-storey drift ratio divides by it.
- A joint belongs to a storey when it lies on its elevation, to a millionth of
  the model's height.
- A storey used by a diaphragm cannot be removed; delete the diaphragm first
  (Assign → Joint → Remove Constraints on its retained node).
