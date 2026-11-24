---
title: Edit → Divide Frames at Joints
group: Edit and tools
summary: Split frames and trusses at the joints that lie inside them.
see_also: edit.merge_joints, edit.mesh, select.menu, edit.join_frames, analyze.auto_mesh
order: 670
---

A column whose top lands in the middle of a beam, or a brace that ends on a
girder, looks connected on screen; unless the beam has a joint there, the
column passes by and the beam does not carry it. This splits every member at
the joints lying on it, so they are connected.

# Values
- **Tolerance** — how close a joint has to be to a member to count as lying on
  it (a thousandth of the model's size to start with).
- **Apply to** — the selected members, or the entire model.
- **Also split members where they cross each other** — two members crossing
  with no joint get one there, shared by both.

# What happens
- Each member becomes pieces between its joints; the pieces keep the section,
  material and assignments, distributed loads and self weight follow them and a
  point load goes to the piece it falls on. One undo step; the new pieces are
  left selected.
- The summary also reports **loose joints** (on no element) and **joints on a
  shell edge** that is not at a corner. Those are not split here: select them
  from the Select menu, delete the loose ones, and subdivide those shells with
  Edit → Mesh so a corner lands on the joint.
