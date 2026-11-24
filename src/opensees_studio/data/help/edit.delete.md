---
title: Edit → Delete
group: Edit and tools
summary: Remove the selected nodes and elements, and what hangs from them.
see_also: edit.check_duplicates, edit.clear_selection
order: 610
---

Deletes the selection. Deleting a **node** also removes the elements that use
it, and the loads and constraints that pointed at it: leaving a dangling
reference makes the model invalid and the next run refuses it.

- Deleting a node that a member needs is refused rather than silently cutting
  the member, when the member is not itself selected.
- The deletion is one command: Ctrl+Z restores the nodes, elements, loads and
  constraints together.
- The **Delete** key does the same from any ribbon tab, as does the Delete
  button in the Home tab's Edit group.
- To remove a duplicate, look at Edit → Check Model for Duplicates first: it
  merges instead of deleting, which keeps the loads and restraints.
