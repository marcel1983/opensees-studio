---
title: Tools → Draw Shell (F8)
group: Edit and tools
summary: Click the corners of a shell: four for a quadrilateral, three and back for a triangle.
see_also: define.create_shell, tools.draw_frame
order: 820
---

Each click adds a corner: an existing node or a grid intersection (a node is
created if there is none there), as with Draw Frame.

- The **fourth** corner closes a `ShellMITC4` quadrilateral. The corners are put
  in a consistent winding from their coordinates, so clicking them in any order
  does not twist the shell; four points that are not a plane quadrilateral are
  refused with the reason in the status bar.
- After **three** corners, a click on the **first** one closes a triangular
  `ShellDKGT`.
- A dashed outline previews the shell through the corners placed so far and the
  snapped point under the cursor, closed back to the first corner.
- **Esc** drops the corners clicked so far; the tool stays armed for the next
  shell. Each shell is one undo step.
- **Section** — the Tools toolbar shows a Section box with the project's plate
  sections while the tool is armed. A new 3D project already has **Slab 20cm**:
  an elastic plate 20 cm thick of the default 4000 psi concrete (Ec = 57000
  √f'c, ν = 0.2, 150 lb/ft³, so the DEAD case carries its weight). A project
  without any plate section gets that slab, as one undo step, when the tool is
  armed. A composite deck slab comes from Define → Steel Deck Slab Wizard.

Define → Create Shell does the same from three or four selected joints.
