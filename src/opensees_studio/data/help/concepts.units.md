---
title: Units and the solver
group: Mechanics
summary: OpenSees has no units; the application never converts behind your back.
see_also: concepts.model, analyze.run
order: 40
---

Every number you type is in **your** unit system, consistently: if lengths are
metres, forces are newtons and stresses pascals; if lengths are millimetres,
forces are newtons and stresses megapascals. The solver adds and multiplies
numbers and never checks them, so the only thing that matters is that one system
is used throughout.

- The project records two things: the **model units** its values are typed in,
  and the **display units** results are shown in (Options → Set Display Units).
  Changing the display units converts the numbers on diagrams, tables and plots
  — it never rewrites the model, and never re-interprets what you typed.
- **g** is 9.80665 m/s² in SI, 9806.65 mm/s² in millimetres, 32.174 ft/s² in US
  customary — the app picks the one matching your system when a dialog needs it.
- When a value is converted (an imperial shape into an SI project, for instance)
  the dialog shows both the published and the converted value, and says so.

The classic mistake is mixing them: a mass in kg with a stiffness in N/mm gives
a period that is wrong by a factor of 1000. There is no unit checking to catch
it — only a sanity check on the period, which the modal case reports.

# Typing numbers
Every decimal field takes a plain number, scientific notation (`1e-10`,
`2.9e4`) or basic arithmetic: `+`, `-`, `*`, `/` and parentheses, for example
`6.5/2`, `3*4.2 + 0.15` or `(12 - 0.3)/4`. The expression is worked out when
you press Enter or leave the field, and the field then shows the result. A value
outside the field's range, a division by zero or an unfinished expression is not
accepted: the field goes back to its last valid value. Units are not part of the
expression, so `2*3` in a length field is 6 in the model's length unit.
