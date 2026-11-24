---
title: Tools → Select
group: Edit and tools
summary: The default tool: click to select, drag a box, middle-drag to orbit, wheel to zoom.
see_also: tools.draw_node
order: 770
---

Clicking a node or an element **adds** it to the selection, so building one is
just clicking; Ctrl+click takes an item out, and clicking empty space clears the
lot. Dragging with the left button draws a box, as in SAP2000: dragged **left
to right** (a solid blue window) it takes only what is fully inside; dragged
**right to left** (a dashed green box) it also takes what the box touches, so a
member that crosses it is picked. Select → Intersecting Line picks what a line
cuts instead. A box never selects a node or an
element that is hidden in that viewport. The camera turns with a
middle-button drag, which the left button no longer does.

With nothing else active this is also what unlocks the model for inspection:
hovering an element shows its properties, and the property dock follows the
selection.

# Editing several at once
With more than one thing selected, the Properties panel edits what they share.
Joints: the restraints (a box that differs between the joints shows a partial
check and is left alone) and the six lumped masses. Elements: type, section,
material, area, geometric transformation, integration rule and points, end
offsets, rigid-zone factor and cardinal point, each applied to the selected
elements that have it (an area to the trusses, a section to the frames). A value
the selection shares is shown as it is; one that differs shows **(varies)** and
keeps each item's own value unless you change it. **Apply to N joint(s)** and
**Apply to N element(s)** send only what you changed, as one undo step.
