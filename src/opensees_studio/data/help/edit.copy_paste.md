---
title: Edit → Copy / Paste
group: Edit and tools
summary: Copy the selection, then paste it at an offset as often as needed.
see_also: edit.replicate, edit.move
order: 720
---

**Copy (Ctrl+C)** remembers the selected joints and members; selecting only
members takes their joints too, and selecting only joints takes the members
between them. Nothing is changed in the model yet.

**Paste (Ctrl+V)** asks for the offset **dX, dY, dZ** from where the copied
objects are, in the project's length unit, and places one copy there. The
offset of the last paste is offered again, and the pasted objects become the
selection, so a frame copied once can be pasted bay after bay.

The copy is a Replicate of one copy: it keeps sections, releases and other
frame options, restraints, masses and the loads of every pattern (see
Edit → Replicate). Paste is one undo step.

- While a text field has the focus (the console, a table), Ctrl+C and Ctrl+V
  copy and paste text there; click the model view first.
- The clipboard belongs to the open project: New or Open empties it, and
  copied objects deleted since are left out of the paste.
