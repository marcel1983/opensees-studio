---
title: Modal analysis: periods, mode shapes and the solver choice
group: Mechanics
summary: Eigenvalues of K·φ = ω²·M·φ, and why the solver is chosen for you.
see_also: mechanics.response_spectrum, analyze.cases
order: 60
---

A modal case solves the generalised eigenvalue problem **K φ = ω² M φ**. What
comes out is, per mode, an eigenvalue ω² (and its period T = 2π/ω), a mode shape
and a participation factor.

# Parameters
- **Number of modes** — how many. One rule of thumb is enough modes to cover
  90 % of the mass in each direction; the results panel reports the
  participation, so it is visible rather than assumed.
- **Mass** — comes from the nodal masses (Assign → Joint → Masses) and from any
  element mass (a section's density, `rho`). A model with no mass has no modes.

# Mechanics
- The **period** is what a response spectrum needs: the pseudo-acceleration
  Sa(T) read at the mode's period is what scales the mode.
- Mode shapes are normalised to unit modal mass and their sign is arbitrary;
  the application normalises it deterministically (largest component positive)
  so two runs of the same model look the same.
- A **repeated eigenvalue** (a symmetric structure has pairs) returns any two
  orthogonal shapes of that subspace; because "any" depends on the starting
  vector, the application orthogonalises them before display or combination.
- The solver is chosen rather than guessed: a dense solver for small models
  (exact, no start vector, deterministic), ARPACK above a size threshold
  (faster). ARPACK keeps its random start vector, so only its first call in a
  process is reproducible — the application re-runs such a case in a fresh child
  process instead of risking a different answer.
