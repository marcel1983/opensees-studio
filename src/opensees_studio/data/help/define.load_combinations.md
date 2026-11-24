---
title: Define → Load Combinations
group: Define
summary: Factored sums and envelopes of the results of analysis cases.
see_also: analyze.cases, analyze.run, display.select_results
order: 1130
---

A load combination combines the **stored results** of analysis cases; it never
runs a solver of its own. A combination can include Static and Response Spectrum
cases, and other combinations (an envelope of the strength combinations, for
instance). Each included case has a scale factor.

# The four types
- **Linear Add** — the factored sum, 1.2·DEAD + 1.6·LIVE. Superposition: valid
  only when the cases respond linearly.
- **Envelope** — the maximum and the minimum over the included cases, value by
  value. Valid for any case, linear or not.
- **Absolute Add** — the sum of the magnitudes.
- **SRSS** — the square root of the sum of the squares.

# Maximum and minimum
Every result has an upper and a lower value. A static case has one value (both
are the same); a response spectrum result is a peak, so it counts as plus and
minus that peak. A Linear Add of static cases therefore has one value; an
envelope, an SRSS, an Absolute Add, or anything that includes a spectrum has a
maximum and a minimum. With a negative scale factor the two swap.

Element forces are enveloped as **internal forces**, the sign the force diagram
draws, so the diagram of the maximum is the upper envelope of the case diagrams.
The results table lists each end force as OpenSees reports it (localForce), with
its maximum and minimum.

# What a combination contains
Only what every included case provides. A response spectrum case provides
displacements, reactions, element forces and shell resultants: each is the SRSS
or CQC of the response to the equivalent static load of every mode, a peak
magnitude, so it counts as plus and minus that peak. A spectrum result stored
before it had forces gives displacements only: run the case again.

# Warnings
A Linear Add, Absolute Add or SRSS that includes a case solved with an iterative
algorithm (Newton, …), or a model with P-Delta or corotational transformations,
is applied with a warning: adding nonlinear responses is not the response to the
added loads. Run the summed loads as one case instead, or use an Envelope.
Material nonlinearity is not detected.

# Running a combination
Analyze → Run lists the combinations after the cases. Running one runs only the
cases it needs that have no current results (in one analysis process), then
combines. A result stays current until the model changes; editing a combination
does not make results stale. Display → Show Results Of… switches between stored
results without running anything.

# Generating the combinations of a design code
**Generate from a design code…** adds the combinations of ASCE 7-16 (LRFD or
ASD), EN 1990, TS 500 / TBDY 2018, RNC-07 or NSCM Managua from cases you tag
with the load they carry: Dead, Live, Roof live, Snow, Rain, Wind and Earthquake (the tag is guessed from
the case name). The result is an ordinary set of Linear Add combinations: edit,
copy or delete them. Wind and static earthquake cases are added in both signs; a
response spectrum case is already plus and minus, so it is added once. An
envelope over each generated group is added too (one per group, so the ultimate
and serviceability limit states of EN 1990 do not mix). Roles a code does not use
are named after the run.

**Create the missing load cases** (on by default) gives every load the code uses
that no case is tagged with an empty load case of its own before generating:
LIVE, ROOF LIVE, SNOW, RAIN, WIND X and WIND Y, EQ X and EQ Y (one wind and one
earthquake case along X in a 2D model), and DEAD with the self weight if there is
no dead case. Each is a Plain pattern with a linear time series and a linear
static case, all named after the load; the dialog lists what it would create.
Their patterns start empty: assign the loads before running. Undo removes the
cases and the combinations together.

The factors are the code's. Judgement stays yours: the occupancy-dependent
live-load reduction, favourable versus unfavourable permanent action, the
national annex.

**Earthquake: 100% + 30% orthogonal rule** applies to any code: with two or more
earthquake cases, each acts at 100% with the others at 30% (±Ex ± 0.3Ey and
±0.3Ex ± Ey).

## ASCE 7-16 LRFD (Section 2.3.1)
- 1.4D
- 1.2D + 1.6L + 0.5(Lr or S or R)
- 1.2D + 1.6(Lr or S or R) + (L or 0.5W)
- 1.2D + 1.0W + L + 0.5(Lr or S or R)
- 1.2D + 1.0E + L + 0.2S
- 0.9D + 1.0W
- 0.9D + 1.0E

