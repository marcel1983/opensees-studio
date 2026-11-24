---
title: Design → Steel Connections → Connection Checks (AISC 360 Chapter J)
group: Design
summary: User-defined weld, bolt, plate, block-shear and concentrated-force checks.
see_also: design.connections, design.gussets, design.column_splices, design.steel_check
order: 400
---

Lists, adds, edits and removes AISC 360 Chapter J connection checks.

- Choose the limit state: **fillet weld** J2.4, **bolt shear/tension** J3.1,
  **bearing/tearout** J3.6, **slip-critical** J3.4, **plate shear**
  J4.3/J4.4, **block shear** J4.5, **bearing strength** J7.1,
  **concrete bearing** J8, **groove-welded splice** J6, **flange local
  bending** J10.1, **web local yielding** J10.2, **web local crippling**
  J10.3, **web sidesway buckling** J10.4 or **web compression buckling**
  J10.5.
- **Fillers** J5: the weld check reports the J5.1a leg increase and the bolt
  shear check applies the J5.2 factor when a filler thickness is given.
- **Anchor rods** J9 use the J3 bolt tension/shear checks; the concrete
  embedment design follows ACI 318 and is out of scope.
- **Concentrated forces** J10 use the loaded flange and web dimensions. J10.1
  is reported as **not required** when `lb < 0.15 bf`; J10.4 is reported as
  **not required** when `(h/tw)/(Lb/bf)` exceeds 2.3 (restrained) or 1.7
  (unrestrained). The 50% reductions near the member end are applied and
  shown in the notes.
- **J10 fields by check**: J10.1 uses `Fyf`, `tf`, `bf`, `lb` and the distance
  to the end. J10.2 uses `Fyw`, `tw`, `k`, `lb`, `d` and the distance. J10.3
  (crippling) uses `Fyw`, `E`, `tw`, `tf`, `d`, `lb`, the distance and `Qf`.
  J10.4 uses `Fy`, `Sx`, `Mr`, `tw`, `tf`, `h`, `bf`, the unbraced length `Lb`
  (the **Bearing length lb / unbraced Lb** field) and the restraint. J10.5
  uses `E`, `Fyw`, `tw`, `h`, `Qf`, the distance and `d`.
- Enter the demand `Vu` or `Tu` and the fields the check uses. The dialog
  enables the relevant group; the other fields are not read.
- OK stores the list as one undoable step; the report and the calculation
  memory show the nominal and available strengths, the ratio, the status and
  the calculation steps.

The dialog is a design aid: it checks the limit state from the values you
enter, but it does not choose the plate, the bolts, the weld or the stiffener
for you. J10.6 panel zone is in the SMF joint table; the J10.7-J10.9
stiffener and doubler-plate design is not modeled.
