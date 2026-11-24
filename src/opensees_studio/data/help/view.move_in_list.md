---
title: View → Move Up / Move Down in List
group: View
summary: Step to the next plan level or elevation line, showing only its objects.
see_also: view.top, view.grid_line_view
order: 1790
---

In a plan or elevation (Top, Front or Right), **▲ Move Up in List** (Ctrl+Up)
and **▼ Move Down in List** (Ctrl+Down) move to the next entry of the Level combo:
the storey above or below in a plan, the next or previous grid line in an
elevation. The working plane follows, so the draw tools snap on that level.

As in SAP2000, the view then shows only the objects on that level: the joints
within the Grid Line View window of its grid line (50 mm unless you set another
in View → Grid Line View) and the elements whose joints are all there. Picking
another level in the Level combo keeps showing one level at a time;
**View → Show All Objects** brings everything back.

The buttons are greyed out in the 3D view and when the grid has a single line
across the view.
