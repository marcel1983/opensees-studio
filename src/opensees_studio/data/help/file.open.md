---
title: File → Open
group: File
summary: Open a .osmodel project (and offer to recover a crashed run).
see_also: file.save, file.save_as, file.recent, file.run_batch
order: 220
---

A project is a single JSON file with a schema version. Opening one that is newer
than the application is refused rather than quietly rewritten.

- If the current project has unsaved changes you are asked first.
- If an earlier run left a **pre-run snapshot** newer than the file, the
  application offers to restore it: that is the crash recovery path.
- The project you are leaving takes its own pre-run snapshot with it, so
  reopening it later does not offer a recovery nobody needs. Cancelling the
  prompt or the file dialog keeps both.
- An old `schema_version` is migrated on load and stamped with the current one
  on the next save.
- If File → Run Batch… solved this project and the model has not changed since,
  the application offers to **load the stored results**, so they can be viewed
  without running again.
