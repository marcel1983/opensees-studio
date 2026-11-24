---
title: Edit → Join Frames
group: Edit and tools
summary: Merge selected members that continue each other into one member.
see_also: edit.divide_frames, edit.merge_joints
order: 690
---

The inverse of Divide Frames: a beam drawn in pieces, or split at a joint that
is no longer needed, becomes one member again. Select two or more members.

Two selected members are joined at a joint when the joint has nothing to keep:
- they are the **only elements** at the joint, and run in a **straight line**
  through it;
- they are the **same element type with the same properties** (section,
  transformation, modifiers, local-axis angle) and neither has end releases,
  end offsets or an insertion point;
- the joint has **no restraint, mass, nodal load or constraint**;
- their **uniform loads match** pattern by pattern (the joined member takes one
  copy); a point, trapezoidal or temperature load keeps the joint.

A chain of pieces becomes one member, with the id of its first piece; the
joints between them are removed. The log names every joint that was kept and
why. One undo step; with nothing to join, nothing changes and a message says
why.
