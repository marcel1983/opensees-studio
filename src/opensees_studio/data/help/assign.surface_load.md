---
title: Assign → Area → Surface Load on Shells
group: Assign — areas
summary: A pressure on the selected shells, uniform or by joint pattern, as consistent nodal forces.
see_also: define.joint_patterns, assign.joint_pattern, assign.floor_load, define.create_shell
order: 1360
---

Puts a load per area on every selected shell (`ShellMITC4`), in the load
pattern you pick. Beams and other elements in the selection are skipped. A shell
that is meshed later passes the load to every piece, and Edit → Replicate copies
it with the shell. The load is drawn on the shell as arrows as long as the
pressure under them.

# Distribution
- **Uniform (by element)** — the same pressure everywhere. Each corner takes the
  value times the integral of its shape function, so the four add up to value ×
  area also on a warped quad.
- **By joint pattern** — the pressure varies over the shell: at each corner it is
  the **multiplier** times the pattern's value at that node (Define → Joint
  Patterns), and in between it follows the shell's bilinear shape functions.
  Each corner takes `Σ ∫N_i N_j dA · p_j`, so the resultant and its point of
  application are exact for a linearly varying pressure — a hydrostatic load on a
  wall puts its resultant at a third of the depth. A node without a value in the
  pattern counts as zero.

# Values
- **Value / Multiplier** — force per area (uniform), or the factor on the
  pattern's values. For a pattern made with *Z at zero pressure and weight per
  unit volume* the values already are a pressure: use a multiplier of 1.
- **Direction** — **Global Z** (a floor's weight is a negative value), **Global
  X / Y**, or the **shell normal** (local 3: the right-hand turn of its nodes
  1-2-3-4, so a pressure on a wall, a tank or a sloped roof). A pressure that
  should push *outward* from a tank needs the shells' normals to point outward:
  check them with **View → Show Extruded Sections**, which draws each section in
  its local axes.
