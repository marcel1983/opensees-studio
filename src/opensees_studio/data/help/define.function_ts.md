---
title: Define → Add Function TimeSeries
group: Define
summary: Constant, Trig, Triangle, Rectangular or Pulse series.
see_also: define.linear_ts, define.path_ts
order: 1050
---

A time series given by a formula instead of samples. The rows follow the type:

- **Constant** — the factor at every time (a load held in a transient).
- **Trig** — factor · sin(2π (t - t_start)/T + shift) + zero shift, between start
  and end (harmonic loads, a sine sweep step).
- **Triangle** — a triangular wave of period T, peak = factor, between start and end.
- **Rectangular** — the factor between start and end, zero elsewhere (a step held
  for a while).
- **Pulse** — rectangular pulses of period T, on for the width fraction of each
  period, between start and end (impacts, machine loads).

A static case steps time by its load increment, so these series also shape a
static load history. Checked against OpenSees' own evaluation.
