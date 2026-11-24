"""File menu commands."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

FILE_ACTIONS: tuple[ActionSpec, ...] = (
    # SAP2000's Ctrl+N: units and a template first.
    ActionSpec("file.new_model", "&New Model…", "_on_new_model", shortcut="std:New"),
    ActionSpec("file.new", "New &Blank 3D Model", "_on_new"),
    ActionSpec("file.new_2d", "New &2D Frame…", "_on_new_2d"),
    ActionSpec("file.new_2d_truss", "New 2D &Truss", "_on_new_2d_truss"),
    ActionSpec("file.open", "&Open…", "_on_open", shortcut="std:Open"),
    ActionSpec("file.save", "&Save", "_on_save", shortcut="std:Save", needs=Needs.PROJECT),
    ActionSpec(
        "file.save_as", "Save &As…", "_on_save_as", shortcut="std:SaveAs", needs=Needs.PROJECT
    ),
    ActionSpec(
        "file.project_info", "Project &Information…", "_on_project_info", needs=Needs.PROJECT
    ),
    ActionSpec("file.import_dxf", "&DXF Drawing…", "imports.dxf", needs=Needs.PROJECT),
    ActionSpec("file.import_s3d", "&PORTICO Model (.s3d)…", "imports.s3d"),
    ActionSpec("file.import_s2k", "SAP2000 &Text (.s2k / .$2k)…", "imports.s2k"),
    ActionSpec("file.import_ifc", "&IFC (.ifc)…", "imports.ifc"),
    ActionSpec("file.import_tcl", "OpenSees &Tcl Script (.tcl)…", "imports.tcl"),
    ActionSpec(
        "file.export_script", "OpenSees &script (.py)…", "exports.script", needs=Needs.PROJECT
    ),
    ActionSpec("file.export_ifc", "&IFC (.ifc)…", "exports.ifc", needs=Needs.PROJECT),
    ActionSpec("file.export_s2k", "SAP2000 &Text (.s2k)…", "exports.s2k", needs=Needs.PROJECT),
    ActionSpec(
        "file.export_report",
        "&Report (PDF / Word / HTML)…",
        "exports.report",
        needs=Needs.PROJECT,
    ),
    ActionSpec(
        "file.calc_memory", "Calculation &Memory…", "exports.calc_memory", needs=Needs.PROJECT
    ),
    # Enabled only with a solver (Options → Solver): the window sets it.
    ActionSpec("file.run_batch", "Run &Batch…", "_on_run_batch", needs=None),
    ActionSpec("file.quit", "&Quit", "_on_quit", shortcut="std:Quit"),
)
