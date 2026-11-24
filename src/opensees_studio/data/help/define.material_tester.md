---
title: Define → Material Tester
group: Define
summary: Run one material through a strain protocol and see its curve.
see_also: define.material_library, mechanics.fiber_sections
order: 980
---

A single material, loaded in an isolated model by a prescribed strain history,
with the stress-strain response plotted. It answers "what does this material do"
before you trust it inside a section.

# Values
- **Material** — any defined uniaxial material.
- **Protocol** — monotonic to a strain, or cyclic with an amplitude and a number
  of cycles. The strain rate is irrelevant for these rate-independent laws.
- It uses the same emitters as the analysis runner, so a material cannot behave
  one way in the tester and another way in a model.
- Like an analysis, the test runs in a separate process: the solve takes
  milliseconds, starting the process about a second. If OpenSees ends that
  process on an input it cannot handle, the summary shows the exit code and the
  solver's last output, and the application stays open.
