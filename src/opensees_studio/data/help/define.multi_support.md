---
title: Define → Add Multi-Support Excitation
group: Define
summary: Drive the selected supports with a displacement history (MultipleSupport).
see_also: define.uniform_excitation, define.path_ts
order: 1060
---

Different supports moving differently — a long bridge, a pipe on two
structures — need the motion applied at the supports instead of as an inertial
load. Select the supports, then choose the direction, a **displacement** time
series and a factor. Each selected joint must be restrained in that direction:
the runner swaps its restraint for the imposed motion when the pattern runs.

Run it in a transient case. The velocity OpenSees also needs is derived from the
displacement series, which is what carries the motion into
stiffness-proportional damping of the elements.
