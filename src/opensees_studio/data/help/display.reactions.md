---
title: Display → Show Reactions
group: Display
summary: The support reactions of the case on screen, as arrows and arcs.
see_also: display.reactions_table, analyze.results_database
order: 1600
---

Draws, at every restrained node, a red arrow for the reaction force and a
violet circle for the reaction moment, both **proportional to their
magnitude**: the largest force and the largest moment of the case set the
length and the radius, so the picture compares nodes with each other rather than
with an absolute value.

# Reading it
- The arrow points along the reaction: the force the support applies to the
  structure. An arrow that ends on the joint is a force pulling that way.
- The circle lies in the plane perpendicular to the moment, and you read its
  turning sense with the right hand: thumb along the moment, fingers curling the
  way it acts.
- The case shown is the one in the caption (top left). Change case and the
  overlay follows.
- The numbers of the same case are in the **Reactions** tab and in
  *Display → Reactions Table*.

Nothing is drawn when the case reports no reactions (a free-floating model, or
element types that do not deliver them).
