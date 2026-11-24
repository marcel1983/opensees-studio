---
title: Edit → Redo
group: Edit and tools
summary: Put back the edit Undo took away (Ctrl+Y).
see_also: edit.undo
order: 600
---

Redo replays the command that was undone last. Doing anything new clears the redo
branch, as usual.

A command that is redone re-applies the *same* inputs it was given (the same
offset, the same description, the same file); it does not re-read anything from
disk.
