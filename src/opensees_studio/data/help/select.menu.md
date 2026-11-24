---
title: Select menu
group: Edit and tools
summary: Select by element type, section, material or load pattern, invert, or go back.
see_also: edit.select_all, edit.clear_selection, edit.divide_frames
order: 650
---

Every entry **adds** to the current selection, so two queries in a row select
both sets: the frames of section A, then those of section B. Start from Clear
Selection (Esc) to pick one set alone.

# Entries
- **Invert Selection** (Ctrl+I) — selects every joint and element that is not
  selected, and drops the ones that are.
- **Get Previous Selection** (Ctrl+P) — goes back to what was selected before
  the last change; pressing it again swaps back.
- **Intersecting Line** — the next left drag on the view draws a line instead
  of a box, and every frame, truss or shell the line cuts is selected (Ctrl held
  when you release: deselected). Joints are not taken. It is the quick way to
  pick the columns of one storey or the braces of a bay; it switches itself off
  after one line, and Esc cancels it.
- **The Selection toolbar** (on the left) has SAP2000's side buttons: **all**
  (Select All), **ps** (Get Previous Selection), **clr** (Clear Selection) and
  **line** (Intersecting Line).
- **All Joints / All Elements** — one kind only; Select All (Ctrl+A) takes both.
- **By Element Type / Section / Material** — the submenus list what the model
  uses, with a count. A material is found wherever an element reaches it: its
  own material fields, or the fibres, patches and layers of its section.
- **By Load Pattern** — the joints and elements a pattern loads. A pattern with
  a self weight loads every frame whose section has a unit weight.
- **By Group** — the joints and elements of a group (Define → Groups).
- **Supported Joints**, **Joints with Mass**, **Elements with Self Weight**
  (frames, trusses and shells).
- **Loose Joints** — joints no element, constraint, rigid link or diaphragm uses.
  **Joints Inside Members** — joints lying inside a frame or truss without being
  one of its ends, with those members (fix them with Edit → Divide Frames at
  Joints). **Joints on Shell Edges** — joints inside a shell edge, not at a
  corner, with those shells (subdivide the shells with Edit → Mesh). The three
  use the duplicates check's tolerance, a millionth of the model's size.
- **Joints of Selected Elements** — the end joints of what is selected;
  **Elements between Selected Joints** — the elements whose every joint is
  selected.
