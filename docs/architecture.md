# Architecture

## Layering

OpenSees Studio uses a strict **MVVM + service layer** architecture. Dependencies
flow in **one direction only**: outer layers may depend on inner layers, never
the reverse.

```
┌─────────────────────────────────────────────────────────────────┐
│  views/         Qt widgets, dialogs, 3D canvas — PySide6 only   │
│       ▲                                                          │
│       │ signals/slots, viewmodel binding                         │
│  viewmodels/    Qt-aware adapters, QUndoStack, selection state   │
│       ▲                                                          │
│       │ pure Python calls                                        │
│  services/      OpenSeesRunner, PersistenceService, Results      │
│       ▲                                                          │
│       │                                                          │
│  core/          Project, Node, Element, Material — pure Python   │
│                 NO Qt imports. NO openseespy imports.            │
└─────────────────────────────────────────────────────────────────┘
```

### Why this matters

- The `core` package is testable without a display server, without OpenSees,
  and without Qt. CI runs `pytest tests/unit/` in milliseconds.
- Replacing OpenSeesPy with another solver (e.g. `xara`, a future fork) only
  touches `services/opensees_runner.py`.
- A future CLI or Jupyter frontend reuses `core` and `services` unchanged.

## Package map

| Package | Responsibility | Allowed imports |
|---|---|---|
| `core` | Domain entities and invariants | stdlib, numpy, pydantic |
| `services` | I/O, solver invocation, persistence | core + stdlib + h5py + openseespy |
| `viewmodels` | Bridge core ↔ Qt; expose Qt signals; manage undo/redo | core, services, PySide6 |
| `views` | Pure UI; no business logic | PySide6, pyvistaqt, viewmodels |
| `commands` | `QUndoCommand` subclasses; mutate model via services | services, viewmodels |

## Menu commands

A command of the window is declared once, as an `ActionSpec` in
`views/actions/<area>.py`: its id (`"file.save"`), its text, the method that
runs it, its shortcut and what it needs to be enabled (`Needs.PROJECT`,
`Needs.SELECTED_NODES`, …). `ActionRegistry` builds the `QAction` objects from
those tables, connects them and enables them; `MainWindow.action("file.save")`
returns one. The spec tables are plain data with no Qt import, so a unit test
checks that every command has a handler and a help page.

The migration is by menu: File, Design and parts of Edit, Define and Assign
are declared this way, the rest is still built by hand in
`MainWindow._build_actions`. A declared action is also stored as `_act_<name>`,
the name the ribbon layout, `core.help.ACTION_TOPICS` and the icon files use; a
command that had another name before it was declared keeps it through
`legacy_attribute`.

## Controllers

What a group of commands *does* lives in a controller, not in `MainWindow`:
`views/controllers/<area>.py` holds a `QObject` that is given a `Shell` — the
window as the parent of its dialogs, the view model, the focused canvas, the
log and "refresh the commands" — and keeps the state of its area (the
clipboard and the open Move/Replicate window, for `TransformsController`).
Whatever else it needs from the window arrives as a named constructor argument
(`arm_measure`, `release_measure`), so the coupling is visible where the
controller is created. A command's spec names the controller method as its
handler: `"transforms.move"` is `window.transforms.move`.

| Controller | Window attribute | Commands |
|---|---|---|
| `TransformsController` | `transforms` | Edit → Copy, Paste, Move, Replicate, Mirror, Extrude |
| `BuildingController` | `building` | Define → Storeys, Mass Source, Seismic Loads; Assign → Diaphragm, Rigid Link, Remove Constraints |
| `DesignController` | `design` | The Design menu (19 commands): basis, Direct Analysis, notional loads, members, steel and concrete checks, connections, base plates, footings |

