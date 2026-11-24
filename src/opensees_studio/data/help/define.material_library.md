---
title: Define → Material Library
group: Define
summary: The uniaxial and nD materials the model can use.
see_also: define.section_library, mechanics.fiber_sections, define.material_tester, define.default_materials
order: 960
---

Materials are the constitutive laws the elements and fibre sections point at.

- **From library…** inserts a *typical construction material*: specified concrete
  strengths (f'c from 17 MPa up, with ACI's 0.002 and 0.003 strains), the
  reinforcing grades ACI permits (280, 420, 550 and A706's 690), the structural
  steels AISC tabulates (A992, A36, A572 Gr. 50, A500 Gr. B) and masonry at its
  usual specified strengths (Em = 700 f'm for clay masonry, 900 f'm for concrete
  block). Each row names the clause it comes from, and the picker shows the
  published value beside the one that will be inserted, converted to this
  project's units. Masonry enters as an elastic material: an existing wall's
  nonlinear backbone is a per-building decision, not a table lookup.
- **Uniaxial** (used by trusses, zero-length elements, links and fibre sections):
  `Elastic`, `ElasticPP`, `Hardening`, `Steel01`, `Steel02`, `Concrete01`,
  `Concrete02`, `Concrete04`, `Hysteretic`, `HystereticSM`, and through one
  generic form, in the order and with the names of the OpenSeesPy manual:
  - steel and concrete: `ReinforcingSteel`, `Concrete06`, `Concrete07`,
    `ConcreteCM` (Chang-Mander: Tsai's envelope in compression and tension,
    cyclic rules for RC under earthquake loading; `-GapClose` 1 closes cracks more
    gradually);
  - deterioration (plastic hinges): `ModIMKPeakOriented`, `ModIMKPinching`,
    `Bilin`, `Pinching4` (a symmetric envelope);
  - dampers and rate models: `ViscousDamper`, `BilinearOilDamper`, `Viscous`,
    `BoucWen`. A dashpot answers the strain rate, so it acts only in a
    transient case: put it in a zero-length or link element, in `Parallel`
    with the spring it damps. Keep a `ViscousDamper`'s `K_el` realistic: when
    Cd / K_el is some 1e5 times shorter than the time step its internal
    integrator fails;
  - multilinear and gaps: `ElasticBilin`, `ElasticPPGap` (no force until the
    gap closes, then elastic up to Fy and plastic, the plastic strain widening
    the gap; Fy and gap of one sign, negative for a compression gap),
    `MultiLinear`, `ElasticMultiLinear` (a table of strain-stress points);
  - pile springs: `PySimple1`, `TzSimple1`, `QzSimple1`;
  - wrappers of other materials: `Parallel` (stresses added, optional factors),
    `Series` (strains added), `MinMax` (failure outside a strain range),
    `InitStrainMaterial`, `InitStressMaterial`, `Fatigue`. A wrapper is emitted
    after what it wraps, whatever the list order, and a missing or circular
    reference is reported before the run.
- **nD** (plane elements and shell layers): `ElasticIsotropic`,
  `ElasticOrthotropic` (Ex, Ey, Ez, the Poisson's ratios and shear moduli, a
  layer stiffer one way than the other), `J2Plasticity`,
  `PlasticDamageConcretePlaneStress`, and the plate wrappers a layered shell needs:
  `PlateFiber` (of a 3D material), `PlateFromPlaneStress` (of a plane-stress
  concrete, with its out-of-plane shear modulus) and `PlateRebar` (a uniaxial
  steel at an angle).

Every form row shows the parameter's OpenSees name and meaning; each material is
checked against the live solver, and the Material Tester runs any uniaxial one
(a wrapper together with what it wraps).
- A **catalog material** puts one of the gidopensees presets into the project
  with its unit-carrying defaults read out of the schema; the ones whose
  behaviour could not be verified against the solver refuse to be emitted rather
  than guess.

# Values that matter most
- `Steel02`: `Fy` (yield), `E0` (initial modulus), `b` (post-yield slope as a
  fraction of E0), and optionally `R0`, `cR1`, `cR2` for the transition curve.
- `Concrete04`: `fpc` (compressive strength, negative), `epsc0` (strain at
  peak), `fpcu`/`epsU` (crushing), and the Popovics parameters. For a confined
  core, use the confined strength and strain.
- `Elastic`: `E`. Everything else follows from the section.
