---
title: Options → Autosave Recovery Copy
group: Options
summary: How often unsaved changes are copied for recovery after a crash.
see_also: file.recent, analyze.run
order: 1900
---

Every few minutes (**5** by default; 2 or 10, or **Off**), a project with
unsaved changes is written to a **recovery copy**. The project file itself is
never touched: only Save writes it.

- A saved project's copy sits beside it as `<name>.run-snapshot.osmodel`. Opening
  the project after a crash, when the copy is newer than the file, asks whether
  to **restore** the changes (they come back as unsaved) or **discard** them.
- A project that was never saved has its copy in the application's data
  folder. The start page then offers **Recover the unsaved project**, with the
  time of the copy.
- Saving, closing the project normally or opening another one removes the copy.
  A run writes the same copy before it starts, so the latest one wins.

The choice is remembered for the next sessions. Nothing is written while the
project has no unsaved changes, or while an analysis runs.
