---
title: View → Color By
group: View
summary: Paint frames and shells by section, by material or by group.
see_also: view.colors
order: 1950
---

Each viewport chooses its own colouring; a key in its upper-right corner lists
each category in its colour, one line each, so a long section or group name is
written in full (at most 15 lines; the last one then counts the rest).

# Entries
- **Single Colour** — every frame in the frame colour, every shell in the shell
  colour (View → Colors…).
- **By Section** — one colour per section; a BeamWithHinges member with two hinge
  sections gets the colour of the pair. Members with no section (trusses) keep
  the frame colour, listed as "(no section)".
- **By Material** — one colour per material, followed through the section: a
  reinforced-concrete fibre section is "concrete + steel". A truss is coloured by
  its own material.
- **By Group** — each group in its own colour (Define → Groups); an element in
  several groups takes the first one in the list, and one in none is "(no
  group)".

The selection is still drawn in the selection colour on top of the categories.
The choice is saved with the project, like the other display settings of the
main viewport.
