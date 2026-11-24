---
title: Display → Show Results Of
group: Display
summary: Pick which stored case or load combination the Display views show.
see_also: define.load_combinations, display.deformed, display.force_diagram
order: 1570
---

The Display views (deformed shape, force diagram, shell contours) and the results
panel show one result at a time — normally the latest run. Show Results Of lists
every case result that is still current for the model, and every load
combination, and switches to the one you pick without running anything.

- A combination is combined from the current case results. When one of its cases
  has none (never run, or the model changed since), run the combination from
  Analyze → Run: it runs only the missing cases.
- A combination with a maximum and a minimum draws both force diagrams at once,
  offers a Max/Min choice in the deformed shape, and lists both in the tables;
  Export CSV writes the table shown.
