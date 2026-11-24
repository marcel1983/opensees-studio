---
title: Display → Export Time-History Animation
group: Display
summary: An MP4 (or GIF) of a transient response.
see_also: display.time_history, display.deformed
order: 1660
---

Exports the deformed shape over the steps of a transient case as an animation,
so a response can be shown to someone else.

- MP4 needs FFmpeg (through `imageio`); GIF always works and is the fallback the
  error message suggests.
- The frame rate and the deformation scale are the values to set: too fast hides
  the response, too slow makes a large file.
- Exporting renders one frame per step: a long record at a small time step is a
  lot of frames, so it is worth narrowing the step range first.
