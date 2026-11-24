---
title: Response spectrum: modes, damping and combination
group: Mechanics
summary: Combining modal maxima with SRSS or CQC.
see_also: mechanics.modal, display.response_spectrum
order: 100
---

A response spectrum case takes a design spectrum (a code spectrum such as
TBDY-2018, a user target spectrum, or one computed from a record) and the
structure's modes, and combines them into a design response.

# Parameters
- **Spectrum and direction** — the curve, its damping and the direction it acts
  in (horizontal X/Y, vertical Z). The application's default damping is 5 %.
- **Combination rule** — **SRSS** (root sum of squares) or **CQC** (complete
  quadratic combination). SRSS assumes the modes are far apart in period; CQC
  adds the cross terms with a correlation coefficient and is the safer default
  when modes are close, which is the usual case for a 3D building.
- **Scale factor** — multiplies the spectrum's accelerations for this case
  (Analyze → Cases, default 1). Use it for the base-shear scaling a code asks
  for: NSCM Ec. 8.2-14 (Vb / Vt when the modal base shear Vt is below the ELF
  Vb), ASCE 7 §12.9.1.4, or RNC-07 Art. 33 a (0.8 a W0 / (Ω Q')). Divide the
  required base shear by the case's base shear and type the ratio.
- **Modes** — every mode used must be orthogonalised and sign-normalised; the
  application does that before combining, so a repeated eigenvalue cannot
  produce a wrong combination. Inside a group of repeated modes it also turns
  the basis so one mode carries all of the group's participation in the
  spectrum's direction: SRSS and CQC then give the same answer whatever basis
  the eigen solver returned, on every platform.

# Mechanics
The peak response of mode *i* is Sa(T_i)·Γ_i·φ_i (Γ is the modal participation
factor). The total peak is **not** the sum: the modes do not peak at the same
instant, so they are combined statistically. SRSS/CQC give a design envelope,
not a time history — nothing here tells you when the peak happens.

**Forces and reactions.** Element forces, support reactions and shell
resultants come from the static response of the model to each mode's equivalent
load, M·φ_i·Γ_i·Sa(T_i), combined component by component with the same rule and
correlation as the displacements. They are peak magnitudes (the sign is lost in
the combination), and a combination uses them as plus and minus that peak. The
load uses the nodal mass, as the participation factors do; mass given as an
element density is not in it.

For a nonlinear structure a response spectrum is only an approximation: it comes
from linear modal analysis. The usual route is a pushover or a transient.
