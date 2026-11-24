---
title: Display → Show Load Assigns
group: Display
summary: Choose which load pattern and which kinds of load the canvas draws.
see_also: display.options, display.object_info, assign.distributed_load, assign.frame_point_load
order: 1710
---

The canvas draws the loads of the model view (View → Visibility → Loads must be
on; OK here switches it on). This dialog says which ones:

- **Load pattern** — *All load patterns* draws every pattern, each in its own
  colour, named in the key at the top left. Loads that share a member, the
  same point of a member or a joint are **stacked**: the second is drawn above the
  first instead of on top of it, so a partial load is not hidden under a uniform
  one. Choosing one pattern draws that pattern only, in the colours of the kinds
  of load (green joint loads, magenta frame point loads, orange frame
  distributed loads, sky-blue shell loads), with a legend of the kinds it has.
- **Kinds of load** — joint loads, frame point loads, frame distributed loads
  (uniform, trapezoidal, partial, and the frame loads an area load becomes) and
  shell loads can each be hidden, to read a dense model one kind at a time.
- **Show values** — writes the magnitude beside each load: `50 kN`,
  `10 kN/m`, `0 → 15 kN/m` for a load that varies, a shell pressure at its
  centre. Values are in the display units (Options → Units); newtons and
  pascals become kN and kPa from a thousand up.

Arrow sizes are proportional to what is drawn: a force against the largest
force, a load per length against the largest load per length, so a 50 kN load
is longer than a 20 kN one. The overall size is the Load arrows percentage of
Display → Display Options.

The choice belongs to the viewport and is saved with the project's view
settings. A deleted pattern falls back to all patterns.
