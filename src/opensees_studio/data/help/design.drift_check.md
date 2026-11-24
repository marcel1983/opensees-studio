---
title: Design → Storey Drift Check
group: Design
summary: Amplified inter-storey drift ratios against an allowable ratio.
see_also: design.steel_check, define.storeys
order: 510
---

For every static and response spectrum case with a result in this session, the
drift ratio of each storey (the difference of the floor displacements over the
storey height, see Define → Storeys) is multiplied by the **amplification** and
compared with the **allowable drift ratio**. A ratio above 1 is over the limit.

The **Code** list fills in common limits: ASCE 7-22 Table 12.12-1 (0.020, 0.015 or
0.010 h by risk category; set the amplification to Cd / Ie, since the analysis
gives elastic drifts), NCh433 (0.002 h at the centre of mass), Eurocode 8,
RNC-07 Art. 34 and NSCM. **RNC-07**: service drifts are the reduced ones times
Q'Ω/2.5 against 0.002 h (0.004 h without fragile partitions), collapse drifts
times QΩ against Tabla 4 (0.030 h for ductile frames, 0.015 h with limited
ductility); the presets assume Q' = 2 and Q = 4, 3 or 2: change the
amplification to your Q. **NSCM** (10.4, Tabla 5.5.1): δ = Cd δe / I with the
system's γmax; the presets are risk category I/II (I = 1). Category III takes
75 % of the limit and I = 1.3, category IV 50 % and I = 1.65.
Response spectrum drifts are combined per storey by the case's own rule, never
taken as the difference of two peak displacements.

The project needs storeys; the limit and the amplification are saved with it.
