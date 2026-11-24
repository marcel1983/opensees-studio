---
title: Design → Design Basis (AISC)
group: Design
summary: Where a steel design starts: code, method, stability design, systems and steels.
see_also: design.direct_analysis, design.steel_check
order: 340
---

Everything the later steel checks read, set once for the project.

# Values
- **Design method** — LRFD or ASD. The Direct Analysis Method cases are made for
  LRFD (in ASD, C2.1(e) runs the analysis at 1.6 times the combinations).
- **Stability design** — the *Direct Analysis Method* of AISC 360 Chapter C
  (second-order analysis with reduced stiffness and notional loads; every
  member is then checked with **K = 1** and **B1** for P-delta), the *Effective
  Length Method* (Appendix 7.2, the K factors you enter) or the *First-Order
  Method* (Appendix 7.3). *Not chosen* keeps the K factors and the B1 switch of
  the Steel Frame Check as they are.
- **Lateral system** along X and, in 3D, along Y: none, a steel system not
  detailed for seismic (R = 3), OMF, IMF, SMF, OCBF, SCBF, EBF or BRBF. The
  dialog shows R, Ω0 and Cd of ASCE 7 Table 12.2-1. Ω0 (the larger of the two
  directions) makes the overstrength combinations of the direct analysis cases.
  AISC 341 member checks are applied for SMF, IMF, SCBF and OCBF; the others are
  checked against AISC 360 with a note.
- **SDS** — the 0.2 SDS D term of the overstrength combinations.
- **Ry** — expected to specified yield stress (AISC 341 Table A3.1).
- **Steel by shape family** — the grade of W, M, S, HP, tees, channels, angles,
  rectangular and round HSS and pipe: ASTM A36, A572 Gr. 50, A992, A588 Gr. 50,
  A500 Gr. B and C, A1085 or A53 Gr. B, each with its Fy and Fu (A500 and A53
  have their own values for round sections). *AISC Manual defaults* sets the
  preferred grades of Manual Table 2-4. A family left on *Project Fy / Fu* uses
  the values of the Steel Frame Check. A member can still take its own grade.
