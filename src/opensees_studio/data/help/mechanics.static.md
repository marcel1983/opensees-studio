---
title: Static analysis: what the parameters do
group: Mechanics
summary: Solving K·u = F, in steps, and what changes when it is not linear.
see_also: analyze.cases, analyze.run, mechanics.numberer_system
order: 50
---

A static case solves the equilibrium of the model under the loads of its
patterns. In one step, with a linear model, that is a single solve; in several
steps it is a load ramp, which is what a non-linear model needs.

# Parameters
- **Number of steps** — how many increments the pattern's total load is divided
  into. One step is right for a linear model; a model with material or geometric
  non-linearity needs enough steps for the solver to follow the path (10 to 100
  is typical).
- **Patterns** — which load patterns take part. Several patterns are applied
  together, which is how a gravity preload plus a lateral load is built.
- **Numberer / system** — how the equations are ordered and solved. The default
  is fine; a sparse direct system with an RCM or AMD numberer is faster on large
  models.
- **Tolerances and algorithm** — only used by the non-linear algorithms
  (Newton, ModifiedNewton, KrylovNewton) and the convergence test.
- **Preload cases** — a case imported from SAP2000 with an initial condition
  keeps it (the form lists it under *Kept as they are*). Those static cases run
  first, each with its own steps and algorithm, and are locked with
  `loadConst -time 0.0`; then this case applies its patterns. The results are
  the whole state, **preload included**, and the run log says so: do not add
  the preload case again in a combination. A preload cannot carry temperature
  loads (put them in the case itself), and the PyNite engine refuses a
  preloaded case.

# Mechanics
The solver assembles the stiffness matrix **K** and the load vector **F** and
solves for the displacements **u**. Element forces follow from the displacements,
not from the loads directly — which is why a redundant structure redistributes
its internal forces as members yield.

A gravity preload followed by `loadConst -time 0.0` (the *chained* workflow) keeps
the gravity state and starts the next pattern from a zero time, so the following
transient or pushover does not re-apply gravity.