`DesignController` is the example of the named hooks: it is created with
`results` (the case results computed on the project as it is now) and
`show_ratios` (the ratio overlay and its legend dock, which belong to the
window's post-processing display), and `tests/gui/test_design_controller.py`
runs it with a plain `QMainWindow` and two lambdas.

`MainWindow` is being emptied this way, one area per pull request; it keeps
the layout, the docks and the wiring.

## Wizards and generated models

A wizard does not edit the project. Its geometry lives in `core` as a pure
function (`core.frames.build_portal_frame`, `core.trusses.build_truss`,
`core.templates`, `core.warehouse.plan_warehouse`), and what the project gains
is collected in a `core.generated.GeneratedModel`: materials, sections, joints,
members, groups, a grid, cases, loads, combinations. One function inserts it,
`commands.generated.insert_generated(vm, model, text=...)`:

1. `model_problems` checks the model against the project (ids already taken,
   a member whose section, material or joint exists nowhere, a grid name in
   use) and raises before anything is pushed;
2. the parts go in as one macro, so one Ctrl+Z takes the whole structure back;
3. if a command still refuses, the macro is undone and removed from the stack.

A script uses `GeneratedModel.apply(project)` instead, with no undo stack.

## Threading and the analysis process

The Qt main thread owns all widgets. OpenSees never runs in it:

- **Analyses** run in a child process. `viewmodels.AnalysisRunner` writes the
  pre-run snapshot and starts `python -u -m opensees_studio.run --project
  <snapshot> --cases <ids> --out <dir>` (the argv comes from
  `child_cli.analysis_cli_command()`, so frozen bundles re-enter themselves).
  The CLI prints one JSON object per line (`log`, `progress`, `case_started`,
  `case_finished`, `error`) and writes results through `services.result_store`
  (HDF5 + `manifest.json`); a hard exit inside OpenSees cannot take the window
  down, and Cancel kills the process.
- **Analyze → Check Model Stability** uses the same entry point with
  `--project <snapshot> --check-stability`: the child builds the model, captures
  the sparse initial stiffness through `PythonSparse` (`services.stability`),
  diagnoses it with a dense reference up to 1 200 equations or a shifted sparse
  eigenvalue search above that, and prints one `stability` line whose report
  `viewmodels.StabilityChecker` turns back into a `StabilityReport`. It also
  streams `stability_progress` phases; the checker can terminate the child and
  the GUI disables the check while it runs. `tools/stability_bench.py` builds
  the reproducible frame/truss families.
- **Batch runs** (File → Run Batch…, `python -m opensees_studio.batch`) start
  the same CLI on each project file itself (no snapshot: the file is not open),
  with `--out <stem>_batch_results --record-db <stem>_results.sqlite`, so the
  child also fills the results database. `services.batch` plans the jobs and
  writes the summary and `batch.json` (the model fingerprint the results belong
  to); `viewmodels.BatchRunner` drives several `QProcess` children at a time,
  the CLI a thread pool of subprocesses. File → Open loads the stored results
  when the fingerprint still matches.
- **Custom Python blocks** (Define → Custom OpenSees Commands) run only where
  someone trusted them. The GUI asks when a file is opened and passes
  `--allow-custom-commands` to every child it starts; without the flag the CLI
  refuses a project with enabled blocks (exit 3), and a batch skips it unless
  the user ticks *Run custom Python blocks* or passes the flag.
- **Material Tester** (Define → Material Tester) uses the same CLI with
  `--project <tmp> --material-test <id> --material-protocol <json>`: the
  material and the ones it wraps go to a temporary project, the child prints one
  `material_test` line with the stress-strain history
  (`services.material_tester.test_uniaxial_material_in_child`, a blocking
  `subprocess.run` under the wait cursor). An `error` line keeps the
  exception's type in `error_type`; any other exit is reported with its code and
  the stderr tail.
- `OPENSEES_STUDIO_IN_PROCESS=1` (`child_cli.in_process_mode`) runs all three in
  process instead, for debugging.

## Axes and the solver frame

Z is the elevation axis of every model. A 3D model uses X, Y and Z as they are;
a 2D model lives in the global **X-Z plane** (nodes at y = 0, DOFs Ux, Uz, Ry in
the node's storage slots 0, 2, 4). OpenSees' 2D models are in its own x-y
plane, so `core.plane` is the one mapping between the two: OpenSees receives
(X, Z) as its (x, y), and its in-plane rotation `rz` is a rotation about -Y, so
a 2D rotation or moment changes sign on the way (`dof_signs`). The runner emits
coordinates, hidden nodes, `-jntOffset` and `-orient` vectors, nodal loads and
displacement control through it, and applies the sign to every result it
reads, so result arrays keep OpenSees' DOF order with global signs. Files below
schema 3 store 2D models in the X-Y plane; `persistence.load_project` rotates
them +90° about X (`migrate_2d_payload_to_xz`).

## Persistence

- Project files: `*.osmodel` — a JSON document validated by Pydantic models.
  Human-readable, diff-able, version-controllable.
- Results: one HDF5 file per case plus `manifest.json` in the run's output
  directory (`services.result_store`, float64, lossless), rebuilt with
  `load_results`. Node results are in OpenSees' DOF order with global signs.
- Schema: `schema_version` 3 (2D models in the X-Z plane). A newer file is
  refused; older ones are migrated on load and saved as 3.

## OpenSeesPy command sequencing

`OpenSeesRunner` always emits commands in this order; the model layer enforces
that all required pieces exist before a run can be requested:

1. `wipe()` and `model('basic', '-ndm', ndm, '-ndf', ndf)`
2. `node(...)` for every node
3. `fix(...)` for every restrained DOF
4. `uniaxialMaterial(...)` / `nDMaterial(...)`
5. `section(...)` (if used)
6. `geomTransf(...)` for frame elements
7. `element(...)` for every element
8. `timeSeries(...)`
9. `pattern(...)` with nested `load(...)`
10. `recorder(...)`
11. `system / numberer / constraints / integrator / algorithm / analysis`
12. `analyze(...)`

Any deviation from this order is a runtime error in OpenSees. The runner
asserts the order at the service boundary; the UI never has to think about it.
