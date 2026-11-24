---
title: Display → Reactions Table
group: Display
summary: The reactions of the case being shown, one row per restrained node.
see_also: display.reactions
order: 1610
---

Brings the **Reactions** tab of the bottom dock to the front: node, Fx, Fy, Fz,
Mx, My and Mz in global components, in project units. It follows the case on
screen, so it updates when the displayed result changes.

# Reading it
- Only nodes that report a reaction appear; a free joint is not listed as a row
  of zeros.
- A case with a time axis shows the **final step**, the same one the arrows draw.
- A 2D model stores three components (Ux, Uz, Ry), so it shows **Fz** and
  **Mz**, with Fy and Mx at zero.
- The arrows in *Display → Show Reactions* are built from exactly these numbers.

The tab lives with Console and Results: click its header, or use this action to
raise it.
