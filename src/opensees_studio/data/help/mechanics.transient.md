---
title: Transient analysis: time steps, damping and convergence
group: Mechanics
summary: Integrating M·ü + C·u̇ + K·u = F(t) step by step.
see_also: mechanics.static, define.ground_motions, display.time_history
order: 80
---

A transient case integrates the equations of motion in time. The input is a
ground motion (or a time series), and the output is a history of any response
you asked the recorder for.

# Parameters
- **Time step (dt)** — must be small enough to follow the input and the modes
  that matter: a rule of thumb is dt ≤ T_min/10 for the highest mode carrying
  mass. The application checks the record's own step and says if they differ.
- **Number of steps** — usually the record length divided by dt.
- **Rayleigh damping** — C = α·M + β·K, given as a damping ratio ζ at two
  periods (or as α and β directly). For one target ratio at one period, β =
  2ζ/ω. The two periods must bracket the range that matters; damping applied to
  a range it was not fitted to is a common source of surprises.
- **Which stiffness β multiplies** — the case has three β fields, OpenSees'
  `rayleigh αM βK βKinit βKcomm`: the *current* tangent, the *initial*
  stiffness and the last *committed* stiffness. For a linear model they are the
  same. For a non-linear one prefer committed (what the OpenSees examples use) or
  initial: damping on the current tangent changes inside every Newton iteration
  once the model softens, and a run can stop converging for that reason alone.
- **Mode-1 damping ratio** — the runner computes β = 2ζ/ω₁ from the first mode
  after the preload and applies it to the committed stiffness, replacing the
  three β fields (α still applies). ω₁ comes from the dense solver at or below
  500 free DOF and from ARPACK above; with modal damping as well, it is the
  first of the N modes computed for it, so the case solves one eigen problem.
- **Modal damping** — one ratio ζ for each of the first N modes (OpenSees
  `modalDamping`), as SAP2000 and ETABS damp a modal history: every mode up to N
  gets exactly ζ, whatever its period, so no pair of periods has to be chosen.
  The runner computes the N modes after the preload (dense solver at or below
  500 free DOF, ARPACK above) and adds the modal damping to any Rayleigh damping;
  N is capped at the number of free DOF. Modes above N get no modal damping.
  Checked against the logarithmic decrement of a damped single-DOF free
  vibration.
- **Algorithm** — Newmark (average acceleration is the default and is
  unconditionally stable for linear models) or HHT with its α parameter.
- **Integrator and convergence** — for a non-linear model, the same Newton
  family and tolerance settings as a static case, per step.

# Mechanics
- Mass-proportional damping (α) damps the low modes; stiffness-proportional
  (β) damps the high ones. Fitting ζ at two periods sets both.
- **Stiffness-proportional damping with `-doRayleigh`** on the elements makes
  the damping forces depend on the element's own velocity, which is what makes
  an imposed support motion propagate correctly.
- A run that stops early did not converge; the log records the step it reached
  and the results keep what was computed. That is a result, not a crash: a
  non-converged step usually means the model is too coarse, the step is too
  large, or the structure has become unstable.
