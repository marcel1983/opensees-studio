---
title: Analyze → Auto-mesh Frames Before Run
group: Analyze
summary: Run divides frames that another frame ends on or crosses, so they connect.
see_also: edit.divide_frames, analyze.run
order: 680
---

A beam drawn from column to column with a secondary beam ending in its middle,
or two braces drawn across each other, look joined on screen but share no
joint: the secondary beam is left hanging, the braces pass through each other.
Like SAP2000's automatic frame meshing, Run fixes that before it starts.

# What Run does
- A frame or truss is **split at every joint lying inside it**: a member ending
  on another one gets a joint there, shared by both (a T-junction).
- Two members that **cross** with no joint are both split, and the crossing
  becomes one joint.
- A joint counts as lying on a member within a thousandth of the model's size,
  the tolerance Edit → Divide Frames at Joints proposes.
- The pieces keep the section, material, local axes, modifiers and the other
  assignments; end releases and end offsets stay at the member's own two ends;
  distributed loads follow the pieces, a point load goes to the piece it falls
  on, and the pieces stay in the member's groups.
- It is **one undo step** ("Auto-mesh frames") in the model, written to the
  log, so the results belong to the pieces you see. Nothing is divided by
  length, and nothing happens while you draw.

# Turning it off
- **Analyze → Auto-mesh Frames Before Run** turns it off for the whole project
  (saved with it).
- **Assign → Frame → Auto Mesh…** turns it off for the selected members: such
  a member is never split by Run, neither where another member ends on it nor
  where it crosses one. A member that ends on it still has its own end joint,
  and the members it ends on are still split there.

A batch run from the command line uses the model as it is saved.
