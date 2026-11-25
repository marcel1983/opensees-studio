# CLAUDE.md — Project context for Claude Code

This file is loaded automatically by Claude Code (and other AI coding
assistants) when working in this repo. It captures the architectural
rules, conventions, and gotchas that aren't obvious from reading the
code. Keep it short — link out instead of duplicating.

## Project: OpenSees Studio

A desktop GUI for OpenSeesPy. PySide6 + PyVista + pyqtgraph.

See [`README.md`](README.md) for the user-facing overview and
[`docs/architecture.md`](docs/architecture.md) for the long form
architecture document.

## Architecture

- **Pattern**: MVVM + service layer.
- **`core/`** — pure Python, no Qt, no openseespy. Pydantic v2 models for
  `Project`, `Node`, `Element`, `Material`, `Section`, `Load`, `Analysis`.
  Safe to import from a script, notebook, or future CLI.
- **`services/`** — `OpenSeesRunner`, persistence, deformation, spectrum,
  section_properties, animation_export. May import openseespy. No Qt.
- **`viewmodels/`** — Qt-aware adapters. `ProjectViewModel`,
  `AnalysisRunner`, `QUndoStack`.
- **`views/`** — Qt widgets, dialogs, 3D canvas. Never imports
  openseespy directly — go through a service.
- **`commands/`** — `QUndoCommand` subclasses for every model mutation.
- **Analysis execution** runs in a child process. `AnalysisRunner`
  (viewmodels) first writes the pre-run snapshot
  `<stem>.run-snapshot.osmodel` next to the project file (for a never-saved
  project `untitled.run-snapshot.osmodel` in the app data directory,
  override with `OPENSEES_STUDIO_DATA_DIR`), then starts
  `python -u -m opensees_studio.run --project <snapshot> --cases <id> --out <dir>`
  with `QProcess` (`sys.executable`, unbuffered so the stderr of a hard exit
  is not lost). The CLI (`opensees_studio/run.py`) prints
  one JSON object per stdout line (`log`, `progress`, `case_started`,
  `case_finished`, `error`), flushed per line; fd 1 is redirected to stderr
  first, so OpenSees native output never touches the protocol. Exit codes:
  0 every case ran (an early stop is a result), 2 Python-side analysis
  error with an `error` line, 3 invalid project or reference; anything else
  means the child died. Results travel through `services/result_store.py`
  (float64 HDF5 plus `manifest.json`, lossless) and are rebuilt with
  `load_results`. The snapshot doubles as crash recovery: on open, a
  snapshot newer than the file prompts to restore or discard; a normal save,
  a close, or New/Open replacing the project removes it
  (`ProjectViewModel._retire_run_snapshot`, only once the replacement has
  happened). `OPENSEES_STUDIO_IN_PROCESS=1` runs the previous
  threaded in-process worker (debugging, no cancel).
  Batch runs (File → Run Batch…, `python -m opensees_studio.batch`, `--batch`
  in a frozen bundle) start the same CLI per project file with `--out
  <stem>_batch_results --record-db <stem>_results.sqlite`; `services/batch.py`
  plans jobs and writes `batch.json` (the model fingerprint), and File → Open
  offers those results only while `model_fingerprint` still matches.
  Custom Python blocks run only with consent: without
  `--allow-custom-commands` (`child_cli.ALLOW_CUSTOM_COMMANDS_FLAG`) the CLI
  refuses a project with enabled blocks (exit 3) and the batch skips it. The
  GUI passes the flag to every child, because it asked when the file was opened;
  a new spawn site that builds a model passes it the same way.
  `OPENSEES_STUDIO_CLI_HARD_EXIT_AFTER=N` is a test-only hook that makes the
  CLI hard-exit with 255 after N progress lines.
  `OPENSEES_STUDIO_TEST_SKIP_BEARING_ORIENT=1` is a test-only hook that leaves
  `-orient` off bearings, so OpenSees itself hard-exits on a zero-length
  bearing. Solver-speed banners (the fullGenLapack "VERY SLOW" line) are kept
  out of the run log and stay in the stderr capture. Check Model Stability
  (`--check-stability`) and the Material Tester (`--material-test ID
  --material-protocol JSON`, one `material_test` line) use the same CLI, so no
  OpenSees call happens in the GUI process outside `OPENSEES_STUDIO_IN_PROCESS=1`.

The dependency direction is strict and one-way: `views → commands →
viewmodels → services → core`, and CI enforces it with import-linter
(`[tool.importlinter]` in `pyproject.toml`, run as `lint-imports`): the
layers, plus "core imports no Qt and no OpenSeesPy", "services import no Qt
except `services/qt_workers.py`", and "nobody outside `services/` imports
OpenSeesPy directly". Run it before pushing; a violation fails the `test`
job.

