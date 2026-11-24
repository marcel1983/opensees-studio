---
title: Display → Influence Line
group: Display
summary: Any response of an influence-line case against the load's position, and a vehicle on it.
see_also: analyze.cases, display.force_diagram
order: 320
---

An **influence-line case** (Analyze → Cases… → Add → *InfluenceLine*) walks a
load along a chain of frame members — a bridge girder, a crane runway — and
solves the model once per stop. Each stop's result holds every displacement,
reaction and member end force with the load there.

# Defining the case
- **Path**: the member ids in the order the load travels. Consecutive members
  must share a joint; each is walked from the joint it shares with the previous
  one, so a path can turn corners.
- **Stops per member**: equal intervals of every member (a joint shared by two
  members is one stop). Ten is plenty for straight members.
- **Load direction** and **value**: -1 along Z, the default, is a unit load
  downward. The analysis is linear elastic.
- **Vehicle axles** (optional): `load@offset` pairs, the offset measured behind
  the front axle, for example `35@0, 145@4.3, 145@8.6`. They prefill the dialog.

# The dialog
Pick the **response**: a joint displacement or a reaction (by joint and DOF) or a
member end force (by member, component and end, in the sign of the force
diagrams). The plot is its value **per unit load** in the sense of the case's
load, against the distance along the path.

**Envelope** moves the vehicle across the path in **both directions**, axle by
axle (an axle off the path counts nothing), and reports the largest and the
smallest effect and where the front axle stood. Axle loads are in the sense of
the case's load: with the default case a downward axle is positive.
