---
title: Design spectra: user table, ASCE 7-16, TBDY 2018, RNC-07 and NSCM
group: Mechanics
summary: Where a response spectrum comes from, and how a case ends up using it.
see_also: define.ground_motions, mechanics.response_spectrum, display.response_spectrum
order: 90
---

Three kinds of spectrum meet in this application, and they are not the same
object:

- a **target spectrum** (Ground Motions → Target spectrum) is a *design*
  spectrum in g: the dialog plots it and the record-scaling reads it;
- a **case response spectrum** (``project.spectra``) is the tabulated curve a
  response-spectrum *analysis* reads, with Sa in the project's acceleration unit;
- a **record spectrum** is computed from one ground motion, to compare with the
  design curve.

# Defining one
- **User table** — a period/Sa file (period in s, Sa in g). It is copied point for
  point into the case spectrum: resampling a table somebody typed would change
  the numbers they meant.
- **ASCE 7-16** — from the mapped MCER ``Ss`` and ``S1`` and the site class, or
  from ``SDS`` and ``SD1`` directly, with ``TL`` from the maps (4 s to 16 s).
  The site coefficients come from Tables 11.4-1 and 11.4-2 and the design values
  from Eqs. (11.4-1) to (11.4-4): ``SDS = 2/3 Fa Ss``, ``SD1 = 2/3 Fv S1``.
  - **Site class F is a site-specific study** (§11.4.8), and so is class E beyond
    ``Ss = 0.75`` or ``S1 = 0.1``: the dialog says so and refuses to extrapolate
    a table the standard leaves blank. Use your own site spectrum instead.
  - Where class **D is assumed** because the soil is unknown, §11.4.3 forbids
    ``Fa`` below 1.2; the checkbox applies that floor.
- **TBDY 2018** — the same machinery with the Turkish site coefficients, ``TL``
  fixed at 6 s.
- **RNC-07 (Nicaragua)** — Art. 27, Ec. 6, from the zone acceleration ``a0``
  (zone A 0.1, B 0.2, C 0.3 g, or the value of the Anexo C map: a value between
  two zones takes the higher zone for Tabla 2), the soil type I to III (``S`` of
  Tabla 2) and the group (A multiplies by 1.5). ``d = 2.7 a0``, Ta = 0.1 s,
  Tb = 0.6 s, Tc = 2 s. Soil type IV needs a site-specific spectrum and is
  refused. **Reduced (a / ΩQ')** divides by Ω = 2 and Q'(T) of Ec. 2 with the
  Art. 23 irregularity factor (0.9, 0.8 or 0.7, Q' never below 1): the spectrum
  of a modal analysis per Art. 33.
- **NSCM (Managua, 2021)** — Ec. 6.7-1 from ``a0`` (0.36667 g for Managua, Tabla
  14.2; the zone Z1 to Z4 follows from it), the site class A to D (``Fas`` of
  Tabla 6.4.1, ``FSTb`` and ``FSTc``) and the risk category I to IV (I = 0.75,
  1.0, 1.3, 1.65). ``A0 = a0 Fas I``, β = 2.4, Tb = 0.05, Tc = 0.3, Td = 2 s, each
  scaled by its FST. Class E needs a site response study and is not offered.
  **Reduced** divides by ``Ro = R ΦP ΦE``, with the rising branch of Ec. 6.9-1.
  The case spectrum of both codes runs to 10 s.

# Using one
"Use as case spectrum" turns the spectrum on screen into the tabulated curve a
case reads, sampling the code's own corner periods (T0, Ts, TL) so the plateau
and both decay branches survive, and converting g into the project's acceleration
unit. A response-spectrum *case* then points at it by id (Analyze → Cases), and
the modal combination (SRSS or CQC) does the rest.
