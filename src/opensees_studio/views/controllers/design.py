"""Design menu: basis, members, steel and concrete checks, connections, footings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import (
    AddNotionalLoadsCommand,
    AddSectionsCommand,
    SetChapterJChecksCommand,
    SetColumnSplicesCommand,
    SetConnectionsCommand,
    SetDesignSettingsCommand,
    SetGussetsCommand,
)
from opensees_studio.core import LinearTimeSeries
from opensees_studio.core.design.settings import DesignSettings
from opensees_studio.core.design.stability import notional_pattern
from opensees_studio.services.steel_design import steel_frame_check
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import DriftCheckDialog, NotionalLoadsDialog, SteelDesignDialog
from opensees_studio.views.dialogs.chapter_j import ChapterJDialog
from opensees_studio.views.dialogs.column_splices import ColumnSplicesDialog
from opensees_studio.views.dialogs.connections import ConnectionsDialog
from opensees_studio.views.dialogs.gussets import GussetsDialog


class DesignController(QObject):
    """Runs the Design menu: each command opens its dialog and stores what it returns.

    The checks read results, they never run an analysis: ``results`` gives the
    case results computed on the project as it is now, by case id (the window's
    cache). ``show_ratios`` paints a check's ratios on the model with its legend
    dock; that overlay is post-processing display, which the window still owns.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        results: Callable[[], dict[int, Any]],
        show_ratios: Callable[..., None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._results = results
        self._show_ratios = show_ratios

    # ── basis and stability ───────────────────────────────────────────
    def design_basis(self) -> None:
        """Design → Design Basis: code, method, stability method, systems and steel grades."""
        from opensees_studio.views.dialogs.design_basis import DesignBasisDialog

        project = self._vm.project
        if project is None:
            return
        dialog = DesignBasisDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != project.design:
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
            self._shell.log(
                f"Design basis: {settings.method}, {settings.stability_method} stability "
                f"design, system {settings.seismic_system}"
                + (f" / {settings.seismic_system_y}" if settings.seismic_system_y else "")
                + (
                    f", {len(settings.steel_grades)} family grade(s)."
                    if settings.steel_grades
                    else "."
                )
            )

    def direct_analysis(self) -> None:
        """Design → Direct Analysis Method: one second-order case per LRFD combination."""
        from opensees_studio.commands import ReplaceDirectAnalysisCasesCommand
        from opensees_studio.views.dialogs.design_basis import DirectAnalysisDialog

        project = self._vm.project
        if project is None:
            return
        dialog = DirectAnalysisDialog(project, self._results(), self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cases = dialog.cases()
        if not cases:
            return
        self._vm.apply_command(
            ReplaceDirectAnalysisCasesCommand(self._vm, cases, dialog.settings())
        )
        self._shell.log(
            f"Direct Analysis Method: {len(cases)} case(s) generated; run them "
            "(Analyze → Run All Cases), then check Δ2/Δ1 here and the members in "
            "Design → Steel Frame Check."
        )

    def notional_loads(self) -> None:
        """Design → Generate Notional Loads: AISC 360 C2-1 patterns, one undo step."""
        project = self._vm.project
        if project is None:
            return
        method: str = project.design.method if project.design is not None else "LRFD"
        dialog = NotionalLoadsDialog(project, self._window, method=method)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        directions, factor, method = dialog.settings()
        series: LinearTimeSeries | None = None
        if project.time_series:
            time_series_id = project.time_series[0].id
        else:
            series = LinearTimeSeries(id=project.next_time_series_id(), name="Notional")
            time_series_id = series.id
        patterns = []
        next_id = project.next_pattern_id()
        for direction in directions:
            pattern = notional_pattern(
                project,
                pattern_id=next_id,
                time_series_id=time_series_id,
                factor=factor,
                method=method,
                direction=direction,
            )
            next_id += 1
            if pattern.nodal_loads:
                patterns.append(pattern)
        if not patterns:
            QMessageBox.warning(
                self._window,
                "Notional loads",
                "No storey carries a gravity load. Define a mass source or a Dead/Live "
                "load pattern first.",
            )
            return
        self._vm.apply_command(AddNotionalLoadsCommand(self._vm, patterns, series))
        total = sum(
            load.forces[0] + load.forces[1] for pattern in patterns for load in pattern.nodal_loads
        )
        self._shell.log(
            f"Added {len(patterns)} notional load pattern(s), total {total:.6g}; "
            "use them in the cases of the Direct Analysis Method."
        )

    # ── members ───────────────────────────────────────────────────────
    def member_classification(self) -> None:
        """Design → Member Classification: physical members, roles and unbraced lengths."""
        from opensees_studio.views.dialogs.member_classification import (
            MemberClassificationDialog,
        )

        project = self._vm.project
        if project is None:
            return
        dialog = MemberClassificationDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != (project.design or DesignSettings()):
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
            chosen = sum(1 for m in settings.members if m.role is not None)
            self._shell.log(
                f"Member classification: {dialog.member_count()} member(s), "
                f"{chosen} element(s) with a role set by hand."
            )

    def built_up(self) -> None:
        """Design → Built-Up Shapes: welded I-shapes, and their analysis sections, one undo step."""
        from opensees_studio.views.dialogs.built_up_shapes import BuiltUpShapesDialog

        project = self._vm.project
        if project is None:
            return
        dialog = BuiltUpShapesDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        sections = dialog.new_sections()
        if settings == (project.design or DesignSettings()) and not sections:
            return
        stack = self._vm.undo_stack
        stack.beginMacro("Built-up shapes")
        try:
            if settings != (project.design or DesignSettings()):
                self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
            if sections:
                self._vm.apply_command(AddSectionsCommand(self._vm, sections))
        finally:
            stack.endMacro()
        self._shell.log(
            f"Built-up shapes: {len(settings.built_up)} defined"
            + (f", {len(sections)} analysis section(s) added." if sections else ".")
        )

    # ── steel frame ───────────────────────────────────────────────────
    def steel_check(self) -> None:
        """Design → Steel Frame Check: AISC 360-16 ratios over this session's results.

        The dialog reads the case results cache and runs nothing itself; its
        settings are stored on OK with one undoable command.
        """
        project = self._vm.project
        if project is None:
            return
        dialog = SteelDesignDialog(
            project,
            self._results(),
            selected_elements=frozenset(self._shell.canvas().selection.elements),
            parent=self._window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != project.design:
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
        report = dialog.report()
        if report is not None:
            self._shell.log(
                f"Steel frame check (AISC 360-16, {settings.method}): {report.summary()}"
            )
            for note in report.notes:
                self._shell.log(note)
        if dialog.select_failing_requested:
            failing = dialog.failing_elements()
            self._shell.canvas().selection.set_selection(set(), failing)
            self._window.statusBar().showMessage(
                f"Selected {len(failing)} failing member(s).", 4000
            )
        if dialog.show_ratios_requested and report is not None:
            self._show_ratios(report, settings)

    def steel_ratios(self) -> None:
        """Design → Display Steel Ratios: paint the members by the stored check's ratios.

        Runs the AISC 360-16 check with the project's design settings (the
        defaults when none were stored) over this session's results, as the
        Steel Frame Check dialog would, and shows the overlay with its legend.
        """
        project = self._vm.project
        if project is None:
            return
        settings = project.design or DesignSettings()
        report = steel_frame_check(project, self._results(), settings)
        if not any(m.status != "not designed" for m in report.members):
            reason = " ".join(report.notes) or (
                "No frame member has an AISC section the check covers."
            )
            QMessageBox.information(self._window, "Display Steel Ratios", reason)
            return
        self._shell.log(f"Steel frame check (AISC 360-16, {settings.method}): {report.summary()}")
        self._show_ratios(report, settings)

    def drift_check(self) -> None:
        """Design → Storey Drift Check: amplified drift ratios against the allowable one."""
        project = self._vm.project
        if project is None:
            return
        dialog = DriftCheckDialog(project, self._results(), parent=self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != project.design:
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))

    # ── connections ───────────────────────────────────────────────────
    def joint_connections(self) -> None:
        """Design → Connections by Joint: topology of every member end, shear tabs checked."""
        from opensees_studio.views.dialogs.joint_connections import JointConnectionsDialog

        project = self._vm.project
        if project is None:
            return
        dialog = JointConnectionsDialog(project, self._results(), self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != (project.design or DesignSettings()):
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
        rows = dialog.run_check()
        tabs = [r for r in rows if r.status in ("OK", "NG")]
        failing = [f"{r.connection.element_id}{r.connection.end}" for r in tabs if r.status == "NG"]
        self._shell.log(
            f"Connections by joint: {len(rows)} connection(s), {len(tabs)} shear tab(s)"
            + (f", over the limit at {', '.join(failing)}." if failing else ".")
        )

    def base_plates(self) -> None:
        """Design → Base Plates: every column base over the design load sets."""
        from opensees_studio.views.dialogs.base_plates import BasePlatesDialog

        project = self._vm.project
        if project is None:
            return
        dialog = BasePlatesDialog(project, self._results(), self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != (project.design or DesignSettings()):
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
        failing = [r.node_id for r in dialog.run_check() if r.status == "NG"]
        self._shell.log(
            f"Base plates: {len(dialog.designs())} column base(s)"
            + (f", over the limit at node(s) {', '.join(map(str, failing))}." if failing else ".")
        )

    def connections(self) -> None:
        """Design → Connections: edit the AISC 358 RBS connections."""
        project = self._vm.project
        if project is None:
            return
        dialog = ConnectionsDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        connections = dialog.connections()
        if connections != project.connections:
            self._vm.apply_command(SetConnectionsCommand(self._vm, connections))
        self._shell.log(f"{len(connections)} RBS connection(s).")

    def gussets(self) -> None:
        """Design → Gussets: edit the AISC 341 SCBF gusset plates."""
        project = self._vm.project
        if project is None:
            return
        dialog = GussetsDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        gussets = dialog.gussets()
        if gussets != project.gussets:
            self._vm.apply_command(SetGussetsCommand(self._vm, gussets))
        self._shell.log(f"{len(gussets)} gusset plate(s).")

    def column_splices(self) -> None:
        """Design → Column Splices: edit the AISC 341 SCBF column splices."""
        project = self._vm.project
        if project is None:
            return
        dialog = ColumnSplicesDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        splices = dialog.splices()
        if splices != project.column_splices:
            self._vm.apply_command(SetColumnSplicesCommand(self._vm, splices))
        self._shell.log(f"{len(splices)} column splice(s).")

    def chapter_j(self) -> None:
        """Design → Connection Checks: AISC 360 Chapter J checks."""
        project = self._vm.project
        if project is None:
            return
        dialog = ChapterJDialog(project, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        checks = dialog.checks()
        if checks != project.chapter_j_checks:
            self._vm.apply_command(SetChapterJChecksCommand(self._vm, checks))
        self._shell.log(f"{len(checks)} Chapter J check(s).")

    # ── calculators ───────────────────────────────────────────────────
    def base_plate(self) -> None:
        """Design → Base Plate & Anchors: DG1 and ACI 318 Ch. 17 for one column base."""
        from opensees_studio.views.dialogs.connection_calculators import BasePlateDialog

        project = self._vm.project
        if project is None:
            return
        nodes = sorted(self._shell.canvas().selection.nodes)
        dialog = BasePlateDialog(
            project,
            self._results(),
            nodes[0] if len(nodes) == 1 else None,
            self._window,
        )
        dialog.exec()

    def bolted_connection(self) -> None:
        """Design → Bolted Connection: prying action and an eccentric bolt group."""
        from opensees_studio.views.dialogs.connection_calculators import BoltedConnectionDialog

        project = self._vm.project
        if project is None:
            return
        BoltedConnectionDialog(project, self._window).exec()

    # ── concrete and foundations ──────────────────────────────────────
    def concrete_check(self) -> None:
        """Design → Concrete Frame Check: ACI 318-19 ratios over this session's results."""
        from opensees_studio.views.dialogs.concrete_design import ConcreteDesignDialog

        project = self._vm.project
        if project is None:
            return
        dialog = ConcreteDesignDialog(project, self._results(), self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != project.design:
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
        report = dialog.report()
        if report is not None:
            self._shell.log(f"Concrete frame check (ACI 318-19): {report.summary()}")
            for note in report.notes:
                self._shell.log(note)
            if dialog.show_ratios_requested:
                self._show_ratios(report, settings, concrete=True)

    def footings(self) -> None:
        """Design → Footings: an isolated footing under every support, ACI 318-19 and the soil."""
        from opensees_studio.views.dialogs.footings import FootingsDialog

        project = self._vm.project
        if project is None:
            return
        dialog = FootingsDialog(project, self._results(), self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings != (project.design or DesignSettings()):
            self._vm.apply_command(SetDesignSettingsCommand(self._vm, settings))
        reports = dialog.reports()
        failing = [r.label for r in reports if r.status == "NG"]
        combined = len(settings.combined_footings)
        self._shell.log(
            f"Footings: {len(settings.footings)} footing(s)"
            + (f" and {combined} combined" if combined else "")
            + (f", over the limit: {', '.join(failing)}." if failing else ".")
        )

    def footing_pressures(self) -> None:
        """Design → Footing Pressure Plan: the soil pressure under every footing, in plan."""
        from opensees_studio.services.footings import all_footing_reports
        from opensees_studio.views.dialogs.footing_pressures import FootingPressuresDialog

        project = self._vm.project
        if project is None:
            return
        results = self._results()
        reports = all_footing_reports(project, results, project.design)
        FootingPressuresDialog(project, reports, self._window).exec()
