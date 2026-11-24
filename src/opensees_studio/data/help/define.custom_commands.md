---
title: Define → Custom OpenSees Commands
group: Define
summary: OpenSeesPy calls for anything the application has no form for.
see_also: define.material_library, analyze.cases
order: 1070
---

Each block is Python run while the model is built, in list order:

- **After the materials** — materials exist, sections and elements do not yet.
- **After the elements** — the whole model exists, before loads and analysis.

Names a block can use: `ops` (OpenSeesPy), `project` (read it, do not change it),
`ndm`, `ndf`, and `tag`, the first of the 1000 tags reserved for that block (from
1 000 000 up), so its objects never collide with the application's. A block that
raises stops the run with its name and the error; a block with a syntax error is
refused when you press OK. The exported OpenSees script contains the block's
commands.

# Safety
The code runs on this computer with your permissions. When you open a file that
contains enabled blocks, you are asked whether to trust them; answering No
disables them until you enable them here. Outside the window nobody is there to
ask, so the command-line analysis (`python -m opensees_studio.run`) refuses a
project with enabled blocks unless it is given `--allow-custom-commands`, and a
batch (File → Run Batch, `python -m opensees_studio.batch`) skips such a project
unless *Run custom Python blocks* is ticked or `--allow-custom-commands` given.

# Notes
- With an enabled block, the "no element stiffens this DOF" check is skipped
  (the block may add that stiffness); the solver itself still reports a
  singular model.
- Results are recorded only for the joints and elements of the model; an element
  a block adds shows up in the joints' displacements and reactions.
