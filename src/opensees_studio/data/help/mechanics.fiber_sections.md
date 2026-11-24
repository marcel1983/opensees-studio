---
title: Fiber sections: patches, layers and yielding
group: Mechanics
summary: Why a section made of fibres captures what an elastic one cannot.
see_also: define.material_library, assign.integration, define.material_tester
order: 140
---

A fibre section is a mesh of small areas, each tied to a uniaxial material. The
element integrates the material response over the section at every integration
point along the member, so:
- **axial force and bending interact** by construction (the neutral axis moves
  as the section yields), and
- **yielding, crushing and cracking are where they physically are** (the extreme
  fibre first), not a flag switched at the whole section.

# Parameters
- **Patches** — rectangular or circular regions of one material, divided into
  `n_fib_y × n_fib_z` fibres. More fibres is more accuracy and more cost; 8×8 to
  16×16 over a rectangular section is a working range.
- **Layers** — straight rows of reinforcement, each with an area, a material and
  a position (y, z).
- **Templates** in the fibre section editor: a W-shape, and two reinforced
  concrete ones. **RC rectangular**: the confined core inside the bar centrelines,
  four unconfined cover strips, top and bottom bars and optional side bars (depth
  h along local y, width b along z, cover to the bar centres). **RC circular**:
  a confined core disc, an unconfined cover ring and bars evenly around at the
  cover. Choose the confined concrete (e.g. `Concrete04` with Mander's confined
  strength), the cover concrete and the steel.
- **Materials** — the confinement of the core (`Concrete04` with the confined
  properties) and the steel (`Steel02` with `b` for the post-yield slope) decide
  the section's ductility. The section itself has no stiffness beyond them.

# Mechanics
- A fibre section is a **nonlinear** section: it needs a non-linear static,
  pushover or transient case, with enough steps and Newton iterations. A single
  linear step will not follow it.
- Moment-curvature is the section's response; the member's moment distribution
  comes from the integration rule along its length (Assign → Frame → Beam
  Integration), which must have enough points to sample the curvature.
- The app's Material Tester runs a single material through a strain protocol —
  useful to see a `Concrete04` or `Steel02` curve before trusting a section.
