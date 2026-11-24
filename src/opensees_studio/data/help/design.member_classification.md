---
title: Design → Member Classification
group: Design
summary: Physical members, their role and the unbraced lengths the bracing gives.
see_also: design.steel_check, design.basis
order: 350
---

The steel check works on physical members, not on analysis elements. This page
lists them, one row per member.

# Members
Frame elements of the **same section**, end to end and **collinear** (within 1
degree), form one member. A member continues through a joint where other
members frame in, as long as exactly one collinear element of its section goes
on from there. Its ends are taken as braced.

# Bracing points and unbraced lengths
An interior joint holds the member along one of its local axes (y or z) when, at
that joint:
- another frame or truss element runs within 60 degrees of that axis,
- a support restrains the translation along it,
- a rigid diaphragm's plane contains it, or
- a shell's plane contains it (a slab braces a beam laterally).

**Lx** and **Ly** are the distances between the bracing points along the axes
that major- and minor-axis buckling move the member along; **Lb** (lateral-
torsional buckling) is the minor-axis one. The table shows, per member, the
largest value over its elements.

A **2D model** has no out-of-plane information: there every joint where another
element frames in, or a support, braces the member out of its plane too (the
usual assumption that the floors brace the frame).

# Role
Column, beam or brace from the direction (within 20 % of vertical a column,
within 20 % of horizontal a beam, otherwise a brace). Set it by hand where the
direction misleads (a sloped rafter is a beam, not a brace). The role decides
which AISC 341 provisions a member gets.

Lengths that do not fit (a beam braced by a deck the model does not have) are
entered as overrides in Design → Steel Frame Check; they win over these.
