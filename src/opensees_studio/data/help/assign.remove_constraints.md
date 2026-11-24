---
title: Assign → Joint → Remove Constraints
group: Assign — joints
summary: Take the selected joints out of every equalDOF, rigid link and diaphragm.
see_also: assign.diaphragm, assign.rigid_link
order: 2210
---

Removes every equalDOF and rigid link that touches a selected joint, every
diaphragm whose retained node is selected, and the selected joints from the
diaphragms that list them (a diaphragm left without joints goes too). A storey
diaphragm keeps following its storey: select its retained node to remove it.
Undo puts everything back.
