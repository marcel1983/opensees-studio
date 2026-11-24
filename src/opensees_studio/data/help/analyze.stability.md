---
title: Analyze → Check Model Stability
group: Analyze
summary: Find the mechanisms of the model before running anything.
see_also: analyze.run, assign.support
order: 1500
---

Builds the model exactly as an analysis would, captures its initial stiffness
matrix once and looks for **mechanisms**: motions of the free joints that no
member, spring or support resists. A clearly stable model has none; a model
with a mechanism cannot be solved, or solves into nonsense.

The check runs in the same child process as an analysis, so a model OpenSees
cannot even build does not take the window with it.

# What it reports
- **Free DOFs that no element stiffens** — a joint DOF that nothing connects
  to: a rotation of a truss joint in a frame model, a joint whose every member
  releases the same moment, a node on its own.
- **Mechanisms** — each one lists the joints and DOFs that move the most in it,
  with their share of the motion (+1.00 is the largest). A frame without
  bracing or base fixity sways; a beam on two rollers slides; a chain of hinges
  folds. In a 2D model the DOFs are Ux, Uz and Ry (the X-Z plane).
- **Negative stiffness** and **ill-conditioning** are reported separately from a
  mechanism. A small positive stiffness is not silently called a mechanism.
- **Ungrounded components** �?" a connected group with no restraint or grounded
  spring �?" are checked with a rigid-body translation. When the motion costs no
  stiffness it is reported as a mechanism, with a partial result because the
  rest of the model is not searched.
- **Incomplete** checks say so: an unavailable sparse backend, a non-converged
  eigenvalue search or a lower-bound mechanism count is not presented as a
  stable model.

The joints that move are selected in the view, so you can see where to add a
support, a brace or a member, or which DOF to restrain.

# How it decides
The matrix is captured through OpenSees' **PythonSparse** system as CSR when
the engine provides it, without a dense `n × n` array for a large model. A
small model (up to 1 200 equations) uses a dense symmetric eigenvalue reference;
larger models use a sparse shifted eigenvalue search near zero after a diagonal
scaling. A zero is reported below 1e-10 of the matrix scale, with a normalized
eigenpair residual check. Constraints (equalDOF, rigid links, diaphragms) are
applied first, so a DOF a constraint ties is not counted twice. Mechanism
vectors are expanded to the constrained nodes for the report and selection.
The CSR pointer's last entry defines the stored entries; if OpenSees reports a
larger allocated `nnz`, the stored prefix is used and the difference is noted.
Integer CSR buffers are accepted in 32-bit or 64-bit form.
The check reads the **initial** stiffness: a model that only becomes unstable as
it yields or buckles needs a nonlinear analysis; this is not a buckling factor.

The child reports phases (precheck, build, capture, diagnose, reconstruct) to
the console. **Analyze → Cancel Stability Check** stops it, and the GUI also
imposes a soft 300 s limit; a long native eigenvalue call cannot be interrupted
cooperatively, so the parent terminates the child at its hard deadline. For
reproducible families use `python tools/stability_bench.py --family frame
--size 12` (or `--family truss --mechanism`).