## Tech stack

- **Python 3.12** (`requires-python = ">=3.12"`), PySide6 (Qt 6), PyVista/VTK,
  pyqtgraph, OpenSeesPy 3.8.0.0, Pydantic v2, h5py, imageio[ffmpeg], ifcopenshell
  (File → Export/Import → IFC; imported only inside `services/ifc_export.py` and
  `services/ifc_import.py` when they run, so headless installs never need it).
- Why 3.12: the `openseespywin` and `openseespylinux` 3.8.0.0 wheels both
  declare `Requires-Python >=3.12`. On Windows the wheel ships a single
  `opensees.pyd` linked against `python312.dll`, so use 3.12 exactly (3.13
  cannot load it, even though pip will install it).
- Windows DLL fix: pin `openseespy==3.8.0.0` *and* `openseespywin==3.8.0.0`.

### Venv layout (Windows dev machine, as of 2026-09-18)

- `.venv/`: the live environment. Python 3.12.10, OpenSeesPy 3.8.0.0,
  created with `py -3.12 -m venv .venv` then `pip install -e ".[gui,dev]"`.
- `.venv/` is the only interpreter inside the repo. The py311 rollback
  environment (`.venv-old-py311/`) and the stale Python 3.9.1 `venv/` were
  deleted on 2026-09-18 once the lock file below was recorded.

### Reproducing the known-good environment

`requirements-lock.txt` is a `pip freeze --exclude-editable` of the live
`.venv` (Python 3.12.10 + OpenSeesPy 3.8.0.0), recorded after unit 299,
integration 55 and GUI 181 passed on it. It is a record, not a constraint
file: `pyproject.toml` stays the source of truth for dependency ranges. To
rebuild that exact state: `py -3.12 -m venv .venv`, then
`pip install -r requirements-lock.txt`, then `pip install -e . --no-deps`.
Regenerate the file only after all three suites pass on a changed environment.

## Conventions and gotchas

These are non-obvious things that are easy to break if you don't know:

- Z is the elevation axis of every model. A 2D model lives in the global
  **X-Z plane** (nodes at y = 0) with DOFs Ux, Uz, Ry in storage slots 0, 2, 4;
  OpenSees gets (X, Z) as its (x, y). Everything crossing that boundary goes
  through `core.plane`: `dof_indices`/`dof_signs` (a 2D rotation or moment is
  `-1` times the OpenSees value), `to_solver_coords`, `to_solver_vector3`. Never
  slice `coords[:ndm]` for OpenSees, and never assume 2D means "Y up". Result
  arrays keep OpenSees' DOF order with the global sign applied. 2D files below
  schema 3 are rotated on load by `migrate_2d_payload_to_xz`.
- `ForceComponent` is a plain `Enum`, **not** a `str`-Enum — a `str`
  mix-in breaks `.value` lookup inside PyVista renderers.
- `QObject.receivers()` in PySide6 takes a SIGNAL string, not a
  `SignalInstance` — avoid it.
- Qt mouse-event positions are LOGICAL pixels; VTK is DEVICE pixels.
  Scale by `widget.devicePixelRatioF()` when picking.
- `ModalResults.mode_shapes` is **1-indexed** (mode 1 → key `1`).
- `PathTimeSeries` field is `dt`, not `time_step`.
- `DiagramRenderer` must early-return when `abs_max == 0` — avoid
  divide-by-zero in the colour scale.
- The end-`j` sign is flipped in `extract_diagram_data` so axial /
  shear / moment diagrams are continuous across an element.
- `ProjectCommand` holds its view model by weak reference. Never store a
  strong reference to the view model (or anything owning its `QUndoStack`)
  on a command: the cycle through the stack corrupts the heap when the GC
  frees many of them (`0xC0000374`).
- Floating-point inputs use `views.float_field.FloatField` (full double,
  scientific notation, shortest round-trip display); do not add a plain
  `QDoubleSpinBox`, it rounds to its decimals.
- Unsaved-changes prompt. `MainWindow.closeEvent` confirms only a
  *user-initiated* close: one the window manager sent (`event.spontaneous()`)
  or `File → Quit`, which goes through `_on_quit`. A programmatic `close()`
  (test teardown, `closeAllWindows()` while shutting down) never prompts — a
  modal dialog with no event loop running wedges the exit. New, Open and Save
  are `FilesController` (`window.files`): `save` and `save_as` return `True`
  when the file was written, and `confirm_discard(action)` is the one prompt
  shared by close, New and Open so the three cannot drift apart.
