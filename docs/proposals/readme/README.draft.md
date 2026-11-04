<p align="center">
  <img src="docs/logo.svg" alt="OpenSees Studio" width="640">
</p>

<p align="center">
  A SAP2000-style desktop GUI for
  <a href="https://openseespydoc.readthedocs.io/">OpenSeesPy</a>,
  for structural and earthquake engineers who want visual modeling
  without leaving the OpenSees ecosystem.
</p>

<p align="center">
  <em>Status: pre-alpha. File formats and APIs may change between releases.</em>
</p>

<p align="center">
  <strong>English</strong> · <a href="README.es.md">Español</a> ·
  <a href="docs/features/README.md">Features</a> ·
  <a href="docs/tutorials/README.md">Tutorials</a> ·
  <a href="docs/verification-manual.md">Verification</a> ·
  <a href="docs/roadmap.md">Roadmap</a>
</p>

---

![OpenSees Studio main window](docs/screenshots/main_window.png)

## Why OpenSees Studio

OpenSees is the reference nonlinear FEM solver for earthquake engineering, but
its interface is a script. OpenSees Studio puts a visual model on top of it:
draw on a grid, assign properties through dialogs, run, and read the results on
the model, while every project stays a plain `.osmodel` JSON file that you can
diff in Git and drive from Python.

The data model (`opensees_studio.core`) has no GUI dependency, so the same
project can be built from a script or a notebook.

## Features at a glance

| Module | What you get | Details |
|---|---|---|
| Modeling | Grids (Cartesian and radial), joints, frames, trusses, shells, zero-length elements, meshing, replicate, groups, storeys, wizards | [modeling](docs/features/modeling.md) |
| Materials and sections | OpenSees uniaxial and nD materials, fibre sections, Section Designer, AISC v16 library, RC walls, tapered members, Material Tester | [materials-sections](docs/features/materials-sections.md) |
| Loads and assignments | Supports and springs, frame/area/temperature loads, self weight, equivalent lateral force, joint patterns | [loads-assignments](docs/features/loads-assignments.md) |
| Analysis | Static, modal, pushover, time history, response spectrum, influence lines, combinations and envelopes, batch runs | [analysis](docs/features/analysis.md) |
| Earthquake engineering | Ground-motion catalog, target spectra by code, isolators, modal damping | [earthquake](docs/features/earthquake.md) |
| Model checks | Check Model, stability (mechanisms), duplicates | [model-checks](docs/features/model-checks.md) |
| Results and reporting | Deformed shape, mode animation, diagrams, tables, results database, section cuts, PDF/HTML report | [results-reporting](docs/features/results-reporting.md) |
| Design | AISC 360-16 steel frame check (LRFD/ASD) | [design](docs/features/design.md) |
| Interoperability | DXF, SAP2000 `.s2k`, IFC4, Tcl import; OpenSeesPy script export | [interoperability](docs/features/interoperability.md) |

Press **F1** in the application for the page of the dialog you have open.

## Install

**Desktop bundle (no Python needed).** Download the archive for your system
from the [releases](../../releases), unpack the whole folder and run
`OpenSeesStudio`. The OpenSees solver has its own license and is installed once
from **Options → Solver**.

**From source.**

```bash
git clone https://github.com/marcel1983/opensees-studio.git
cd opensees-studio
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[gui,dev]"                          # Python 3.12 exactly
python -m opensees_studio
```

Headless use, solver options and platform notes:
[install guide](docs/user-guide/install.md).

## First steps

1. **File → New** and pick units; **Define → Grid Wizard** for the grid.
2. Draw frames on the grid; **Assign → Joint → Restraints** for supports.
3. **Define → Materials / Sections**, then assign them to the members.
4. **Define → Load Patterns** and **Analysis Cases**; **Analyze → Run** (F5).
5. **Display** menu for deformed shape, diagrams and tables.

Then follow the [tutorials](docs/tutorials/README.md) or open one of the
bundled [examples](examples/README.md).

## Verification

Every release is checked against closed-form and published solutions (beams,
trusses, P-Δ, modal, time history, response spectrum, plates, fibre sections,
AISC design examples). See the [Verification Manual](docs/verification-manual.md),
generated from real runs and enforced in CI.

## For developers

- [Architecture](docs/architecture.md): MVVM plus a service layer; `core` imports
  no Qt and no OpenSeesPy, and analyses run in a child process.
- [Testing and CI](docs/developer/testing.md) · [Profiling](docs/developer/profiling.md)
  · [Packaging](packaging/README.md) · [Contributing](CONTRIBUTING.md)

## Contributing

Feedback from engineers who use OpenSees is the most valuable contribution:
a feature that is "almost right", a result that disagrees with your script, or
a reproducible model. Code, tests and documentation are welcome as pull
requests to `main`; see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[AGPL-3.0](LICENSE). Free to use, study and modify; if you distribute it or run
it as a network service, you must publish your changes under the same
license. OpenSeesPy is a separate program with its own license.

Copyright © 2026 Ozan and contributors.
