---
title: Define → Groups
group: Define
summary: Named sets of joints and elements, to select a part of the model again.
see_also: assign.group, select.menu
order: 2140
---

A group is a name, a colour and the joints and elements it holds, as in SAP2000
and ETABS. Groups carry no mechanics: they let you pick a part of the model again
later. A joint or an element can belong to any number of groups.

# Values
- **Name** — unique, compared without case. **Colour** — click to change it.
- **Joints**, **Elements** — how many each group holds (read only). Fill them
  with Assign → Assign to Group.
- **Add** / **Remove** — a new empty group, or remove the selected rows. Removing
  a group never deletes its joints or elements.

# Notes
- Deleting a joint or an element takes it out of every group; Undo puts it back.
  Fixing duplicates moves a merged joint's membership to the joint that is kept.
- Select → By Group selects a group's members (adding to the selection).
