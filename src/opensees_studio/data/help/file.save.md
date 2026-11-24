---
title: File → Save
group: File
summary: Write the project (and remove the pre-run snapshot).
see_also: file.save_as, file.open
order: 250
---

Saves to the current path, or asks for one if the project has never been saved.
The file is written atomically: the previous version is replaced only once the
new one is complete, so a save cannot truncate the model you already have.

Saving clears the dirty flag and removes the pre-run snapshot, which only exists
to recover unsaved work.
