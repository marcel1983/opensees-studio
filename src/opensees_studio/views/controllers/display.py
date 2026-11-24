"""What the viewport shows of the results: the views of the Display menu."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from contextlib import AbstractContextManager
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QDockWidget, QMessageBox

from opensees_studio.core import UnitConverter, UnitSystem
from opensees_studio.core.design.settings import DesignSettings
from opensees_studio.core.model_check import Finding
from opensees_studio.services.deformation import (
    DeformationSource,
    linear_static_auto_scale,
    modal_to_deformation,
    motion_to_deformation,
    peak_static_displacement,
    static_to_deformation,
)
from opensees_studio.services.element_forces import ForceComponent
from opensees_studio.services.element_forces import auto_scale as force_diagram_auto_scale
from opensees_studio.services.results import (
    InfluenceLineResults,
    ModalResults,
    PushoverResults,
    ResponseSpectrumResults,
    StaticResults,
    TransientResults,
)
from opensees_studio.services.shell_fields import shell_elements
from opensees_studio.viewmodels.results_session import ResultsSession
from opensees_studio.views.canvas3d import ModelCanvas
from opensees_studio.views.canvas3d.design_ratio_renderer import DesignRatioRenderer
from opensees_studio.views.canvas3d.diagram_renderer import DiagramRenderer
from opensees_studio.views.canvas3d.model_renderer import RendererMode
from opensees_studio.views.canvas3d.shell_contour_renderer import ShellContourRenderer
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import InfluenceLineDialog
from opensees_studio.views.docks import (
    DeformedShapeView,
    DesignRatioView,
    ForceDiagramView,
    HysteresisView,
    ModeShapeAnimator,
    PushoverCurveView,
    ResponseSpectrumView,
    ShellContourView,
    TimeHistoryView,
)
from opensees_studio.views.i18n import tr


class DisplayController(QObject):
    """The post-processing views and the dock each one opens.

    One view at a time: a deformed shape, a mode shape, a force diagram, shell
    contours, a time-history, hysteresis, pushover or response spectrum plot,
    the design ratios, a mechanism of Check Model. Each puts its panel in
    :attr:`dock` (replacing the previous one), draws on the focused viewport
    and names itself in the viewport's caption; Back to Model View takes all of
    it away. :attr:`mode` says what the canvas shows when the pointer and the
    right-click depend on it ("force", "deformed", "mode").

    ``results`` is the window's results session, and ``diagram``, ``contours``
    and ``ratios`` the overlays it draws on the main viewport. ``canvases``
    lists every viewport (the caption goes on all of them), ``busy`` is the
    window's wait cursor, ``select_rows`` selects what a mechanism moves and
    ``close_member_windows`` closes the member diagram windows of a view that
    is being replaced.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        results: ResultsSession,
        diagram: DiagramRenderer,
        contours: ShellContourRenderer,
        ratios: DesignRatioRenderer,
        canvases: Callable[[], Iterable[ModelCanvas]],
        busy: Callable[[str], AbstractContextManager[None]],
        select_rows: Callable[[Sequence[int], Sequence[int]], None],
        close_member_windows: Callable[[], None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._results = results
        self._diagram = diagram
        self._contours = contours
        self._ratios = ratios
        self._canvases = canvases
        self._busy = busy
        self._select_rows = select_rows
        self._close_member_windows = close_member_windows
        #: The active post-processing dock, or None in the model view.
        self.dock: QDockWidget | None = None
        #: "force", "deformed" or "mode" while the canvas shows one of them.
        self.mode: str | None = None
        #: What the viewport is displaying ("Deformed Shape"), ahead of the case name.
        self.title: str | None = None
        self._units_refresh: Callable[[], None] | None = None  # re-show the dock in new units

    def refresh_units(self) -> bool:
        """Re-show the open view in the display units; False when none re-shows itself."""
        if self._units_refresh is None:
            return False
        self._units_refresh()
        return True

    def set_title(self, title: str | None) -> None:
        """Say what the viewport draws ("Deformed Shape"), ahead of the case's name."""
        self.title = title
        if self._results.latest is not None:
            self.set_caption(self._results.caption_for(self._vm.project, self._results.latest))

    def set_caption(self, text: str | None) -> None:
        """Put ``text`` in every viewport: the main one and each view window."""
        if text and self.title:
            text = f"{self.title}  ·  {text}"
        for canvas in self._canvases():
            canvas.set_result_label(text)

    def register_units_refresh(
        self,
        view: Any,
        after: Callable[[], None] | None = None,
    ) -> None:
        """Remember how to re-show ``view`` when the display units change.

        ``view`` must expose ``set_units(UnitConverter)``; ``after`` re-applies
        whatever the dock draws (a diagram overlay, a deformed shape). The dock
        being torn down, or another project being opened, drops the callback.
        """
        project = self._vm.project

        def _refresh() -> None:
            if self.dock is None or self._vm.project is not project:
                return
            view.set_units(UnitConverter.of(project.meta))
            if after is not None:
                after()

        self._units_refresh = _refresh

    def show_deformed(self) -> None:
        """Display → Show Deformed Shape: the static result (or one bound of a combination)."""
        static = self._results.static()
        if static is None or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Deformed Shape",
                "Run a Static analysis or a load combination first (Display works on the "
                "latest results).",
            )
            return
        self.tear_down()
        suggested = linear_static_auto_scale(self._vm.project, static)
        view = DeformedShapeView(suggested_scale=suggested)
        view.show_bounds(self._results.is_envelope())
        dock = QDockWidget("Deformed Shape", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock
        self.mode = "deformed"
        self.set_title("Deformed Shape")

        # The member curves integrate the moment diagrams: build the shape once
        # per result and let the slider only change its scale.
        shapes: list[tuple[object, str, DeformationSource]] = []

        def _apply(scale: float) -> None:
            bound = view.current_bound()
            current = self._results.static(bound)
            if current is None or self._vm.project is None:
                return
            results = self._results.latest
            if shapes and shapes[0][0] is results and shapes[0][1] == bound:
                src = shapes[0][2]
            else:
                # Span loads are read back from a case: not for a combination.
                src = static_to_deformation(
                    self._vm.project,
                    current,
                    span_loads=isinstance(results, StaticResults),
                )
                shapes[:] = [(results, bound, src)]
            self._shell.canvas()._renderer.set_mode(
                RendererMode.DEFORMED, replace(src, scale=scale)
            )
            self._shell.canvas().render()

        def _on_bound(bound: str) -> None:
            current = self._results.static(bound)
            if current is not None and self._vm.project is not None:
                view.set_peak_displacement(peak_static_displacement(self._vm.project, current))
            _apply(view.current_scale)

        view.scaleChanged.connect(_apply)
        view.boundChanged.connect(_on_bound)
        view.closed.connect(self.back_to_model)
        view.set_units(UnitConverter.of(self._vm.project.meta))
        view.set_peak_displacement(peak_static_displacement(self._vm.project, static))
        _apply(suggested)  # initial frame at the suggested scale
        self.register_units_refresh(view, after=lambda: _apply(view.current_scale))

    def show_mode_shape(self) -> None:
        """Display → Animate Mode Shape: the modal result on screen, one mode at a time."""
        if not isinstance(self._results.latest, ModalResults) or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Mode Shape",
                "Run a Modal analysis first.",
            )
            return
        self.tear_down()
        n_modes = len(self._results.latest.eigenvalues)
        freqs = list(self._results.latest.frequencies)
        animator = ModeShapeAnimator(n_modes, freqs)
        dock = QDockWidget("Mode Shape Animator", self._window)
        dock.setWidget(animator)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock
        self.mode = "mode"

        def _apply(mode: int, scale: float, phase: float) -> None:
            self.set_title(f"Mode Shape {mode}")
            if not isinstance(self._results.latest, ModalResults):
                return
            src = modal_to_deformation(
                self._vm.project, self._results.latest, mode=mode, scale=scale, phase=phase
            )
            self._shell.canvas()._renderer.set_mode(RendererMode.MODAL, src)
            self._shell.canvas().render()

        animator.frameChanged.connect(_apply)
        animator.closed.connect(self.back_to_model)
        animator.exportRequested.connect(
            lambda: self._export_mode_shape(animator, _apply),
        )

    def _export_mode_shape(self, animator, apply_callable) -> None:  # type: ignore[no-untyped-def]
        """Capture one period of the current mode shape to MP4/GIF.

        Runs synchronously on the main thread — typically <10s for a
        100-node model. We deliberately don't push this to a QThread
        because the off-screen renderer must be touched from the GUI
        thread (VTK's Qt-backed render window isn't thread-safe).
        """
        from PySide6.QtWidgets import QFileDialog

        path, _sel = QFileDialog.getSaveFileName(
            self._window,
            "Export Mode Shape Animation",
            f"mode_{animator.current_mode() + 1}.mp4",
            "MP4 Video (*.mp4);;GIF Animation (*.gif);;WebM Video (*.webm)",
        )
        if not path:
            return

        from opensees_studio.services.animation_export import export_mode_shape_video

        mode = animator.current_mode()
        scale = animator.current_scale()

        def set_phase(phase: float) -> None:
            apply_callable(mode, scale, phase)

        try:
            self._shell.log(f"Exporting mode {mode + 1} animation → {path} …")
            export_mode_shape_video(
                self._shell.canvas(),
                set_phase,
                Path(path),
                n_frames=60,
                fps=30,
                progress=lambda i, n: self._window.statusBar().showMessage(
                    f"Exporting frame {i}/{n}",
                ),
            )
            self._window.statusBar().clearMessage()
            self._shell.log(f"Export complete: {path}")
        except Exception as exc:
            QMessageBox.critical(
                self._window,
                "Export failed",
                f"Could not write the animation:\n\n{exc}\n\n"
                "MP4 export requires FFmpeg via imageio. Try .gif as a fallback.",
            )

    def show_force_diagram(self) -> None:
        """Display → Show Force Diagram: N, V, M or T along the line elements."""
        if self._results.static() is None or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Force Diagram",
                "Run a Static analysis or a load combination first; force diagrams visualise "
                "its element-force output.",
            )
            return
        if self._results.is_envelope():
            self._shell.log(
                "The force diagram draws both bounds of the combination: the maximum and the "
                "minimum diagram, labelled at their extreme values."
            )
        self.tear_down()

        # Pick the component with the largest abs_max as the initial choice
        # so the user sees something even if N (the default) happens to be
        # zero (cantilever bending case, etc.).
        best_comp, best_data = self._best_initial_component()
        suggested = force_diagram_auto_scale(self._vm.project, best_data)

        view = ForceDiagramView(suggested_scale=suggested)
        # Sync the picker to the auto-chosen best component WITHOUT firing
        # signals (we'll emit a single render below).
        view._component.blockSignals(True)
        idx = view._component.findData(best_comp)
        if idx >= 0:
            view._component.setCurrentIndex(idx)
        view._component.blockSignals(False)

        dock = QDockWidget("Force Diagram", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock
        self.mode = "force"

        def _render(component: ForceComponent, scale: float) -> None:
            if self._results.static() is None:
                return
            self.set_title(f"Force Diagram {component.name}")
            data = self._results.diagram_data(self._vm.project, component)
            if data.element_ids.size == 0:
                self._shell.log(
                    f"Nothing to draw for {component.name}: a force diagram runs "
                    "between the two ends of a line element, and no such element "
                    "returned forces (shells and quads have no ends)."
                )
            self._diagram.render(self._vm.project, data, scale)
            self._shell.canvas().render()

        def _on_component_changed(component: ForceComponent) -> None:
            # Recompute the suggested scale for the new component and push
            # it back into the view, which will re-emit `changed`.
            data = self._results.diagram_data(self._vm.project, component)
            new_scale = force_diagram_auto_scale(self._vm.project, data)
            view.set_scale_base(new_scale)

        view.componentChanged.connect(_on_component_changed)
        view.changed.connect(_render)
        view.closed.connect(self.back_to_model)
        view.set_units(UnitConverter.of(self._vm.project.meta))

        # Force the first render now that everything is wired.
        view._emit_changed()
        self.register_units_refresh(
            view,
            after=lambda: _render(view.current_component(), view.current_scale),
        )

    def _best_initial_component(self):
        """Return the (component, data) pair with the largest |force|.

        Used when first opening the diagram dock so we don't show an empty
        diagram for cases where the default component happens to be zero.
        """
        best_comp = ForceComponent.N
        best_data = self._results.diagram_data(self._vm.project, ForceComponent.N)
        best_max = best_data.abs_max
        for comp in (
            ForceComponent.V2,
            ForceComponent.V3,
            ForceComponent.M2,
            ForceComponent.M3,
            ForceComponent.T,
        ):
            d = self._results.diagram_data(self._vm.project, comp)
            if d.abs_max > best_max:
                best_max, best_comp, best_data = d.abs_max, comp, d
        return best_comp, best_data

    def shell_contours(self) -> None:
        """Display → Show Shell Contours: colour the shell faces by a field.

        The dock is the control; the canvas overlay is the renderer, and the two
        talk through `ShellContourView.changed`. The scale box starts at 0 (the
        undeformed model) because a force or moment contour is read on the
        geometry it belongs to, and warping is what makes a deformation contour
        legible.
        """
        static = self._results.static()
        if static is None or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Shell Contours",
                "Run a Static analysis first: the contour shows its displacements and "
                "its shell section resultants.",
            )
            return
        if not shell_elements(self._vm.project):
            QMessageBox.information(
                self._window,
                "Shell Contours",
                "This model has no shell elements. A contour paints shell faces "
                "(ShellMITC4 or quad elements).",
            )
            return

        self.tear_down()
        if self._results.is_envelope():
            self._shell.log(
                "Shell contours paint one value per face: they show the maximum bound of "
                "the combination."
            )
        view = ShellContourView(n_steps=static.n_steps)
        dock = QDockWidget("Shell Contours", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.resize(700, 500)
        self.dock = dock

        def _render(field_key: str, step: int, scale: float, directions: bool) -> None:
            current = self._results.static()
            if current is None or self._vm.project is None:
                return
            self._contours.render(
                self._vm.project,
                current,
                field_key,
                step=step,
                scale=scale,
                show_directions=directions,
                units=view.target_units,
            )
            self._shell.canvas().render()

        view.changed.connect(_render)
        view.closed.connect(self.back_to_model)
        view.set_units(UnitConverter.of(self._vm.project.meta))
        # The colour bar carries a unit, so a display-unit change repaints.
        view.unitsChanged.connect(
            lambda: _render(
                view.current_field(),
                view.current_step(),
                view.current_scale(),
                view.directions_wanted(),
            ),
        )
        view._field.setFocus()
        view.emit_changed()
        self.register_units_refresh(view)

    def show_time_history(self) -> None:
        """Display → Time-History Plot: a response of the transient result against time."""
        if not isinstance(self._results.latest, TransientResults) or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Time-History Plot",
                "Run a Transient (time-history) analysis first.",
            )
            return
        self.tear_down()
        view = TimeHistoryView()
        view.set_results(self._results.latest)
        view.set_available_nodes([n.id for n in self._vm.project.nodes])
        dock = QDockWidget("Time-History Plot", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        # Plotter docks deserve more space than the slim deformed-shape panel.
        dock.resize(700, 500)
        self.dock = dock
        view.closed.connect(self.back_to_model)
        view.set_units(UnitConverter.of(self._vm.project.meta))
        self.register_units_refresh(view)

    def export_th_animation(self) -> None:
        """Export the deformed shape evolution over a transient analysis."""
        if not isinstance(self._results.latest, TransientResults) or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Export Time-History Animation",
                "Run a Transient (time-history) analysis first.",
            )
            return
        from PySide6.QtWidgets import QFileDialog, QInputDialog

        from opensees_studio.services.animation_export import (
            export_time_history_video,
        )

        # Compute a sensible scale: peak displacement → ~10% of bbox.
        # We piggy-back on the deformation service for consistency.
        # First peek at the data so we can pick `every` such that the
        # video ends up reasonable (~150 frames target).
        n_steps = self._results.latest.n_steps
        if n_steps < 1:
            QMessageBox.information(
                self._window,
                "Export Time-History Animation",
                "The transient run completed no steps, so there is nothing to animate.",
            )
            return
        every, ok = QInputDialog.getInt(
            self._window,
            "Frame decimation",
            f"Take every Nth step ({n_steps} steps available):",
            max(1, n_steps // 150),
            1,
            n_steps,
        )
        if not ok:
            return

        path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Export Time-History Animation",
            f"timehistory_{self._results.latest.case_name}.mp4",
            "MP4 Video (*.mp4);;GIF Animation (*.gif);;WebM Video (*.webm)",
        )
        if not path:
            return

        # Find the largest displacement to set a visible scale.
        from opensees_studio.services.deformation import (
            transient_to_deformation_at_step,
        )

        def set_step(step: int) -> None:
            src = transient_to_deformation_at_step(
                self._vm.project,
                self._results.latest,
                step=step,
            )
            self._shell.canvas()._renderer.set_mode(RendererMode.DEFORMED, src)
            self._shell.canvas().render()

        try:
            self._shell.log(f"Exporting time-history animation → {path} …")
            with self._busy("Exporting animation…"):
                export_time_history_video(
                    self._shell.canvas(),
                    set_step,
                    Path(path),
                    n_steps,
                    fps=30,
                    every=every,
                    progress=lambda i, n: self._window.statusBar().showMessage(
                        f"Exporting frame {i}/{n}",
                    ),
                )
            self._window.statusBar().clearMessage()
            self._shell.log(f"Export complete: {path}")
        except Exception as exc:
            QMessageBox.critical(
                self._window,
                "Export failed",
                f"Could not write the animation:\n\n{exc}\n\n"
                "MP4 export requires FFmpeg via imageio. Try .gif as a fallback.",
            )

    def show_hysteresis(self) -> None:
        """Display → Hysteresis Plot: one response of the transient result against another."""
        if not isinstance(self._results.latest, TransientResults) or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Hysteresis Plot",
                "Run a Transient (time-history) analysis first.",
            )
            return
        self.tear_down()
        view = HysteresisView()
        view.set_results(self._results.latest)
        view.set_available_nodes([n.id for n in self._vm.project.nodes])
        view.set_available_elements([e.id for e in self._vm.project.elements])
        dock = QDockWidget("Hysteresis Plot", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.resize(700, 500)
        self.dock = dock
        view.closed.connect(self.back_to_model)
        view.set_units(UnitConverter.of(self._vm.project.meta))
        self.register_units_refresh(view)

    def show_pushover(self) -> None:
        """Display → Show Pushover Curve."""
        if not isinstance(self._results.latest, PushoverResults):
            QMessageBox.information(
                self._window,
                "Pushover Curve",
                "Run a Pushover analysis first.",
            )
            return
        self.tear_down()
        # Plot axes follow the project's units and ndf so a kip-in / ndf=3
        # Moment-Curvature model shows "in" / "kip·in" (or "1/in") rather than
        # hard-coded SI m / N. The display conversion is applied by the view.
        units = self._vm.project.meta.units if self._vm.project is not None else UnitSystem.SI_M_N
        display = self._vm.project.meta.display_units if self._vm.project is not None else None
        ndf = self._vm.project.ndf if self._vm.project is not None else 6
        view = PushoverCurveView(units=units, ndf=ndf, display_units=display)
        view.set_results(self._results.latest)
        dock = QDockWidget("Pushover Curve", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.resize(700, 500)
        self.dock = dock
        view.closed.connect(self.back_to_model)
        self.register_units_refresh(view)

    def show_response_spectrum(self) -> None:
        """Display → Show Response Spectrum: the spectrum and the modes on it."""
        if (
            not isinstance(self._results.latest, ResponseSpectrumResults)
            or self._vm.project is None
        ):
            QMessageBox.information(
                self._window,
                "Response Spectrum",
                "Run a Response-Spectrum analysis first.",
            )
            return
        # Find the spectrum referenced by the case so the dock can plot it.
        case_id = self._results.latest.case_id
        case = next((c for c in self._vm.project.analyses if c.id == case_id), None)
        spectrum = None
        if case is not None and case.type == "ResponseSpectrum":
            spectrum = next((s for s in self._vm.project.spectra if s.id == case.spectrum_id), None)

        self.tear_down()
        view = ResponseSpectrumView()
        view.set_results(self._results.latest, spectrum)
        dock = QDockWidget("Response Spectrum", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.resize(800, 600)
        self.dock = dock
        view.closed.connect(self.back_to_model)
        view.set_units(UnitConverter.of(self._vm.project.meta))
        self.register_units_refresh(view)

    def influence_line(self) -> None:
        """Display → Influence Line: one response of the influence-line case on screen."""
        results = self._results.latest
        if not isinstance(results, InfluenceLineResults) or self._vm.project is None:
            QMessageBox.information(
                self._window,
                "Influence Line",
                "Run an influence-line case first (Analyze → Cases… → Add → InfluenceLine).",
            )
            return
        dialog = InfluenceLineDialog(self._vm.project, results, parent=self._window)
        dialog.exec()

    def design_ratios(
        self, report: Any, settings: DesignSettings, *, concrete: bool = False
    ) -> None:
        """The ratio overlay and its legend dock; Back to model clears both."""
        self.back_to_model()
        self._ratios.render(self._vm.project, report.members, limit=settings.ratio_limit)
        view = DesignRatioView()
        if concrete:
            view.set_report(report, method="", limit=settings.ratio_limit, code="ACI 318-19")
        else:
            view.set_report(report, method=settings.method, limit=settings.ratio_limit)
        dock = QDockWidget("Concrete Ratios" if concrete else "Steel Ratios", self._window)
        dock.setWidget(view)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock
        failing = {m.element_id for m in report.failing}

        def _select_failing() -> None:
            self._shell.canvas().selection.set_selection(set(), failing)
            self._window.statusBar().showMessage(
                f"Selected {len(failing)} failing member(s).", 4000
            )

        view.selectFailing.connect(_select_failing)
        view.closed.connect(self.back_to_model)
        self.set_caption(
            "Concrete ratios · ACI 318-19"
            if concrete
            else f"Steel ratios · AISC 360-16 {settings.method}"
        )
        self._shell.canvas().render()

    def mechanism(self, finding: Finding) -> None:
        """Animate the free motions of a mechanism finding on the model."""
        project = self._vm.project
        if project is None or not finding.modes:
            return
        self.tear_down()
        modes = list(finding.modes)
        labels = [f"Motion {k}: {m.kind.replace('_', ' ')}" for k, m in enumerate(modes, 1)]
        animator = ModeShapeAnimator(
            len(modes), [0.0] * len(modes), labels=labels, title="Mechanism"
        )
        dock = QDockWidget("Mechanism", self._window)
        dock.setWidget(animator)
        self._window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock

        def _apply(mode: int, scale: float, phase: float) -> None:
            if not 0 <= mode < len(modes) or self._vm.project is None:
                return
            chosen = modes[mode]
            src = motion_to_deformation(self._vm.project, chosen.motion, scale=scale, phase=phase)
            self._shell.canvas()._renderer.set_mode(RendererMode.MODAL, src)
            self._select_rows(chosen.node_ids, chosen.element_ids)
            self._window.statusBar().showMessage(f"{chosen.description} {chosen.hint}")

        animator.frameChanged.connect(_apply)
        animator.closed.connect(self.back_to_model)
        animator._export_btn.hide()  # a mechanism is not a result to export
        _apply(0, 1.0, 1.0)
        self._shell.log("Mechanism: " + " ".join(m.description for m in modes))

    # ── what the pointer is over ─────────────────────────────────────
    def element_tooltips_enabled(self) -> bool:
        """False while a deformed or a mode shape is drawn: they are read at the joints."""
        return self.mode not in ("deformed", "mode")

    def node_tooltip(self, node_id: int) -> str | None:
        """Hover text for a joint: where it is, its restraint, mass, members and loads."""
        from opensees_studio.core.hover import node_summary

        project = self._vm.project
        if project is None:
            return None
        text = None
        if self.mode == "deformed":
            text = self._deformed_node_tooltip(node_id)
        elif self.mode == "mode":
            text = self._mode_shape_node_tooltip(node_id)
        return text if text is not None else node_summary(project, node_id)

    @staticmethod
    def _node_box(title: str, subtitle: str, rows: list[tuple[str, str, str]]) -> str:
        """The rich-text box a joint's hover shows: a title, a line and a value table."""
        from html import escape

        cells = "".join(
            f"<tr><td><b>{escape(label)}</b></td><td align='right'>&nbsp;{escape(value)}</td>"
            f"<td>&nbsp;{escape(unit)}</td></tr>"
            for label, value, unit in rows
        )
        return (
            f"<b>{escape(title)}</b><br>{escape(subtitle)}"
            f"<table cellspacing='0' cellpadding='1'>{cells}</table>"
        )

    def _joint_title(self, node_id: int) -> str:
        project = self._vm.project
        node = next((n for n in project.nodes if n.id == node_id), None) if project else None
        title = tr("Joint {id}").format(id=node_id)
        return f"{title} ({node.name})" if node is not None and node.name else title

    def _mode_shape_node_tooltip(self, node_id: int) -> str | None:
        """A box with the joint and its components in the mode the animator draws."""
        from opensees_studio.core.hover import node_mode_shape

        project = self._vm.project
        results = self._results.latest
        view = self.dock.widget() if self.dock is not None else None
        if project is None or not isinstance(results, ModalResults):
            return None
        if not isinstance(view, ModeShapeAnimator):
            return None
        mode = view.current_mode() + 1
        rows = node_mode_shape(project, results, node_id, mode)
        if rows is None:
            return None
        periods = results.periods
        subtitle = tr("Mode {n}").format(n=mode)
        if mode - 1 < len(periods):
            subtitle += f" · T = {float(periods[mode - 1]):.4g} s"
        return self._node_box(
            self._joint_title(node_id),
            subtitle,
            [(label, f"{value:.4g}", "") for label, value, _rotation in rows],
        )

    def _deformed_node_tooltip(self, node_id: int) -> str | None:
        """A box with the joint and its displacements in the case the deformed shape draws."""
        from opensees_studio.core.hover import node_displacements

        project = self._vm.project
        view = self.dock.widget() if self.dock is not None else None
        bound = view.current_bound() if isinstance(view, DeformedShapeView) else "max"
        results = self._results.static(bound)
        if project is None or results is None:
            return None
        rows = node_displacements(project, results, node_id)
        if rows is None:
            return None
        case = self._results.caption_for(self._vm.project, self._results.latest).split("  ·  ")[0]
        if self._results.is_envelope():
            case += " · " + (tr("Max") if bound == "max" else tr("Min"))
        converter = UnitConverter.of(project.meta)
        length = converter.labels.length
        return self._node_box(
            self._joint_title(node_id),
            tr("Case: {name}").format(name=case),
            [
                (
                    label,
                    f"{value if rotation else value * converter.length:.6g}",
                    "rad" if rotation else length,
                )
                for label, value, rotation in rows
            ],
        )

    def element_tooltip(self, element_id: int) -> str | None:
        """Hover text for the canvas: a bearing's key parameters, else the element summary."""
        from opensees_studio.core import BEARING_CLASSES, SLIDING_BEARING_CLASSES
        from opensees_studio.core.hover import element_summary

        if self._vm.project is None:
            return None
        try:
            el = self._vm.project.element(element_id)
        except KeyError:
            return None
        if not isinstance(el, BEARING_CLASSES):
            return element_summary(self._vm.project, element_id)
        if isinstance(el, SLIDING_BEARING_CLASSES):
            try:
                friction = self._vm.project.friction_model(el.friction_model_id).type
            except KeyError:
                friction = "missing"
            lines = [
                f"{el.type} #{el.id}, nodes {el.nodes[0]}-{el.nodes[1]}",
                f"Kinit = {el.k_init:g}, friction model #{el.friction_model_id} ({friction})",
            ]
            if el.type == "SingleFPBearing":
                units = self._vm.project.meta.units
                lines.append(
                    f"Reff = {el.r_eff:g}, T = 2 pi sqrt(Reff / g) = "
                    f"{el.isolated_period(units):.4g} s"
                )
            return "\n".join(lines)
        lines = [
            f"{el.type} #{el.id}, nodes {el.nodes[0]}-{el.nodes[1]}",
            f"Kinit = {el.k_init:g}, Qd = {el.qd:g}, alpha1 = {el.alpha1:g}",
            f"u_y = {el.yield_displacement:.6g}, F_y = {el.yield_force:.6g}",
        ]
        if el.alpha2:
            lines.append(f"alpha2 = {el.alpha2:g}, mu = {el.mu:g}")
        if el.type == "ElastomericBearingBoucWen":
            lines.append(f"eta = {el.eta:g}, beta = {el.beta:g}, gamma = {el.gamma:g}")
        return "\n".join(lines)

    # ── leaving a view ───────────────────────────────────────────────
    def back_to_model(self) -> None:
        """Display → Back to Model View: close the view and clear every overlay."""
        self.tear_down()
        self.set_caption(None)
        self._diagram.clear()
        self._contours.clear()
        self._ratios.clear()
        self._shell.canvas()._renderer.set_mode(RendererMode.MODEL)
        self._shell.canvas().render()

    def tear_down(self) -> None:
        """Remove the open view's dock; the overlays stay for the next view to replace."""
        if self.dock is not None:
            self._window.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        self.mode = None
        if self.title is not None:
            # The next view names itself; until then the caption is the case alone.
            self.set_title(None)
        self._units_refresh = None
        self._close_member_windows()
