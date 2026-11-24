---
title: Define → Steel Deck Slab Wizard
group: Define
summary: A concrete slab on a ribbed steel deck, as a shell stiffer along the ribs.
see_also: tools.draw_shell, define.section_library, define.material_library
order: 1020
---

A slab cast on a steel deck bends and stretches much more stiffly along the
ribs than across them. The wizard works out that stiffness from the deck's
geometry and builds a shell section that has it in each direction, plus the
materials it needs, in one undo step. The drawing shows two ribs and the
centroid of the composite section along the ribs.

# Inputs
- **Profile** — typical trapezoidal (1.5, 2 and 3 in) and re-entrant decks fill
  in the geometry; check it against the manufacturer's table. Changing a value
  turns the profile into *Custom*.
- **Rib height hr**, **rib spacing** (the pitch, centre to centre of the ribs),
  and the **concrete rib width** at the bottom (on the sheet) and at the top of
  the rib: an open trapezoidal deck widens upwards, a re-entrant one narrows.
- **Sheet gauge** (22, 20, 18, 16 ga, SDI design thicknesses) or a thickness.
- **Concrete above the ribs tc**, the **concrete** and the **deck steel**: any
  isotropic material of the project, or a default one (its numbers only).
- **Ribs run along** — the shell's local 1 axis (from its first node to its
  second) or local 2. Draw the shells so that edge runs along the ribs.

# What it computes, per unit width
- **Along the ribs**: the uncracked transformed section — topping, ribs and
  sheet with n = Es / Ec — EA₁ and EI₁ about its own centroid.
- **Across the ribs**: the topping alone, EA₂ = Ec tc, EI₂ = Ec tc³ / 12 (the
  ribs are separate and the folded sheet carries nothing that way).
- **In-plane shear** Gc tc; **twisting** √(EI₁ EI₂) / (2 (1 + ν)) (Huber's
  orthotropic plate); **transverse shear** Gc times the concrete along the ribs,
  Gc tc across them.
- **Weight and mass**: the concrete of the topping and ribs plus the sheet.

The equivalent membrane and bending thicknesses (the solid concrete with the
same EA or EI) and the ratio EI₁ / EI₂ are listed to check against a hand
calculation.

# What it adds
- Two `ElasticOrthotropic` materials (the faces and the core) and the
  `PlateFiber` that wraps each one.
- A `LayeredShell` section of three layers — a thin face, the core, a thin face
  — through the real depth tc + hr (deeper only if the stiffness asks for it).
  OpenSees integrates each layer at its mid-plane, so the core carries membrane
  stiffness only and the faces the bending: their moduli are chosen so that a
  strip of the shell has exactly the EA and EI above in each direction (a wide
  plate, as an isotropic one, 1 / (1 - ν²) of them). νxy = ν √(Ex / Ey).
- The section's unit weight and the layers' density give the real self weight
  and mass.

The stiffness is elastic and uncracked; for a cracked slab, scale the moduli in
Define → Material Library. Edit or assign the section like any other plate
section.
