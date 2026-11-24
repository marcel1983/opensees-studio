"""Define → Time Series, load patterns and ground excitation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import AddLoadPatternCommand, AddTimeSeriesCommand
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import (
    LinearTimeSeriesDialog,
    PathTimeSeriesDialog,
    PlainPatternDialog,
    UniformExcitationDialog,
)


class PatternsController(QObject):
    """What varies a load in time and what carries it: time series and patterns.

    A time series can be defined before there is a project, so the window
    hands over new_project (File → New) and the command starts one. A
    pattern refers to a series: its commands are offered once the project has
    one (Needs.TIME_SERIES). It keeps no state.
    """

    def __init__(self, shell: Shell, *, new_project: Callable[[], None]) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._new_project = new_project

    def add_linear_ts(self) -> None:
        """Define → Add Linear TimeSeries…"""
        if self._vm.project is None:
            self._new_project()
        proj = self._vm.project
        assert proj is not None
        dlg = LinearTimeSeriesDialog(
            next_ts_id=proj.next_time_series_id(),
            parent=self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            ts = dlg.time_series()
            self._vm.apply_command(AddTimeSeriesCommand(self._vm, ts))
            self._shell.log(
                f"Added LinearTimeSeries #{ts.id} '{ts.name}' (factor={ts.factor:g}).",
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Add Linear TimeSeries failed", str(exc))

    def add_path_ts(self) -> None:
        """Define → Add Path TimeSeries… — ground-motion import."""
        if self._vm.project is None:
            self._new_project()
        proj = self._vm.project
        assert proj is not None
        dlg = PathTimeSeriesDialog(
            next_ts_id=proj.next_time_series_id(),
            parent=self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            ts = dlg.time_series()
            self._vm.apply_command(AddTimeSeriesCommand(self._vm, ts))
            self._shell.log(
                f"Added PathTimeSeries #{ts.id} '{ts.name}' "
                f"({len(ts.values)} points, Δt={ts.dt:g} s, "
                f"factor={ts.factor:g}).",
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Add Path TimeSeries failed", str(exc))

    def add_function_ts(self) -> None:
        """Define → Add Function TimeSeries: Constant, Trig, Triangle, Rectangular, Pulse."""
        from opensees_studio.views.dialogs.function_time_series import FunctionTimeSeriesDialog

        if self._vm.project is None:
            self._new_project()
        proj = self._vm.project
        assert proj is not None
        dlg = FunctionTimeSeriesDialog(next_ts_id=proj.next_time_series_id(), parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            ts = dlg.time_series()
            self._vm.apply_command(AddTimeSeriesCommand(self._vm, ts))
            self._shell.log(f"Added {ts.type} TimeSeries #{ts.id} '{ts.name}'.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Add TimeSeries failed", str(exc))

    def constant_ts(self) -> None:
        if self._vm.project is None:
            return
        from opensees_studio.views.dialogs.constant_time_series import ConstantTimeSeriesDialog

        ConstantTimeSeriesDialog(self._vm, self._window).exec()

    def add_plain_pattern(self) -> None:
        """Define → Add Plain Load Pattern…"""
        if self._vm.project is None:
            self._new_project()
        proj = self._vm.project
        assert proj is not None
        if not proj.time_series:
            QMessageBox.warning(
                self._window,
                "Add Plain Load Pattern",
                "Define a TimeSeries first (Define → Add Linear TimeSeries… "
                "or Define → Add Path TimeSeries…) so the pattern has a "
                "time-series reference.",
            )
            return
        dlg = PlainPatternDialog(
            project=proj,
            next_pattern_id=proj.next_pattern_id(),
            parent=self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            pat = dlg.pattern()
            self._vm.apply_command(AddLoadPatternCommand(self._vm, pat))
            self._shell.log(
                f"Added PlainLoadPattern #{pat.id} '{pat.name}' (series #{pat.time_series_id}).",
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Add Plain Load Pattern failed", str(exc))

    def add_uniform_excitation(self) -> None:
        """Define → Add Uniform Excitation… — base ground-motion pattern."""
        if self._vm.project is None:
            self._new_project()
        proj = self._vm.project
        assert proj is not None
        if not proj.time_series:
            QMessageBox.warning(
                self._window,
                "Add Uniform Excitation",
                "Define a Path TimeSeries first (Define → Add Path "
                "TimeSeries…) so the pattern has a ground-motion record "
                "to reference.",
            )
            return
        dlg = UniformExcitationDialog(
            project=proj,
            next_pattern_id=proj.next_pattern_id(),
            parent=self._window,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            pat = dlg.pattern()
            self._vm.apply_command(AddLoadPatternCommand(self._vm, pat))
            self._shell.log(
                f"Added UniformExcitation pattern #{pat.id} '{pat.name}' "
                f"(DOF {pat.direction}, series #{pat.accel_series_id}, "
                f"factor {pat.factor:g}).",
            )
        except Exception as exc:
            QMessageBox.critical(
                self._window,
                "Add Uniform Excitation failed",
                str(exc),
            )

    def add_multi_support(self) -> None:
        """Define → Add Multi-Support Excitation: imposed motion of the selected supports."""
        from opensees_studio.views.dialogs.uniform_excitation import MultiSupportExcitationDialog

        proj = self._vm.project
        if proj is None:
            return
        nodes = sorted(self._shell.canvas().selection.nodes)
        if not nodes:
            QMessageBox.information(
                self._window, "Multi-Support Excitation", "Select the supports to drive first."
            )
            return
        if not proj.time_series:
            QMessageBox.information(
                self._window,
                "Multi-Support Excitation",
                "Define a displacement time series first (Define → Add Path TimeSeries…).",
            )
            return
        dlg = MultiSupportExcitationDialog(proj, proj.next_pattern_id(), nodes, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            pat = dlg.pattern()
            self._vm.apply_command(AddLoadPatternCommand(self._vm, pat))
            self._shell.log(
                f"Added MultipleSupport pattern #{pat.id} '{pat.name}' on "
                f"{len(pat.node_ids)} support(s), DOF {pat.direction}."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Add Multi-Support Excitation failed", str(exc))
