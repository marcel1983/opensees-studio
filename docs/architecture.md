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
`Needs.SELECTED_NODES`, `Needs.TWO_NODES` for exactly two joints, `Needs.TIME_SERIES`, …).
`ActionRegistry` builds the `QAction` objects from those tables, connects them and enables them; `MainWindow.action("file.save")`
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
| `LoadsController` | `loads` | Assign → point, imposed displacement, distributed, trapezoidal, frame point, temperature, tendon, surface and floor loads; joint patterns; Edit → Delete Loads |
| `MembersController` | `members` | Assign → section, material, geometric transformation, local axes, beam integration, releases, end offsets, insertion point, property modifiers, auto mesh; plastic hinge, RC wall, pile soil springs |
| `ExportsController` | `exports` | File → Export: OpenSees script, IFC, SAP2000 text, report, calculation memory. Gets `results` and `report_results` as hooks (the window owns the results) |
| `ImportsController` | `imports` | File → Import: DXF drawing (into the project), PORTICO, SAP2000 text, IFC and Tcl (a new project). Gets `confirm_discard` (the unsaved-changes prompt) and `apply_view_settings` as hooks |
| `LibraryController` | `library` | Define → material library, default materials, MC2010 concrete, friction models, material tester, ground motions, section library, concrete section, steel deck and section designer. Owns the two windows it keeps open (`material_tester_dialog`, `ground_motions_dialog`); gets `new_project` as a hook |
| `GroupsController` | `groups` | Define → Groups, Section Cuts; Assign → Assign to Group |
| `ModelToolsController` | `model_tools` | Edit → Delete selection, Interactive Table Editing, Check Model for Duplicates, Merge Joints, Divide Frames at Joints, Join Frames, Mesh. Gets `select_rows` (select a report row in the viewport) as a hook |
| `AreasController` | `areas` | Define → Create Shell; Assign → Shell Formulation, Area Springs, Edge Springs, Line Springs |
| `PatternsController` | `patterns` | Define → linear, path, function and constant time series; plain load pattern, uniform excitation, multi-support excitation. Gets `new_project` as a hook (a series can be defined with no project open); `Needs.TIME_SERIES` enables the patterns |
| `JointsController` | `joints` | Assign → restraints, masses, springs; EqualDOF, zero-length element and section, bearing, link (exactly two joints: `Needs.TWO_NODES`) |
| `GeneratorsController` | `generators` | File → New Model (units and a template) and New 2D Frame; Define → Create Portal Frame, Create Truss, Create Warehouse and Create Building: the wizard, the plan and its insertion as one undo step. Gets `confirm_discard` (a new model replaces the open one), `grid_wizard` (the grid-only template) and `front_view` (a 2D model face on). |
| `SelectController` | `select` | Select → all, invert, previous selection, the queries (joints, elements, supports, mass, self weight, loose joints, …) and the "By …" submenus, which it adds to the menu itself. Gets `action` (the window's `action(id)`): the menu enables three of its commands when it opens |
| `PropertyEditsController` | `property_edits` | No menu: what the Properties dock calls back with. One joint's mass, an element's type, material, section or fields, and the edits of several joints or elements in one undo step |
| `ViewportController` | `viewport` | View → Isometric, Top, Front, Right, Rotate, Spin, Parallel projection, Move Up/Down in List, Grid Line View, Hide/Isolate Selected, Invert Visible, Show All Objects. Owns the Level list of the View toolbar and the grid line being viewed (`grid_view`); gets `action` for the three commands it enables itself |
| `DrawingController` | `drawing` | Tools → Select, Draw Node, Draw Frame, Draw Truss, Quick Draw Frame, Draw Shell, Quick Draw Shell, Measure Distance. Builds each tool when it is first armed and owns the two Section boxes of the Tools bar. Gets `tools` (the window's `ToolController`), `check_select`/`check_measure` (the tool buttons are an exclusive group of the window) and `offset_dialog` (the open Move or Replicate window) |
| `GridsController` | `grids` | Define → Coordinate System/Grids, Grid Wizard; View → Show Grids and Show Grid Labels (each an undo step). Gets `new_project` (both dialogs work with no project open) and `sync_actions` (the window ticks its two checkable commands again) |
| `DisplayController` | `display` | Display → Show Deformed Shape, Animate Mode Shape, Show Force Diagram, Show Shell Contours, Time-History Plot and its animation export, Hysteresis Plot, Pushover Curve, Influence Line, Response Spectrum, Back to Model View; also the design ratios and the mechanisms of Check Model. Owns the dock of the open view (`dock`), what the canvas shows (`mode`) and the caption of the viewports. Also what a joint or a member says under the pointer, which follows the open view, and the member diagram windows (`member_windows`) a right-click opens on a force diagram or a deformed shape. Gets `results` (the window's `ResultsSession`), the three overlays (`diagram`, `contours`, `ratios`), `canvases`, `busy`, `select_rows`, and for the member windows `results_for_key`, `show_results`, `display_units` and `set_display_units` |
| `ModelLockController` | `model_lock` | Options → Lock Model and the padlock of the status bar (which it owns). Locks the model when results arrive and, after every push, undo and redo, compares the model's fingerprint with the locked one: a change the user does not unlock for is taken back. Gets `results`, `drop_results` (unlocking discards the results of the session) and `action` |
| `UnitsController` | `units` | Options → Set Display Units and the unit picker of the status bar (which it owns). The choice is `project.meta.display_units`; the window's `refresh` hook re-draws the results panel, the open view and the member windows. |
| `AnalysisController` | `analysis` | Analyze → Cases, Check Model, Check Model Stability, Run, Run All Cases, Run Selected Cases, and Auto-mesh Frames Before Run. Owns the Run dialog while it is open and the reports of a failed run and of a stability check. Gets `runner` and `stability` (the window's `AnalysisRunner` and `StabilityChecker`, whose signals the window connects to it), `results`, `finished`, `new_project`, `select_rows`, `show_mechanism` and `console`. The results of a run arrive at `ResultsViewController` |
| `ResultsViewController` | `results_view` | What a run leaves behind and which of it is on screen: receives each case's results and the one to show, Display → Show Results Of, Show Reactions, Reactions Table, Reactions…, Analyze → Delete All Results, and the results a batch stored for the model. Owns the Results and Reactions panels and the Case list and step arrows of the View toolbar (the window places them). Gets `results`, `lock` and `unlock` (the model lock), `set_caption` and `back_to_model` (the Display controller), `show_reactions_dock` and `action`. |
| `FilesController` | `files` | File → New Blank 3D Model, New 2D Truss, Open, Open Recent, Save, Save As, Project Information, Run Batch; the autosaved recovery copy and the recovery of a never-saved project. `confirm_discard(action)` is the one unsaved-changes prompt (New, Open and the window's `closeEvent` call it); `save` and `save_as` return `True` when the file was written. Gets `recent` (the list the start page shares), `recent_changed`, `busy`, `store_view`, `restore_view`, `offer_stored_results` and `is_running`. Quit stays in the window (`closeEvent`); New Model and New 2D Frame are `GeneratorsController`. |
| `VisibilityController` | `visibility` | What a viewport draws: View → Visibility, Show Extruded Sections, Show Local Axes, Color By and Colors; Display → Display Options and Show Load Assigns. It changes the `ViewSettings` of the focused viewport and keeps the ticks truthful (`sync_actions`); the ticks are the window's actions, handed over with `attach` (one or more per field). `store_in_project` and `restore_from_project` carry the primary viewport in the project file. Gets `main_canvas`. |

`DesignController` is the example of the named hooks: it is created with
`results` (the case results computed on the project as it is now) and
`show_ratios` (the ratio overlay and its legend dock, which belong to
`DisplayController`), and `tests/gui/test_design_controller.py`
runs it with a plain `QMainWindow` and two lambdas.

The results in memory are not attributes of the window either:
`viewmodels.results_session.ResultsSession` (`window.results`) holds the
results on screen (`latest`), the case results the combinations are built from
(`cases`) and the ones kept for the report only (`extra`), and answers what the
window and the controllers ask of them (which are current for the model, the
caption, the static result or one bound of a combination, the diagram of a
component, the reactions). It has no widget, and
`tests/gui/test_results_session.py` uses it without a window.

`MainWindow` is being emptied this way, one area per pull request; it keeps
the layout, the docks and the wiring.

## Wizards and generated models

A wizard does not edit the project. Its geometry lives in `core` as a pure
function (`core.frames.build_portal_frame`, `core.trusses.build_truss`,
`core.templates`, `core.warehouse.plan_warehouse`,
`core.building.plan_building`), and what the project gains
is collected in a `core.generated.GeneratedModel`: materials, sections, joints,
members, groups, storeys, diaphragms, a grid, cases, loads, combinations, the
mass source and the design settings. One function inserts it,
`commands.generated.insert_generated(vm, model, text=...)`:

1. `model_problems` checks the model against the project (ids already taken,
   a member whose section, material or joint exists nowhere, a diaphragm
   without its joints or its storey, a mass source naming a pattern that is not
   there, a grid name in use) and raises before anything is pushed;
2. the parts go in as one macro, so one Ctrl+Z takes the whole structure back;
3. if a command still refuses, the macro is undone and removed from the stack.

A script uses `GeneratedModel.apply(project)` instead, with no undo stack.

## Seismic codes

The equivalent lateral force method (Define → Seismic Loads, and the
earthquake of the warehouse and building plans) asks a registry, never a code's
key. Each code is a `SeismicCode` in a module of its own under
`core/seismic_codes/` (`asce7_16`, `tbdy2018`, `rnc07`, `nscm2021`) and an entry
in `SEISMIC_CODES`. A code gives:

- `base_shear(p, weights, heights)`: the base shear, one force per storey, the
  coefficient and the clause that governs, as a `BaseShear`;
- `approximate_period(system, height_m)` and its `period_systems`, or an
  `ElfError` when the code has no empirical period (RNC-07);
- `height_limit(p)`: the tallest building the static method is allowed for;
- what it asks for: `hazard` (`"spectral"`, SDS and SD1, or `"a0"`, a0 and a
  soil class), `inputs` (the `ElfParameters` fields it reads), its labels, its
  soils and importance classes, its accidental eccentricity.

`core.equivalent_lateral` gathers the storeys, their weights and heights (what
no code changes) and hands them over; the Seismic Loads dialog enables its
fields from `inputs`. Adding a code is a new module, its entry in the registry
and a test against a worked example of the code
(`tests/unit/test_seismic_codes.py` shows an unknown code going through the
generator untouched).

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
