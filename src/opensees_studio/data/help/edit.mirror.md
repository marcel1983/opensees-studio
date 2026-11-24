---
title: Edit → Mirror
group: Edit and tools
summary: Copy the selection reflected across a global plane (XY, YZ or XZ).
see_also: edit.replicate, edit.move
order: 730
---

Like Replicate, but the copy is reflected rather than translated: the way to
build a symmetric structure from half of it.

# Values
- **Plane** — the mirror plane. `YZ` flips X, `XZ` flips Y (the usual one for a
  plan symmetry in a Z-up model), `XY` flips Z.

Reflection reverses the winding of a face element, so a shell or quad that is
mirrored has its normal reversed relative to the original. For a plate that
matters only if a pressure or a one-sided property depends on it.
