---
title: Define → Add Linear TimeSeries
group: Define
summary: A load that ramps linearly with time: the default for a static case.
see_also: define.plain_pattern, mechanics.static
order: 1080
---

`Linear` goes from 0 to 1 over the case's time: with N steps, step k has
factor k/N. In a static case this is what a "load ramp in N steps" means, and it
is what a non-linear static case needs to follow the path.

Most of the time you do not create one by hand: a load pattern creates a default
linear time series when the first load is applied.
