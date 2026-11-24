---
title: Analyze → Cases
group: Analyze
summary: Define the analyses: type, steps, solver options.
see_also: mechanics.static, mechanics.constraint_handlers, analyze.run, display.influence_line
order: 1490
---

A case is what to solve. Several cases coexist on one model — a gravity static
case, a modal case and a pushover, for instance — each with its own settings.

# The seven types
- **Static** — equilibrium under the patterns' loads, in N steps. See
  **Static analysis**.
- **Staged construction** — the structure grows group by group (Define →
  Groups). Each row of the stage table builds groups, removes groups (shoring,
  formwork) and applies load patterns, which then stay. An element in a group
  some stage builds does not exist before that stage; every other element is
  there from the start. New elements appear stress-free; a removed element's
  forces go back into the structure. New joints are built **at their design
  position** (a floor is built level, whatever the storeys below have
  shortened: their displacement is the movement since they were built) or
  **following the deformed structure** (the rigid continuation of the joint they
  grow from). A pattern's self weight weighs only the elements its stage builds,
  so give each stage its own weight pattern. The result has one step per stage:
  the state at the end of it. A load on an element that does not exist yet, a
  group removed before it is built, and members with end releases or rigid end
  zones in a staged group are refused before the run. Verified on a column built
  storey by storey (Verification Manual V-20); see `examples/staged_frame.osmodel`.
  Mark the case **time-dependent** for creep and shrinkage: its time is then the
  concrete age in days (starting at the case's start time), each stage applies
  its loads at once and holds them for its **duration**, in geometrically spaced
  time steps; the concrete must be a `TDConcreteMC10` material (Define →
  Concrete Creep & Shrinkage).
- **Modal** — eigenvalues and mode shapes; needs mass. See **Modal analysis**.
- **Pushover** — displacement-controlled monotonic push to a target. See
  **Pushover**.
- **Transient** — time integration of a ground motion or a time series. See
  **Transient analysis**.
- **Response spectrum** — modal maxima combined by SRSS or CQC. See
  **Response spectrum**.
- **Influence line** — a unit load walked along a chain of members, one linear
  solve per stop, with an optional vehicle. See **Display → Influence Line**.

# Options that apply to most types
- **Steps** and, for a transient, **dt**.
- **Numberer, system, constraints, algorithm, convergence test** — see Numberer,
  system and solver and Constraint handlers. The defaults are chosen to work;
  change them for size or for a case that struggles. Every option of OpenSeesPy
  3.8 that runs is offered:
  - systems BandGeneral, BandSPD, ProfileSPD, SparseGeneral, SparseSYM, UmfPack,
    FullGeneral;
  - algorithms Linear, Newton, NewtonLineSearch, ModifiedNewton, KrylovNewton,
    SecantNewton, RaphsonNewton, PeriodicNewton, BFGS, Broyden;
  - tests NormDispIncr, NormUnbalance, EnergyIncr, the Relative… ones (relative to
    the first iteration; on macOS, BFGS and Broyden do not meet the relative
    displacement and energy tests in OpenSees 3.8: pair them with NormDispIncr),
    NormDispAndUnbalance and NormDispOrUnbalance (the tolerance is used for both
    norms) and FixedNumIter (exactly the max iterations; do not pair it with
    SecantNewton, which divides by zero once converged);
  - static integrators LoadControl, DisplacementControl, ArcLength,
    MinUnbalDispNorm; transient Newmark (γ, β), HHT (α), GeneralizedAlpha (αM, αF),
    CentralDifference and TRBDF2 (no parameters). The parameter rows follow the
    integrator. Diagonal and ExplicitDifference are not offered: they need mass on
    every DOF.
- **Patterns** — which load patterns take part, and in what order.
- **Recorders** — what to save (node displacements, reactions, element forces).
  Asking for less is faster and produces smaller result files.
- **Name** — the label the case shows in the list, the Run progress, the results
  picker and the report. Rename it from the case list (double-click a row, or
  select it and press **Rename** / F2) or from the form's **Name** field. The
  name is a label, not a model input: renaming a case does not change its
  results or the load combinations that use it, so there is nothing to re-run.

# Chained workflows
A gravity preload followed by `loadConst -time 0.0` and then a pushover or a
transient is the standard way to start a non-linear case from the deformed
gravity state. The case list applies the patterns in the order given.
