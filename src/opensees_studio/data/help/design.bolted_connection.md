---
title: Design → Connection Calculators → Bolted Connection (Prying, Bolt Group)
group: Design
summary: Prying action of a tee or end plate, and the most loaded bolt of an eccentric group.
see_also: design.base_plate, design.chapter_j
order: 470
---

A calculator (LRFD, project units).

# Prying action (AISC Manual Part 9)
For a flange of thickness t and Fu with bolts of diameter db in holes d' at a
tributary width p, b from the bolt line to the stem and a to the edge:
b' = b - db/2, a' = min(a, 1.25 b) + db/2, ρ = b'/a', δ = 1 - d'/p,
tc = √(4 B b' / (0.9 p Fu)) for the bolt's available tension B,
α' = ((tc/t)² - 1) / (δ(1 + ρ)) within 0 and 1, Q = (t/tc)²(1 + δα') ≤ 1. The
available tension per bolt is B·Q; the window also gives tc and the thickness
that needs no prying for the demand.

# Eccentric bolt group (elastic method, Manual Part 7)
Bolts at x,y (semicolon-separated pairs) and a force (Px, Py) at a point: each
bolt takes P/n plus the torsion M·r/Ip about the group's centroid. The most
loaded bolt is compared with the single-bolt strength you give (the smaller of
J3.6 shear and J3.10 bearing, from Design → Steel Connections → Connection Checks). The elastic
method is conservative next to the instantaneous centre of rotation.
