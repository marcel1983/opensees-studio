---
title: Ground motions: records, scaling and metadata
group: Mechanics
summary: What the record library stores, and what scaling does to it.
see_also: mechanics.transient, define.ground_motions
order: 110
---

Ground-motion records live in the project catalog (Define → Ground Motions).
Each entry has a file, a format, a unit and metadata computed from the samples.

# Parameters
- **Format** — PEER `.AT2`, two-column (time, acceleration) or single-column
  (acceleration only, with a step you provide).
- **Acceleration unit** — `g` or the project's acceleration unit; the factor is
  stored with the record so what the solver receives is explicit.
- **Scaling** — by PGA, by Sa(T1) of a chosen period, or to match a target
  spectrum over a period range. Every scaling factor is recorded in the case and
  reported, so a scaled run can be explained later.
- **Metadata** — PGA, PGV, PGD, Arias intensity and the 5-95 % significant
  duration, all computed from the samples and stored with the record.

# Mechanics
- A **uniform excitation** applies the record at every support, which is the
  usual assumption for a small structure; a **multiple-support** (imposed
  displacement) case drives chosen supports with different records, which is
  what a long bridge needs.
- The record's own time step and the analysis step must agree, or the
  application resamples and says so. Reading a 0.005 s record into a 0.01 s
  analysis silently halves the frequency content.
- Scaling by Sa(T1) is not the same as scaling by PGA: the first matches the
  demand at the structure's own period, the second matches the amplitude of the
  input.
