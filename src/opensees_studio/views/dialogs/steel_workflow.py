"""Guided seven-stage steel-design workflow.

The engine already keeps AISC 360, AISC 341, AISC 358, Chapter J and ASCE 7
separate. This dialog is the front end that orders them the way an engineer
works: design basis, model and loads, demands, member check, seismic system,
connections, detailing.

It does not re-implement any check. Each stage shows the state of the current
project and links to the dialog that edits or runs it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from opensees_studio.core.design.settings import DesignSettings
from opensees_studio.core.help import TOPIC_PROPERTY
from opensees_studio.core.units import labels_for
from opensees_studio.services.steel_design import (
    DesignReport,
    default_fu,
    default_fy,
    steel_frame_check,
)
from opensees_studio.views.screen_fit import FittedDialog

_STAGES = [
    ("1. Base de diseño AISC/ASCE", "Código, método, materiales, sistema sísmico y análisis."),
    ("2. Modelo de análisis y cargas", "Miembros, perfiles, cargas, casos y combinaciones."),
    ("3. Demandas por estación", "Fuerzas internas, 25 estaciones y load sets."),
    ("4. Chequeo de miembros AISC 360", "D2, E3/E4/E7, F2-F10, G2/G6 y H1."),
    ("5. Chequeo sísmico AISC 341", "D1.1, SMF/IMF, SCBF, OCBF y capacidad."),
    ("6. Conexiones AISC 358 + Chapter J", "RBS, gussets, empalmes y J2-J10."),
    ("7. Detallado y entrega", "Ratios, reporte, memoria y QA."),
]

_STATUS_COLORS = {
    "OK": "#2b8a3e",
    "PENDIENTE": "#6b7280",
    "REVISAR": "#c92a2a",
    "N/A": "#6b7280",
}


def _stress_text(value: float, unit: str) -> str:
    """A stress in a readable unit, without changing the model."""
    if unit == "Pa":
        return f"{value / 1e6:.4g} MPa"
    return f"{value:.4g} {unit}"


class SteelWorkflowDialog(FittedDialog):
    """Seven-stage guide over the existing steel-design checks."""

    def __init__(
        self,
        project: Any,
        results_provider: Callable[[], dict[int, Any]],
        controller: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._results_provider = results_provider
        self._controller = controller
        self._report: DesignReport | None = None
        self._report_error: str | None = None
        self._statuses: list[str] = ["PENDIENTE"] * len(_STAGES)
        self._summaries: list[QLabel] = []
        self._status_labels: list[QLabel] = []
        self._buttons: list[list[QPushButton]] = []

        self.setWindowTitle("Steel Design Workflow")
        self.setProperty(TOPIC_PROPERTY, "design.steel_workflow")
        self.resize(1120, 760)
        self._build_ui()
        self.refresh()

    # ── construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "<b>Steel Design Workflow</b><br>"
                "AISC 360-16 member check → AISC 341-22 seismic → AISC 358-22 / Chapter J connections → detailing"
            )
        )

        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.setMinimumWidth(330)
        self._list.setMaximumWidth(390)
        for title, _description in _STAGES:
            self._list.addItem(QListWidgetItem(title))
        self._list.currentRowChanged.connect(self._show_stage)
        body.addWidget(self._list)
        self._pages = QStackedWidget()
        for index, (title, description) in enumerate(_STAGES):
            self._pages.addWidget(self._build_page(index, title, description))
        body.addWidget(self._pages, 1)
        root.addLayout(body, 1)

        nav = QHBoxLayout()
        self._back = QPushButton("< Back")
        self._back.clicked.connect(self._previous)
        self._next = QPushButton("Next >")
        self._next.clicked.connect(self._next_stage)
        self._refresh = QPushButton("Refresh")
        self._refresh.clicked.connect(self.refresh)
        nav.addWidget(self._back)
        nav.addWidget(self._next)
        nav.addWidget(self._refresh)
        nav.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        nav.addWidget(buttons)
        root.addLayout(nav)
        self._list.setCurrentRow(0)

    def _build_page(self, index: int, title: str, description: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        subtitle = QLabel(description)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Estado:"))
        status = QLabel("PENDIENTE")
        status.setStyleSheet("font-weight: bold;")
        status_row.addWidget(status)
        status_row.addStretch(1)
        layout.addLayout(status_row)
        self._status_labels.append(status)

        summary_box = QGroupBox("Estado actual")
        summary_layout = QVBoxLayout(summary_box)
        summary = QLabel("")
        summary.setWordWrap(True)
        summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        summary_layout.addWidget(summary)
        layout.addWidget(summary_box, 1)
        self._summaries.append(summary)

        actions = QHBoxLayout()
        page_buttons: list[QPushButton] = []
        for text, method in self._page_actions(index):
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, name=method: self._call(name))
            actions.addWidget(button)
            page_buttons.append(button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self._buttons.append(page_buttons)
        return page

    def _page_actions(self, index: int) -> list[tuple[str, str]]:
        if index == 0:
            return [
                ("Editar parámetros AISC...", "edit_steel_settings"),
                ("Cargas notionales DAM...", "open_notional_loads"),
                ("Deriva...", "open_drift_check"),
            ]
        if index == 1:
            return [
                ("Casos de análisis...", "open_analysis_cases"),
                ("Ejecutar análisis...", "run_analysis"),
            ]
        if index == 2:
            return [("Actualizar", "refresh")]
        if index == 3:
            return [("Abrir chequeo AISC 360...", "open_member_check")]
        if index == 4:
            return [
                ("Gussets...", "open_gussets"),
                ("Empalmes...", "open_column_splices"),
                ("Conexiones RBS...", "open_connections"),
            ]
        if index == 5:
            return [
                ("Conexiones RBS...", "open_connections"),
                ("Gussets...", "open_gussets"),
                ("Empalmes...", "open_column_splices"),
                ("Chapter J...", "open_chapter_j"),
            ]
        return [
            ("Mostrar ratios...", "show_steel_ratios"),
            ("Exportar reporte...", "export_report"),
            ("Memoria de cálculo...", "open_calc_memory"),
        ]

    # ── state ───────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Re-read the project and recompute the report behind the stages."""
        self._report = None
        self._report_error = None
        settings = self._project.design or DesignSettings()
        results = self._results_provider()
        try:
            self._report = steel_frame_check(self._project, results, settings)
        except Exception as exc:  # a check that cannot run is a stage state, not a crash
            self._report_error = str(exc)
        self._statuses = self._compute_statuses(settings, results)
        self._update_list()
        self._update_pages(settings, results)

    def _compute_statuses(self, settings: DesignSettings, results: dict[int, Any]) -> list[str]:
        report = self._report
        frame_members = [el for el in self._project.elements if len(el.nodes) == 2]
        stage1 = "OK" if self._project.design is not None else "PENDIENTE"
        stage2 = "OK" if frame_members and results else "PENDIENTE"
        stage3 = (
            "REVISAR"
            if self._report_error
            else ("OK" if report and report.load_sets else "PENDIENTE")
        )
        designed = [m for m in report.members if m.status != "not designed"] if report else []
        failing = [m for m in report.members if m.status == "NG"] if report else []
        stage4 = "REVISAR" if failing else ("OK" if designed else "PENDIENTE")
        if settings.seismic_system == "none":
            stage5 = "OK"
        elif report is None:
            stage5 = "PENDIENTE"
        else:
            seismic_ng = any(j.status == "NG" or j.panel_status == "NG" for j in report.joints)
            seismic_ng = seismic_ng or any(j.status == "NG" for j in report.scbf_joints)
            seismic_ng = seismic_ng or any(g.status == "NG" for g in report.gussets)
            seismic_ng = seismic_ng or any(s.status == "NG" for s in report.column_splices)
            seismic_ng = seismic_ng or any(not z.zone_clear for z in report.protected_zones)
            has_seismic = bool(
                report.joints
                or report.capacity_design
                or report.scbf_joints
                or report.protected_zones
                or report.gussets
                or report.column_splices
            )
            stage5 = "REVISAR" if seismic_ng else ("OK" if has_seismic else "PENDIENTE")
        connection_items = (
            list(report.connections)
            + list(report.gussets)
            + list(report.column_splices)
            + list(report.chapter_j)
            if report
            else []
        )
        connection_ng = any(getattr(item, "status", "") == "NG" for item in connection_items)
        stage6 = "REVISAR" if connection_ng else ("OK" if connection_items else "PENDIENTE")
        if "REVISAR" in (stage4, stage5, stage6):
            stage7 = "REVISAR"
        elif all(status == "OK" for status in (stage4, stage5, stage6)):
            stage7 = "OK"
        else:
            stage7 = "PENDIENTE"
        return [stage1, stage2, stage3, stage4, stage5, stage6, stage7]

    def _update_list(self) -> None:
        current = self._list.currentRow()
        for index, (title, _description) in enumerate(_STAGES):
            status = self._statuses[index]
            item = self._list.item(index)
            item.setText(f"{title}  [{status}]")
            item.setForeground(QBrush(QColor(_STATUS_COLORS[status])))
        if current >= 0:
            self._list.setCurrentRow(current)

    def _update_pages(self, settings: DesignSettings, results: dict[int, Any]) -> None:
        labels = labels_for(self._project.meta.units)
        fy = settings.fy if settings.fy is not None else default_fy(self._project.meta.units)
        fu = settings.fu if settings.fu is not None else default_fu(self._project.meta.units)
        self._summaries[0].setText(
            "\n".join(
                [
                    f"Método: {settings.method}",
                    f"Fy: {_stress_text(fy, labels.stress)} · Fu: {_stress_text(fu, labels.stress)}",
                    f"Sistema sísmico: {settings.seismic_system} · Ry: {settings.ry:g}",
                    f"B1 P-delta: {'on' if settings.p_delta else 'off'}",
                    f"Load sets: {len(settings.load_sets) or 'todos los casos/combinaciones'}",
                ]
            )
        )
        frame_members = [el for el in self._project.elements if len(el.nodes) == 2]
        self._summaries[1].setText(
            "\n".join(
                [
                    f"Miembros frame: {len(frame_members)}",
                    f"Casos: {len(self._project.analyses)} · Combinaciones: {len(self._project.combinations)}",
                    f"Resultados vigentes: {len(results)}",
                    f"Perfiles AISC chequeables: {sum(1 for m in self._report.members if m.status != 'not designed') if self._report else 0}",
                ]
            )
        )
        report = self._report
        self._summaries[2].setText(
            "\n".join(
                [
                    f"Load sets: {len(report.load_sets) if report else 0}",
                    "Estaciones por miembro: 25",
                    f"Miembros con demanda: {sum(1 for m in report.members if m.status != 'not designed') if report else 0}",
                    f"Chequeo: {'listo' if report else (self._report_error or 'pendiente')}",
                ]
            )
        )
        if report:
            designed = [m for m in report.members if m.status != "not designed"]
            failing = [m for m in report.members if m.status == "NG"]
            worst = max(designed, key=lambda m: m.ratio, default=None)
            worst_text = f"{worst.ratio:.3f} (elemento {worst.element_id})" if worst else "—"
            self._summaries[3].setText(
                "\n".join(
                    [
                        f"Chequeados: {len(designed)} · Sobre el límite: {len(failing)} · No diseñados: {len(report.members) - len(designed)}",
                        f"Peor ratio: {worst_text}",
                        f"Resumen: {report.summary()}",
                    ]
                )
            )
        else:
            self._summaries[3].setText(self._report_error or "Sin resultados para chequear.")

        if settings.seismic_system == "none":
            seismic_text = "No hay capa sísmica activa. Configure un sistema en la etapa 1."
        elif report:
            joints_ng = sum(1 for j in report.joints if j.status == "NG")
            panel_ng = sum(1 for j in report.joints if j.panel_status == "NG")
            seismic_text = "\n".join(
                [
                    f"Sistema: {settings.seismic_system}",
                    f"Juntas SMF/IMF: {len(report.joints)} · NG: {joints_ng} · Panel zone NG: {panel_ng}",
                    f"Capacity design: {len(report.capacity_design)} · Juntas SCBF: {len(report.scbf_joints)}",
                    f"Zonas protegidas: {len(report.protected_zones)} · Gussets: {len(report.gussets)} · Empalmes: {len(report.column_splices)}",
                ]
            )
        else:
            seismic_text = self._report_error or "Sin resultados para el chequeo sísmico."
        self._summaries[4].setText(seismic_text)

        if report:
            rbs_ng = sum(1 for c in report.connections if c.status == "NG")
            gusset_ng = sum(1 for g in report.gussets if g.status == "NG")
            splice_ng = sum(1 for s in report.column_splices if s.status == "NG")
            chapter_ng = sum(1 for c in report.chapter_j if c.status == "NG")
            self._summaries[5].setText(
                "\n".join(
                    [
                        f"RBS: {len(report.connections)} · NG: {rbs_ng}",
                        f"Gussets: {len(report.gussets)} · NG: {gusset_ng}",
                        f"Empalmes: {len(report.column_splices)} · NG: {splice_ng}",
                        f"Chapter J: {len(report.chapter_j)} · NG: {chapter_ng}",
                    ]
                )
            )
        else:
            self._summaries[5].setText(
                self._report_error or "Sin conexiones definidas o sin resultados."
            )

        self._summaries[6].setText(
            "\n".join(
                [
                    f"Miembros: {self._statuses[3]} · Sísmico: {self._statuses[4]} · Conexiones: {self._statuses[5]}",
                    "Salidas: ratios en el modelo, reporte HTML/PDF y memoria de cálculo.",
                    "El detallado final y la revisión del ingeniero no se sustituyen por el chequeo.",
                ]
            )
        )

        for index, status in enumerate(self._statuses):
            label = self._status_labels[index]
            label.setText(status)
            label.setStyleSheet(f"font-weight: bold; color: {_STATUS_COLORS[status]};")

    # ── navigation and actions ──────────────────────────────────────

    def _show_stage(self, index: int) -> None:
        if index < 0:
            return
        self._pages.setCurrentIndex(index)
        self._back.setEnabled(index > 0)
        self._next.setEnabled(index < len(_STAGES) - 1)

    def _previous(self) -> None:
        self._list.setCurrentRow(max(self._list.currentRow() - 1, 0))

    def _next_stage(self) -> None:
        self._list.setCurrentRow(min(self._list.currentRow() + 1, len(_STAGES) - 1))

    def _call(self, method_name: str) -> None:
        if method_name == "refresh":
            self.refresh()
            return
        method = getattr(self._controller, method_name, None)
        if method is not None:
            method()
        self.refresh()
