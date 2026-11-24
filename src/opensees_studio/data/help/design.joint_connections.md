---
title: Design → Steel Connections → Connections by Joint
group: Design
summary: Every member end: what it frames into, the connection that fits, shear tabs checked.
see_also: design.connections, design.member_classification, design.base_plates
order: 420
---

One row per **member end** of the frame (physical members, see Design → Member
Classification; a member that goes on through a joint has no end there).

# Topology
- **Beam to column flange / web**: a beam end at a column. Flange when the
  beam runs along the column's depth d, web otherwise (in 2D, flange).
- **Beam to girder**: a beam end at a beam that continues through the joint.
- **Brace**, **column splice** (a column onto a column of another section,
  listed once, on the upper one), **column base** (a column on a support).

A free cantilever tip and a column top under a roof beam are not connections.

# Suggested connection
- A beam end whose **major-axis moment is released** (Assign → Frame →
  Releases) is a simple connection: a **single-plate shear connection** (shear
  tab), checked here.
- A moment beam end at a column flange in an **SMF or IMF** (Design → Design
  Basis): the **reduced beam section** of AISC 358 Ch. 5, designed in Design →
  Connections. Other moment ends: a fully restrained moment connection, not
  checked here.
- A brace: a gusset plate (Design → Steel Connections → Gussets for SCBF). A
  column splice: Design → Steel Connections → Column Splices for SCBF. A column
  base: Design → Steel Connections → Base Plates.

# The shear tab
Conventional configuration of AISC Manual Part 10: one row of n bolts at s,
the bolt line a from the weld, edge distances Lev and Leh, a plate welded both
sides to the support. Checked under the **largest end shear** over every
alternative of the design load sets (the direct analysis cases when they
exist): bolt shear on the most loaded bolt with the full eccentricity a
(elastic method, conservative), bolt bearing and tearout on the plate and the
beam web, plate shear yielding and rupture, block shear, the welds, the
detailing rule w >= 5/8 tp and the ductility limit tp <= d/2 + 1/16 in. A beam
end starts from 3/4 in A325-N bolts at 3 in, a 3/8 in A36 plate and 1/4 in E70
welds, with as many bolts as fit in the beam's clear depth. Axial force in the
beam (a collector) is not checked.
