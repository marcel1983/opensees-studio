---
title: Edit → Replicate
group: Edit and tools
summary: Copy the selection N times, each copy offset by (dx, dy, dz).
see_also: edit.move, edit.mirror, define.portal_frame, edit.copy_paste
order: 710
---

The classic "copy this frame to the next axis" command, and the way a 2D portal
becomes a 3D building: select the frame, offset by the frame spacing along the
ridge direction, and repeat.

# Values
- **dX, dY, dZ** — the offset between consecutive copies. The default dZ of 3 is
  a storey height; for a building along Y, set dY and zero the others.
- **Number of copies** — how many, each at 1×, 2×, … the offset.
- **Measure…** — picks two joints in the viewport (F7 works too once the
  viewport has the focus) and fills dX, dY, dZ with the vector between them,
  such as the spacing from one axis or floor to the next. The window is
  modeless, so the viewport stays usable while it is open.

# What comes with the copy
- Nodes keep their **restraints and masses** (they are node fields).
- The **loads** on the copied nodes and elements are re-created for the copies:
  a copied loaded floor comes back loaded. Loads that were already copies are
  not doubled.
- **Ground motions are not copied**: copying a frame must not multiply a base
  motion.
- Only elements whose nodes are *all* in the selection are copied; a member that
  hangs outside the selection is skipped, not cut.
