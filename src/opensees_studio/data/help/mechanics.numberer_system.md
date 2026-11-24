---
title: Numberer, system and solver
group: Mechanics
summary: How the equations are ordered and solved, and when the choice matters.
see_also: analyze.cases, mechanics.static
order: 160
---

These are per-case settings in Analyze → Cases. The defaults are sane; the
choice matters on large models and on models that struggle to converge.

- **Numberer** — the order the unknowns are put in. `Plain` is the model order;
  `RCM` (reverse Cuthill-McKee) and `AMD` (approximate minimum degree) reorder
  to reduce bandwidth and fill-in. On a model with thousands of DOF, AMD with a
  sparse system is often several times faster.
- **System** — how the linear system is stored and solved: `BandGeneral` and
  `ProfileSPD` for small banded problems, `SparseGeneral`/`UmfPack` for large
  sparse ones. `FullGeneral` is the reference implementation (slow, exact).
- **Algorithm** — `Linear` solves once (linear problems only); `Newton` and
  `ModifiedNewton` iterate for non-linear ones; `KrylovNewton` and
  `NewtonLineSearch` help when Newton stalls.
- **Convergence test** — an energy or residual test with a tolerance and a
  maximum number of iterations. Too tight wastes iterations; too loose accepts a
  wrong answer.
- **Eigen solver** — not a free choice: the application picks a dense solver for
  small models and ARPACK above the threshold (see Modal analysis), and
  re-executes an ARPACK case in a fresh process so the answer is reproducible.