The live-load factor in the last combinations is 1.0: the 0.5 exception depends
on the occupancy.

With **Add overstrength combinations (Ω0 E)** and a seismic case, Section 2.3.6
adds `(1.2 + 0.2SDS)D + Ω0E + L + 0.2S` and `(0.9 - 0.2SDS)D + Ω0E`, named
`Ω0: …`; `Ω0` (Table 12.2-1) and `SDS` are dialog fields.

## ASCE 7-16 ASD (Section 2.4.1)
- D; D + L; D + (Lr or S or R); D + 0.75L + 0.75(Lr or S or R)
- D + 0.6W; D + 0.7E
- D + 0.75L + 0.75(0.6W) + 0.75(Lr or S or R); D + 0.75L + 0.75(0.7E) + 0.75S
- 0.6D + 0.6W; 0.6D + 0.7E

The overstrength option adds Section 2.4.5:
`(1.0 + 0.14SDS)D + 0.7Ω0E` and `(0.6 - 0.14SDS)D + 0.7Ω0E`.

## EN 1990
- **Ultimate, equation 6.10**: 1.35G + 1.5Q1 + Σ 1.5 ψ0,i Qi, with each variable
  action (imposed, roof, snow, wind) leading in turn, and 1.35G alone. With
  *favourable permanent action* the set is repeated with 1.0G (uplift,
  overturning).
- **Seismic (accidental), 6.11b**: G + E + Σ ψ2,i Qi.
- **Serviceability**: characteristic G + Q1 + Σ ψ0,i Qi; frequent
  G + ψ1,1 Q1 + Σ ψ2,i Qi; quasi-permanent G + Σ ψ2,i Qi.

The ψ factors are those of Table A1.1: the *imposed load category* (A to H) sets
them for Live cases, roofs (Lr) are category H, wind is 0.6 / 0.2 / 0, snow is
0.5 / 0.2 / 0 (0.7 / 0.5 / 0.2 above 1000 m). Rain has no EN 1990 factors and is
not used. With *Roof imposed load without snow or wind* the roof load (Lr),
when it leads, is not accompanied by the snow or the wind (EN 1991-1-1
3.3.2 (1)).

## TS 500 / TBDY 2018
- 1.4G + 1.6Q
- G + nQ ± E and 0.9G ± E (TBDY 2018), with n the *live load participation* (1.0
  by default; Table 4.3 of the code gives 0.3 for housing and offices)
- G + 1.3Q ± 1.3W and 0.9G ± 1.3W (TS 500)

Roof live, snow and rain cases are not used. Check the factors against the
edition you design to.

## RNC-07 Nicaragua (Art. 15 II)
Dead is CM, Live CV, Wind Pz and Earthquake Fs. Ultimate strength (a):
- 1.4CM; 1.2CM + 1.6CV
- 1.2CM + 1.6Pz + CV; 1.2CM + Fs + CV
- 0.9CM + 1.6Pz; 0.9CM + Fs

With **Also the allowable stress combinations**, Art. 15 II b adds CM + CV,
CM + Pz, CM + 0.7Fs, 0.6CM + Pz and 0.6CM + 0.7Fs (named `ASD: …`, in their own
envelope). The earth pressure Ps is not a load tag: add it to the combinations by
hand (1.6Ps in the ultimate set).

## NSCM Managua (7.5 and 7.6)
Dead is CM, Live CV, Roof live CVT, Snow is the volcanic ash CCV, Wind V and
Earthquake Eh. LRFD (7.5.1, 7.5.4):
- 1.4CM; 1.2CM + 1.6CV + 0.5CVT + CCV
- 1.2CM + 1.6(CVT or CCV) + (CV or 0.5V); 1.2CM + V + CV + 0.5(CVT or CCV)
- 0.9CM + V
- 1.2CM + Ev + Eh + CV + 0.2CCV; 0.9CM - Ev + Eh

The vertical component Ev = 0.2 a0 Fas CM (Ec. 7.8-4) is folded into the dead
factor, from the **a0·Fas** field (0.513 for Managua on class D). The
overstrength option adds the Ω0 Eh combinations, and the allowable stress option
the ASD set of 7.6.1 and 7.6.5. Combinations 5 and 7 of 7.6.1 are printed with
"0.6CV"; they are the wind combinations (as combination 6 and ASCE 7 2.4.1), so
0.6V is used. The lateral soil load H has no tag and is left out.