- Model lock. Results lock the model (`ModelLockController.lock_for_results`,
  `window.model_lock`); the one place that enforces it is its `on_undo_index_changed`, which compares
  `model_fingerprint` with the locked one after every push, undo and redo and
  takes the change back when the user refuses to unlock. So a model change must
  go through the undo stack, and what the fingerprint leaves out
  (`FINGERPRINT_EXCLUDED_FIELDS` in `core.combinations`: combinations, design
  settings and checks, the saved viewport; plus display units and case names)
  is never asked about. A new project field that no result depends on goes in
  that set, or saving or editing it makes every result stale. `tests/gui/conftest.py` answers the
  unlock box with Yes for every test; `test_model_lock.py` sets its own answers.
- Draw tools work on an empty grid. Arming one never moves the camera, and a
  click lands on a grid intersection when one is near and otherwise where the
  view ray meets the working plane; with no grid lines at all the status line
  says there is no snapping (`tests/gui/test_draw_without_grid.py`). Only the
  Quick Draw tools need grid lines, and say so (`DrawingController`).
- `services.persistence._write_text_atomic` is the only way a project or a
  snapshot reaches disk; a save must never truncate the file the user
  already has. `load_project` refuses a `schema_version` newer than
  `SCHEMA_VERSION` instead of quietly rewriting it one version down.
- Start-up order. `app.run` shows `views.splash` right after the
  `QApplication`, then imports `views.main_window` (VTK, PyVista, the `core`
  package). Keep `app.py` and `views/splash.py` free of module-level imports of
  either (`tests/gui/test_splash.py` checks it), and load slow third-party
  libraries that one dialog needs (ezdxf) inside the function that uses them.
  Ribbon icons render on first display (`ribbon.icons._LazySvgEngine`).
- Interface text and Spanish. `views/i18n.py` translates a widget's text when
  it shows, by exact match against `data/i18n/es.json` (keys without the `&`
  accelerator, trailing `:`/`…` or `[unit]`). A new label, button, header, tool
  tip or `tr()` literal needs a catalog entry (`tests/unit/test_i18n_dialogs.py`
  fails otherwise, or add a symbol to its `TECHNICAL`); a text with a run-time
  value is `tr("Apply to <b>{n}</b> …").format(n=...)`, never an f-string. A
  combo box item is not translated unless wrapped in `tr()`, and only where the
  code reads the choice by index or data, never by `currentText()`.
- Menu commands are declared, not hand-built. A command is an `ActionSpec`
  in `views/actions/<area>.py` (id `"file.save"`, text, handler, shortcut, and
  the `Needs` that enable it); `ActionRegistry` builds the `QAction`, connects
  it and enables it, and also stores it as `_act_<name>`, which is how the
  ribbon layout, `ACTION_TOPICS`, the icon file and older tests find it. Ask
  for it with `window.action("file.save")`. The File and Design menus and parts of
  Edit, Select, View, Define, Assign, Analyze, Display and Options are migrated so far: when you add a command, add a spec
  instead of new lines in `_build_actions`, `_wire` and
  `_refresh_action_enablement` (use `needs=None` when the condition is not a
  `Needs` flag and set it in the window). `legacy_attribute` is only for a
  command that already existed under another name (`"assign.diaphragm"` is
  `_act_assign_diaphragm`); a new command never sets it. The spec tables import
  no Qt; `registry.py` is the only module there that does.
