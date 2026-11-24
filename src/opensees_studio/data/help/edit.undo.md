---
title: Edit → Undo
group: Edit and tools
summary: Take back the last model edit (Ctrl+Z).
see_also: edit.redo, edit.delete
order: 590
---

Every change to the model is a command on one undo stack: adding a node, moving a
selection, assigning a section, importing a drawing, fixing duplicates. Undo
takes the last one back; Redo puts it back.

- A command that touches several things — a wizard's frame plus its grid, an
import plus the section it needed — is **one** entry: one undo takes the whole
thing.
- The undo stack is not saved with the project: closing and reopening starts a
  new history.
- The stack is what makes a destructive experiment cheap: run it, look, undo.
