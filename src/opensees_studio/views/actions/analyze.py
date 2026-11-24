"""Analyze menu commands (``AnalysisController``; Delete All Results is ``ResultsViewController``'s)."""

from __future__ import annotations

from opensees_studio.views.actions.spec import ActionSpec, Needs

ANALYZE_ACTIONS: tuple[ActionSpec, ...] = (
    # Works with no project open: it starts one.
    ActionSpec("analyze.case_manager", "&Cases…", "analysis.case_manager", shortcut="Ctrl+Shift+A"),
    ActionSpec(
        "analyze.check_model",
        "Check &Model…",
        "analysis.check_model",
        shortcut="F6",
        needs=Needs.PROJECT,
    ),
    # The next four wait for a solver, and for the run or the check that is
    # under way to end: the window enables them.
    ActionSpec(
        "analyze.check_stability",
        "Check Model &Stability…",
        "analysis.check_stability",
        needs=None,
    ),
    ActionSpec("analyze.run", "&Run…", "analysis.run", shortcut="F5", needs=None),
    # Batch doors: the whole model in one child process, or a ticked subset.
    ActionSpec(
        "analyze.run_all", "Run &All Cases", "analysis.run_all", shortcut="Shift+F5", needs=None
    ),
    ActionSpec("analyze.run_selected", "Run Se&lected Cases…", "analysis.run_selected", needs=None),
    # Enabled by the window: results in memory, or a results database on disk.
    ActionSpec(
        "analyze.clear_results", "Delete &All Results…", "results_view.delete_all", needs=None
    ),
)