- New behaviour does not go into `MainWindow`. An area of the menus is a
  controller in `views/controllers/<area>.py`: a `QObject` that gets a `Shell`
  (the window as dialog parent, the view model, the focused canvas, the log,
  "refresh the commands") and owns its own state; anything else it needs from
  the window is a named constructor argument, never the window's attributes.
  Its commands name it in their spec (`handler="transforms.move"` is
  `window.transforms.move`). `TransformsController` (Copy, Paste, Move,
  Replicate, Mirror, Extrude) is the model to follow; `BuildingController`
  (storeys, mass source, seismic loads, diaphragms, rigid links) has no state
  at all, and `DesignController` (the whole Design menu) shows the hooks: it
  gets `results` (the current case results) and `show_ratios` (the overlay the
  window still owns) and runs in a test with no `MainWindow`; `LoadsController`
  assigns and deletes loads, `MembersController` assigns what a member is
  made of and its frame options, `JointsController` what holds a joint
  and what joins two (`Needs.TWO_NODES` is "exactly two joints selected"), and
  `PatternsController` defines time series and load patterns
  (`Needs.TIME_SERIES`; it gets `new_project` as a hook). `LibraryController`
  (materials, friction models, records, sections) owns the Material Tester and
  Ground Motions windows it keeps open. `ImportsController`
  (File → Import) gets `confirm_discard` and `apply_view_settings`, and
  `ExportsController` (File → Export) `results` and `report_results`; the window
  passes a hook as a lambda, so a test that replaces the window's method still
  reaches it. `SelectController` (the Select menu) adds its own "By …" submenus
  to the menu the window lays out, and gets `action` (the window's
  `action(id)`) for the commands that menu enables when it opens. A controller is
  not only for menu commands: `PropertyEditsController` is what the Properties
  dock calls back with an edit (its `on_…` callbacks are set to its methods).
  `ViewportController` (camera, working plane and Level list, grid line view,
  hide and isolate) owns the Level combo box the window puts in its toolbar;
  Spin and Parallel projection stay hand-built because they listen to `toggled`.
  `DrawingController` (the draw tools, Measure Distance, the Section boxes of
  the Tools bar) gets the window's `ToolController` as `tools`; the tool
  buttons stay an exclusive group of the window, which it ticks through
  `check_select` and `check_measure`. `GridsController` (coordinate
  systems, Grid Wizard, Show Grids) gets `new_project` and `sync_actions`.
  `DisplayController` (the post-processing views of the Display menu, the
  design ratios, the mechanisms of Check Model) owns the dock of the open view
  (`display.dock`), what the canvas shows (`display.mode`), the viewports'
  caption, the hover text and the member diagram windows; the window enables
  its commands from the results on screen (`needs=None`). The results in memory are `window.results`, a
  `viewmodels.results_session.ResultsSession` (`latest` on screen, `cases` for
  the combinations, `extra` for the report only): ask it, do not add a
  `_latest_results` to the window. `ModelLockController` (Options → Lock Model)
  owns the padlock of the status bar and gets `drop_results`.
  `UnitsController` (Options → Set Display Units) owns the unit picker of the
  status bar and gets `refresh`, the window's re-draw of what shows a number.
  `AnalysisController` (the Analyze menu: cases, Check Model, the stability
  check, Run and the batch doors) gets the window's `AnalysisRunner` and
  `StabilityChecker` as `runner` and `stability`; the window connects their
  signals to it. The results of a run go to `ResultsViewController`
  (`window.results_view`: the case on screen, the Results and Reactions
  panels, the Case list and step arrows of the View toolbar, Show Results Of,
  the reactions commands, Delete All Results), which owns those widgets; the
  window only places them. `FilesController` (New Blank, New 2D Truss, Open,
  Open Recent, Save, Save As, Project Information, Run Batch, the autosaved
  recovery copy) gets the recent-files list the start page shares and
  `store_view`/`restore_view` for the viewport a project carries; only Quit
  stays in the window (`closeEvent`). `GeneratorsController` (File → New Model
  and New 2D Frame; Define → Create Portal Frame, Create Truss, Create
  Warehouse, Create Building) gets `confirm_discard`, `grid_wizard` and
  `front_view`.
  `VisibilityController` (View → Visibility, Color By, Colors; Display →
  Display Options, Show Load Assigns; the viewport a project carries) does not
  build its ticks: they listen to `toggled`, so the window builds them and hands
  them over with `attach`, one or more per `ViewSettings` field. A controller's attribute must not be the name of a `QMainWindow`
  method (`window.geometry` would replace `QWidget.geometry()`):
  `tests/gui/test_action_registry.py` checks it, hence `model_tools`.
  The rest of the window is being moved out the same way.
- A frame member with `tension_only` is not a frame in OpenSees: its plan
  (`services.frame_members.TensionOnlyBar`) emits `element truss` on its own
  `uniaxialMaterial Elastic E 0 E*1e-6`, so no releases, offsets or loads along
  it (its self weight is nodal, `core.self_weight`; the runner refuses the rest),
  and the runner switches a Linear static case to Newton. Combinations of such a
  model do not superpose: `core.combination_cases` turns each one into its own
  static case (the warehouse plan does when its braces are tension only).
- What a material, section or element sends to OpenSees is its emitter
  (`services/material_emitters.py`, `section_emitters.py`,
  `element_emitters.py`, registered by type or class); a new kind is an
  emitter there, never a branch in `OpenSeesRunner`.
- A design check's tables in the calculation memory are one function in
  `services/memory_tables.py` (`MEMORY_SECTIONS`), rendered by
  `calc_memory` as HTML, Markdown, LaTeX and ODT; never a table per format.
- An unregistered material type is not a crash: `material_forms.form_for`
  returns a read-only placeholder, the same contract `section_forms` has.
- Never hardcode how the analysis child is spawned. Every spawn site
  (`viewmodels/analysis_runner.py`, `stability_checker.py`, `batch_runner.py`,
  `services/batch.py`, `services/material_tester.py` and the eigen re-exec in
  `run.py`) builds its argv from `child_cli.analysis_cli_command()`: a source install
  re-enters through `python -u -m opensees_studio.run`, a frozen bundle
  through its own executable plus `child_cli.CLI_FLAG`, which `__main__`
  dispatches back to `run.main`. A hardcoded `sys.executable -m ...` works
  in development and breaks every packaged build.
