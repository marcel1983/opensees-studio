---
title: Options → Solver
group: Options
summary: Which engine solves the model, and where OpenSeesPy is installed.
see_also: analyze.run
order: 1930
---

OpenSees Studio models; an **engine** solves. The engine is **OpenSeesPy 3.8**,
a separate program with its own license, and the application can be installed
without it. Without a solver you can still model, export the OpenSeesPy script
or IFC, and write a report; Run, Check Model Stability and the Material Tester
wait for one. The log says at start whether a solver was found.

# Where OpenSeesPy comes from
- **Installed with OpenSees Studio** — in the application's own Python
  environment (`pip install opensees-studio[opensees]`, or a bundle that
  carries it).
- **Another Python** of the same version as the application (3.12) that has
  `openseespy` installed (`python -m pip install openseespy==3.8.0.0`). Choose
  its interpreter; the application asks it where its `openseespy` is, without
  starting OpenSees.
- **A folder** that contains the `openseespy` package (a `site-packages`
  folder).
- **Download OpenSeesPy from PyPI** — the button shows the OpenSeesPy license
  first and downloads only once you tick that you accept it. It fetches the two
  files OpenSeesPy publishes for this platform (Linux x86-64, Windows, macOS on
  Apple silicon), checks each against its published SHA256 digest, unpacks them
  into the application data folder and selects that folder. Cancel stops it
  and leaves nothing behind.
The status line says whether that choice is usable and which version it finds.
When the application's own environment has OpenSeesPy, it is used and another
folder is not.

# License
OpenSeesPy is free for research, education and internal use; commercial
redistribution needs a license from its authors. OpenSees Studio is free
software and does not distribute OpenSeesPy, not even in its downloadable
bundle: each user installs it, from the place its authors publish it, and should
check that their use fits its terms.

# Engine
The **Engine** list shows every engine installed, with the analysis types it
runs.

- **OpenSeesPy** — every analysis type: static, modal, transient, pushover,
  response spectrum, influence lines; nonlinear materials, fibre sections,
  hinges, bearings, shells. A separate download with its own license.
- **PyNite** — ships with OpenSees Studio (MIT license), no download. Linear
  static cases of elastic frames (elastic sections, Euler-Bernoulli) and
  trusses (elastic material), with nodal, uniform, trapezoidal, floor and
  point loads, self weight, moment and torsion releases and support springs;
  **P-Delta** when a member uses the PDelta transformation. It matches
  OpenSeesPy to rounding on those models. It refuses, with a message saying
  what, anything else: shells, zero-length elements, bearings and links,
  constraints, rigid links and diaphragms, partial fixity, end offsets, shear
  areas, surface / temperature / imposed-displacement loads, corotational
  members and corotational trusses (a `CorotTruss` needs OpenSeesPy with an
  iterative algorithm such as Newton; PyNite would solve it as a linear truss),
  and a joint lying inside a member it is not connected to (PyNite
  would connect it — use Edit → Divide Frames at Joints). Its P-Delta iterates
  on the whole model, so it is closer to the exact second-order answer than a
  single OpenSees element with the PDelta transformation, which leaves out the
  member's own P-delta. More engines plug in as Python packages (the `opensees_studio.engines`
entry point). A case of a type the chosen engine does not run is refused when
you run it, with a message naming the engine and what it does run. The
stability check and the Material Tester always use OpenSeesPy, so they stay
available (or not) whatever engine you choose.
