---
title: Constraint handlers: Plain, Lagrange, Penalty and Transformation
group: Mechanics
summary: How OpenSees enforces equalDOF, rigid links and diaphragms.
see_also: analyze.cases, mechanics.constraints, assign.diaphragm, assign.rigid_link
order: 170
---

These are per-case settings in Analyze → Cases (and in the transient and
pushover forms): the handler turns the model's multi-point constraints into
equations.

# The four handlers
- **Plain** — the default. It enforces only an `equalDOF` whose constraint
  matrix is the identity; it drops a rigid diaphragm or a `rigidLink` with a
  warning and can then solve a singular system without reporting failure.
- **Transformation** — the safe general choice. It transforms the constrained
  DOFs away and handles chains, rigid links and diaphragms. The application
  switches a case to Transformation when the model needs it, even if the case
  says Plain.
- **Lagrange** — adds the constraints as extra unknowns with Lagrange
  multipliers. The result is exact, but the system grows and can be indefinite;
  use it when Transformation cannot represent a constraint or when you need the
  constraint forces.
- **Penalty** — adds large penalty stiffness instead of extra unknowns. It keeps
  the system size and stays positive definite, but the penalty value trades
  accuracy against conditioning.

# What the application does
- A case left at **Plain** runs with **Transformation** when the model has a
  diaphragm, a `rigidLink` (including a frame end offset hung off its joint), or
  an imposed support displacement. The modal static solve follows the same rule.
- **Lagrange** and **Penalty** are passed to OpenSees unchanged; they remain
  available for models whose constraints are better handled that way.
- The model check refuses the chaining and repeated-constraint cases that
  Transformation cannot number correctly; see the diaphragm and rigid-link
  pages for the exact rules.
