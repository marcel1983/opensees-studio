---
title: Shells and plates: membrane, bending and thickness
group: Mechanics
summary: Why a shell takes a plate section, and what the four nodes mean.
see_also: define.create_shell, define.section_library
order: 130
---

A `ShellMITC4` is a four-node shell: it carries in-plane membrane forces and
out-of-plane bending at once. Walls, slabs and shear walls are modelled with it.

# Parameters
- **The four nodes** — the element's own geometry. They must be listed around
  the face (counter-clockwise about its normal); Define → Create Shell from 4
  Nodes derives that order from the coordinates, because a scrambled list gives
  an inverted or twisted element.
- **The plate section** — `ElasticMembranePlateSection` carries E, ν, the
  thickness h and the density. OpenSees wants a *section* for a shell, not an
  nDMaterial: the thickness is the section's business, not the material's.
- **E and ν** — the membrane stiffness is E·h/(1-ν²) and the bending stiffness
  D = E·h³/(12(1-ν²)). Note the cube: halving the thickness makes the slab eight
  times more flexible in bending and leaves the membrane behaviour almost
  unchanged.

# Mechanics
- A mesh coarse in bending is **stiffer** than reality: it is a displacement
  formulation, so it approaches the exact answer from below. Refining converges
  (the application's test suite checks exactly this against the classical plate
  solution).
- The element has six DOF per node, including a drilling rotation that carries
  no stiffness of its own. Out-of-plane and drilling DOF have to be restrained
  where the structure is a genuine plate: the portal frame wizard does it for a
  plane frame, and a wall with free edges usually needs the drilling DOF tied.
- In a 3D model a plane frame is a mechanism unless its out-of-plane DOF are
  restrained; that is what the wizard's *restrain the out-of-plane degrees of
  freedom* option is for.
