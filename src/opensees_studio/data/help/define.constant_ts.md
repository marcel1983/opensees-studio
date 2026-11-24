---
title: Define → Time Series → Add Constant TimeSeries
group: Define
summary: A load that stays at one factor for the whole case: a preload.
see_also: define.linear_ts, define.plain_pattern
order: 1090
---

`Constant` keeps the pattern at the same factor through every step, so the
loads are there in full from the first step and do not ramp. Use it for a
preload (an axial force before a pushover, gravity before a transient) that
a later case continues from.

The dialog lists the project's Constant series; Add creates one with the
name and factor entered, Apply replaces the selected one, and Delete refuses
while a load pattern still refers to it.