- An option added to an existing model keeps old files byte-identical by
  leaving its default out of the dump: `core._base.omit_when_default`
  (used by the beam integration rule and the numberer).
- `ops.wipe()` does not reset OpenSees' class-static scratch. `truss` shares
  its force vector and stiffness matrix between 3D ndf 3 and 2D ndf 3 and in
  2D never writes the rotation rows, so `OpenSeesRunner.build` clears them
  (`_clear_truss_scratch`) before a 2D ndf 3 model with trusses. Suspect the
  same when a result depends on what ran earlier in the process.
- Parametric generators plan, then insert. A wizard computes what the project
  gains without touching it and hands it over as a `core.generated.GeneratedModel`
  (materials, sections, nodes, elements, groups, storeys, diaphragms, grid,
  cases, loads, combinations, mass source, design settings); `commands.generated.insert_generated` checks
  it against the project first (`model_problems`: ids taken, references to
  something that is not there) and only then pushes one macro, which it takes
  back whole if a command still refuses (an error inside `redo` is lost by
  `QUndoStack.push`, and a macro that fails half way stays half applied). The
  portal frame, the truss, the New Model templates and the warehouse
  (`core.warehouse.plan_warehouse` → `WarehousePlan` →
  `commands.warehouse.insert_warehouse_plan`) all go through it: a new wizard
  does not open its own `beginMacro`; it is a method of `GeneratorsController`. Its groups
  are one per kind of member and section (`core.member_groups.section_groups`). In a
  generated warehouse a purlin or girt is pinned and is **not** a bracing point
  of the rafter or column unless it has a stabilising angle: the plan writes
  `SteelMemberDesign.length_minor`/`length_ltb`, because `core.design.members`
  would take every member framing in as a brace. Purlins, girts, braces and
  chord ties are built with `auto_mesh` off (`core.warehouse.WHOLE_MEMBERS`), or
  Run's auto-mesh cuts each X where its diagonals cross and the purlins under
  them. Wind (`core.wind`, SI whatever the project's units) is a net pressure per surface, positive pushing inwards;
  `core.warehouse.wind_loads` puts it on the purlins, girts or columns. A
  pressure that depends on two coordinates (the roof zones F to J and the side
  wall zones A to C of EN 1991-1-4) is a `wind.Surface` in `RoofLoad.zones` or
  `WindCase.wall_zones`, and wins over the one-coordinate profile. Several
  naves stand under **one** roof (one ridge over the whole width): wind and
  snow take `spec.width`, never `spec.span` per nave. A wind
  case carries its direction and its suctions, so the plan passes the wind
  cases as `peak_cases` to the combination generator: one sign each, never
  reversed. A warehouse without end wall columns must keep its node and element
  ids (the end walls are built last), or `warehouse_gable` changes. With
  `roof_structure="truss"` the top chord takes the rafter's place
  (`Warehouse.rafter_elements`); every purlin braces it, and the bottom chord is
  braced only at its tie lines. The cases the plan creates use
  `core.warehouse.CASE_SYSTEM` (UmfPack): BandGeneral takes tens of seconds per
  case on a model with that many released members. What a plan writes out of
  square roots, sines or dot products (purlin angle, loads, unbraced lengths)
  goes through `core.warehouse.portable` (12 significant digits): the last
  digit of those differs between processors and C libraries, and the committed
  examples must regenerate byte for byte on every CI runner.
  The earthquake is static (`core.warehouse_seismic`), one coefficient per
  direction (its own reduction factor, and either the plateau of the spectrum
  or the spectrum at that direction's period), as nodal loads from the weight
  lumped on each joint (`seismic_loads`); its cases go to the generator as role
  `E`, both signs, never as `peak_cases`. The wizard's Load combinations page
  edits the code's combinations by case *name*
  (`WarehouseLoads.edited_combinations`, `WarehousePlan.code_combinations`).
  Ash and snow (`core.snow`, a load per area of plan against the position
  across the roof) go on the purlins through `snow_loads`; the balanced and the
  drifted cases are alternatives, so the plan passes `ALTERNATIVE_ROLES` to the
  combination generator, and a code without a snow role (RNC-07) takes the one
  balanced case as a live load.
  `core.building.plan_building` is the same idea for a multi-storey building
  (`BuildingPlan`): Define → Create Building is `GeneratorsController.create_building`
  (`views/controllers/generators.py`), `BuildingWizard` and
  `commands.building.insert_building_plan`; a script calls `plan.apply(project)`.
  The wizard's last page plans the building with the planner the controller
  hands it, so what cannot be built is said before Finish.
  The slab is never modelled: it is `FloorLoad` panels, the mass is the mass
  source (`DEAD` plus the live load the code counts), and the earthquake is
  `core.equivalent_lateral` on the project's storeys (each code a
  `SeismicCode` of `core/seismic_codes/`, found in `SEISMIC_CODES`; the
  generator and the Seismic Loads dialog never branch on a code's key), applied at each
  diaphragm's retained node, which the plan puts at the centre of the floor's
  mass and exactly at the storey's elevation. The `±e` cases of one direction
  are alternatives: pass `EARTHQUAKE_DIRECTIONS` to the combination generator,
  or the 100 % + 30 % rule pairs `EQ X +e` with `EQ X -e`. The plan keeps a
  scratch copy of the project for ids and masses; what goes into it is a copy,
  never the object the plan returns.
- Cold-formed members go to AISI S100-16, not AISC 360. `steel_frame_check`
  dispatches on `section.shape` being a `ColdFormedShape`
  (`core/design/aisi_s100.py`, Direct Strength Method, ADR-0005): the elastic
  local and distortional loads are the finite strip signature curve
  (`core/design/fsm.py`, cached per shape), Fy and Fu come from the section's
  material, and the AISC 341 system does not act on them. Sheeting is a
  brace only through `SteelMemberDesign.sheeted_flange` (`"+"`/`"-"`: the side
  of the local axis the member bends along; a positive M2 compresses the +z
  flange, a positive M3 the -y one): braced where that flange is in
  compression, `R Mno` of I6.2.1 or Lb where it is in tension. The Warehouse
  Wizard writes it for purlins and girts from the wall's outward normal, with
  the sag rod lengths (design lengths only, no elements). The equations, factors
  and limits were checked against the text of S100-16 (reaffirmed 2020, with
  Supplement 2) and are pinned by the DSM Design Guide example and by closed
  forms against the finite strips. The φ and Ω of Chapters E to H hold only
  within Table B4.1-1 (`aisi_s100.dsm_limits`); outside it compression,
  flexure and shear take those of A1.2 (c), so `check_member` needs `ksi` (one
  ksi in the project's stresses) as well as `inch`.
- `Entity.id` is `PositiveInt` (>0). The sentinel `999999` is reserved
  for in-flight / temporary objects that haven't been assigned a real id.
- Eigen determinism rule. ARPACK keeps its random start vector across
  `ops.eigen` calls, so only the first ARPACK eigen call of a process is
  reproducible: a second call flips mode signs and rotates a repeated
  eigenvalue pair. Never pick an eigen solver by hand: take it from
  `core.modal.resolve_modal_solver` (dense `fullGenLapack` at or below
  `DENSE_EIGEN_MAX_FREE_DOF` = 500 free DOF, override with
  `OPENSEES_STUDIO_DENSE_EIGEN_MAX_DOF`, ARPACK above), and never add a
  second ARPACK eigen call to a process: the CLI (`run.py`) re-executes
  such a case in a fresh child, so new eigen-using case types must be
  listed in its `_uses_eigen` and `_routed_to_arpack`. Every mode shape
  that reaches display or combination must pass
  `orthogonalize_degenerate_modes` (repeated eigenvalues: the dense
  solver returns a mass-oblique pair) and `normalize_mode_sign` (tie
  tolerance 1e-9, lowest DOF index wins), as `_run_modal` does; record the
  solver used in the results. Combination rules live in
  `core.modal_combination`; new response spectrum cases default to CQC.
  Response spectrum reactions, element forces and shell resultants are the
  static response to each mode's equivalent load `M φ Γ Sa`
  (`services.spectrum.modal_equivalent_loads`, solved in
  `OpenSeesRunner._modal_static_responses` after the one eigen call, never a
  second `ops.eigen`), combined per component by
  `core.modal_combination.combine_modal_fields` with the same rule and ρ as the
  displacements. They are peak magnitudes; `services.combination.case_bounds`
  turns them into ±peak. The load uses nodal mass only (as the participation
  factors do), not element density.
- **No SAP2000-generated file enters the repository.** The `.s2k` files in
  `tests/fixtures/s2k` are hand-written from the table format, and a test builds
  its own text inline. A real export is used locally only, to check a table's
  columns and fields, and is never copied in: the clean-room provenance of
  `services/sap2000_text.py` depends on it.

## Dependency split

`pyproject.toml` separates dependencies into two tiers:

- **Base** (`pip install -e .`): `pydantic`, `numpy`, `h5py`, `ezdxf`. No
  solver: it models, exports and reports. Safe to use headlessly — no Qt, no
  PyVista, no VTK.
- **Solver extra** (`pip install -e ".[opensees]"`): `openseespy` (and
  `openseespywin` on Windows). OpenSeesPy is an optional *engine* with its own
  license, never a base dependency: `services/engines.py` finds it (this
  environment, another Python 3.12, or a folder appended to `sys.path`, saved in
  `solver.json`), the analysis child gets the folder in
  `OPENSEES_STUDIO_ENGINE_PATH` and the chosen engine in
  `OPENSEES_STUDIO_ENGINE` (it builds that engine's runner with
  `create_runner` and refuses case types the engine does not declare), and the
  GUI disables Run without an engine, and Check Stability and the Material
  Tester without OpenSeesPy (they always call OpenSees). Never import OpenSeesPy at module level, and
  never detect it by importing it. See `docs/adr/ADR-0003-solver-engines.md`.
  Scripts and web backends that solve install `.[opensees]`.
- **GUI extra** (`pip install -e ".[gui]"`): adds PySide6, pyvista, pyvistaqt,
  vtk, pyqtgraph, imageio, ifcopenshell, and `PyNiteFEA` — the bundled second
  engine (MIT; `services/pynite_runner.py`, linear static and P-Delta of elastic
  frames and trusses, results in OpenSees' layout and tested against it in
  `tests/integration/test_pynite_parity.py`). Required to launch the desktop app.

Desktop dev: `pip install -e ".[gui,dev]"` (`dev` pulls in `opensees` and
`gui`, since pytest-qt refuses to start without a Qt binding).
Web / headless: `pip install -e .` (then verify with
`python -c "import sys, opensees_studio.core; assert 'PySide6' not in sys.modules"`).

See `docs/adr/ADR-0002-headless-gui-dep-split.md` for the rationale.

### Frozen builds

`packaging/` freezes the app into a folder an end user runs without Python
(`pip install -e ".[gui,packaging]"`, then `python packaging/build.py`). The
bundle **excludes OpenSeesPy** (ADR-0003): the user installs it from Options →
Solver (`services/engine_install.py`, pinned PyPI wheels with SHA256), and the
smoke test proves both that the frozen CLI refuses without it and that it
solves once installed. The GUI never solves in its own process, so the bundle
re-enters itself as the analysis CLI — see the child-spawn gotcha above. Build with **Python 3.12**:
the interpreter inside the bundle has to be the one the Windows
`opensees.pyd` links against. `packaging/README.md` documents the traps
(the `vtk` shim, PyVista's mypyc module, why VTK is not trimmed); the smoke
test in `build.py` is what proves a bundle can solve before it is shipped.

## Running

```bash
# Activate the venv
.venv\Scripts\activate         # Windows
source .venv/bin/activate      # Linux/macOS

# Launch the app
python -m opensees_studio

# Run tests
pytest tests/unit -v           # pure-logic, no Qt, no openseespy
pytest tests/gui -v            # pytest-qt, real Qt event loop
pytest tests/integration -v    # real openseespy runs (slow)
```

## Test structure

CI scope: a pull request runs only the required checks, `lint` and
`test (ubuntu-latest, 3.12)` (ruff, the mypy ratchet, import-linter, unit,
integration and tools). The Windows/macOS/Python 3.13–3.14 entries of `test`,
the `headless` and `gui` jobs and CodeQL run on every push to `main`, weekly,
and from Actions → Run workflow. So run `pytest tests/gui` locally before a PR
that touches the GUI: no PR check will.

- `tests/unit/` — pure logic, instant. No Qt, no openseespy.
  It runs without any `QT_QPA_PLATFORM` setting; a test that needs `qtbot`
  (and with it a QApplication) belongs in `tests/gui/`. The CI `headless` job
  runs it with `.[opensees]` and pytest only (no PySide6, PyVista or pytest-qt):
  a test that imports `viewmodels`, `commands` or `views` goes to `tests/gui/`
  (the one exception is the Qt-free spec tables of `views/actions`, see
  `tests/unit/test_action_specs.py`), and a renderer test skips itself with
  `pytest.importorskip("pyvista")`.
- `tests/gui/` — `qtbot` fixture, `@pytest.mark.gui`.
  Run it in one pytest process: `pytest tests/gui` (255 tests in 45 files
  as of 2026-09-28, about 50 s on Windows). CI does the same in its `gui`
  job. Check the exit code, not only the pass count: any non-zero code (for
  example `0xC0000374` after all tests pass) is a teardown bug.
  `tests/gui/conftest.py` closes plotters and top-level widgets at session
  end. Fallback for diagnosing a crash: run one process per test file, which
  names the failing file (about 185 s on Windows):
  `Get-ChildItem tests\gui\test_*.py | ForEach-Object { python -m pytest $_.FullName }`.
  The single process used to segfault around test 73 because VTK render
  windows accumulated (see `reports/STATUS_2026-09-12.md`); since the
  2026-09-23 teardown fixes it passes.
- `tests/integration/` — real `openseespy` runs that exercise full
  model → solve → results pipelines on the bundled examples, including the
  analysis CLI as a subprocess (`test_analysis_cli.py`) and the
  direct-versus-CLI result parity (`test_cli_result_parity.py`).

## Results snapshots

`tools/results_snapshot.py` runs every project in `examples/` through the
analysis CLI and pins a fingerprint of each case in
`tests/data/results_snapshots.json` (`tests/integration/test_results_snapshot.py`
checks it, 1e-5 relative). Never re-pin to make CI green: a change of results is
pinned only with `--write --reason "..."`, which appends the before/after to
`docs/results-changes.md`, and the CHANGELOG gets a **Results changed** entry
for it. A new example is pinned with `--write <stem>`.

## Render budget

`tools/render_bench.py` builds synthetic models and measures the geometry build
(CPU) and the number of actors from the renderer, without opening a GPU context
— `tests/tools/test_render_budget.py` runs it in the normal suite. The ceilings
live in `tools/render-budget.txt` and are a ratchet: the actor count is exact,
the time ceiling is wide enough to survive a busy runner. Target from the
roadmap: 10k nodes and 20k frames at 30 fps, so the numbers only go down.

## File-size budget

`tools/file-size-budget.txt` is the ceiling on the length of every Python file
of `src/opensees_studio`: 1,500 lines, or the file's own ceiling when it was
already longer (`views/main_window.py`, the runner, the importers…).
`tests/tools/test_file_size_budget.py` fails when a file goes over, and also
when a listed file is 150 lines under its ceiling, so the ceiling follows the
file down. Do not raise a ceiling or add a file to make a change fit: split
the file (a controller, a widget of its own, a module per case type or code).
Generated code is exempt.

## Examples

The `examples/` directory contains both Python scripts and
pre-generated `.osmodel` files. Each script builds the project, saves
it, reloads, and round-trips for sanity. See [`examples/README.md`](examples/README.md)
for the full catalogue.

To regenerate every example after changing the data model:

```bash
for f in examples/*.py; do python "$f"; done
```

## Before opening a PR

**Always update from `main` first.** Before opening a PR (and before
pushing a branch that will become one), check `git branch --show-current`
— several sessions share this checkout and one may have switched the
branch — then `git fetch origin` and merge `origin/main` into the branch,
re-run the gates and the affected tests on the result, and only then push
and open the PR against `main`. Do not stack a PR on another feature
branch: it merges into that branch, not into `main`.

A PR is not ready until the documentation that the change invalidates is
fixed **in the same PR**. This applies to every PR, not only to
user-visible features:

1. **Help pages.** Every menu action and dialog has a page: a file
   `data/help/<topic id>.md` (front matter `title`, `group`, `summary`,
   `see_also`, `order`; the format is in `core/help.py`'s docstring). Add the
   new page **and** its line in `ACTION_TOPICS` (`core/help.py`); `tests/gui/test_help_window.py::test_every_menu_action_declares_a_page_that_exists`
   fails on an action that does not declare one. Write the body for
   somebody who has the dialog open, and link related pages through
   `see_also`.
2. **User-facing docs.** `README.md`, `docs/` and `examples/README.md`
   wherever the change alters what they describe: menu paths, shortcuts,
   file format, command line, I/O.
3. **Format and behaviour changes.** If the `.osmodel` payload gained a
   field, document it where the format is described and keep the
   `omit_when_default` rule (a project that does not use the option must
   still save byte-identical).
4. **Delete what is no longer true.** A stale paragraph, a screenshot of a
   removed dialog, a documented flag that no longer exists: remove it in
   the same PR instead of leaving the contradiction in place.
5. **CHANGELOG.** Add the entry when the change is user-visible.
6. **Gates.** `ruff check`, `ruff format --check`, `python tools/typecheck.py`
   (must stay within the budget) and `lint-imports` before pushing.

## Branch strategy

- `main` is the only integration branch in this fork: a short-lived branch per
  change (`feat/`, `fix/`, `chore/`, …) merged by pull request.
- For contributions to the original repository, branch from `upstream/main`;
  its `develop` branch is the maintainer's experimental branch, not a PR target.
- Releases are tags on `main` (`v0.0.x`). **Pushing the tag is what publishes**:
  `desktop.yml` builds the three bundles, writes `SHA256SUMS.txt` and the
  `publish` job creates the release with the notes taken from `CHANGELOG.md`.
  Do not write the release body by hand — the workflow overwrites it.
- Conventional commit style: `feat:`, `fix:`, `refactor:`, `docs:`,
  `test:`, `chore:`, `ci:`.
