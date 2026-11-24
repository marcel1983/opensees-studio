---
title: Options → Set Display Units
group: Options
summary: The unit system results are shown in.
see_also: concepts.units
order: 1970
---

Chooses the unit system displayed numbers are converted to (reactions,
diagrams, tables, plots). It does **not** change the model: the solver works with
the numbers you typed, in whatever system they are consistent with.

- Change it to read a result in another system (a kN·m moment as kip·ft, for
  instance) without touching the model. Every open result view is refreshed on
  the spot: diagram values, displacement tables and curves all move together
  with their unit labels.
- Forces, moments (force × length) and stresses (force / length²) each convert
  with the factors their combination implies, so the numbers stay physical.
- It is also the system used when a dialog converts a value that arrives from
  outside (an imperial shape into the project).
- See **Units and the solver** for why the application never converts the numbers
  you type.

# The unit systems

Each one is coherent (the mass unit is force·s²/length, so F = m·a needs no
factor), and any of them can be the model's (File → New Model) or the display's:

| System | Length | Force | Mass | Stress |
|---|---|---|---|---|
| SI (m, N) | m | N | kg | Pa |
| SI (mm, N) | mm | N | t | MPa |
| SI (m, kN) | m | kN | t | kPa |
| SI (mm, kN) | mm | kN | kN·s²/mm | kN/mm² |
| Metric (m, kgf) | m | kgf | kgf·s²/m (9.81 kg) | kgf/m² |
| Metric (cm, kgf) | cm | kgf | kgf·s²/cm | kgf/cm² |
| Metric (m, tonf) | m | tonf (1000 kgf) | tonf·s²/m | tonf/m² |
| US (in, kip) | in | kip | kip·s²/in | ksi |
| US (ft, kip) | ft | kip | kip·s²/ft | ksf |
| US (in, lb) | in | lb | lb·s²/in | psi |
| US (ft, lb) | ft | lb | slug | psf |

With **kgf or tonf** the mass is *not* in kilograms: a mass of 1 kgf·s²/m is
9.81 kg. Material densities, joint masses and the mass source must be in that
unit; the default materials, the material library and every conversion the
program makes already are. Gravity is 9.80665 m/s², 980.665 cm/s². A SAP2000
text file in Kgf or Tonf now opens in its own system. Load values on the canvas
move to the unit a thousand times larger from a thousand up: 2500 kgf is shown as
2.5 tonf, 1500 lb as 1.5 kip.
