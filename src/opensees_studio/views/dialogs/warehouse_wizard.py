"""Warehouse wizard: a 3D steel warehouse from a few numbers.

Five pages, in the order the questions come up: how big the building is, what
runs between the frames (purlins, girts, bracing, end wall columns), what the
members are made of, what the roof carries under which design code, and the
wind. A wireframe preview on the side follows every field.

Everything it builds comes from :mod:`opensees_studio.core.warehouse`; the
wizard is fields, the preview and their translation into a
:class:`~opensees_studio.core.warehouse.WarehouseSpec`, a section choice and a
:class:`~opensees_studio.core.warehouse.WarehouseLoads`. The caller plans and
inserts the result (``commands.warehouse``), so cancelling leaves nothing
behind.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
    QWizard,
    QWizardPage,
)

from opensees_studio.core.code_combinations import CODES
from opensees_studio.core.help import TOPIC_PROPERTY
from opensees_studio.core.units import UnitSystem, labels_for
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    DEFAULT_ROOF_DEAD_KPA,
    GROUP_COLOURS,
    GROUPS,
    SECTION_KEYS,
    WIND_METHODS,
    Warehouse,
    WarehouseError,
    WarehouseLoads,
    WarehouseSpec,
    WarehouseWind,
    build_warehouse,
    default_section_name,
    force_from_kn,
    length_from_m,
    pressure_from_kpa,
    warehouse_wind_cases,
)
from opensees_studio.core.wind import (
    DIRECTIONS,
    OPENINGS,
    RNC07_REGIONAL_SPEEDS,
)
from opensees_studio.views.dialogs.frame_wizard import (
    ROOF_CHOICES,
    SUPPORT_CHOICES,
    _CompletablePage,
    _field,
)
from opensees_studio.views.i18n import tr
from opensees_studio.views.screen_fit import fit_to_available_screen

#: What a section combo reports for "create the default section".
CREATE_DEFAULT = -1

_COS30 = math.cos(math.radians(30.0))

#: Exposure choices per wind procedure: (key, label).
WIND_EXPOSURES: dict[str, tuple[tuple[str, str], ...]] = {
    "rnc07": (
        ("R1", "R1: open country, few or no obstructions"),
        ("R2", "R2: flat or rolling terrain with few obstructions"),
        ("R3", "R3: urban and suburban area"),
        ("R4", "R4: dense area of tall buildings"),
    ),
    "asce7": (
        ("B", "B: urban, suburban or wooded terrain"),
        ("C", "C: open terrain with scattered obstructions"),
        ("D", "D: flat, unobstructed terrain facing open water"),
    ),
}
#: The exposure each procedure starts with.
DEFAULT_EXPOSURE: dict[str, str] = {"rnc07": "R2", "asce7": "C"}

#: RNC-07 Tabla 7: (key, label).
WIND_TOPOGRAPHIES: tuple[tuple[str, str], ...] = (
    ("T1", "T1: sheltered base of a hill, leeward side"),
    ("T2", "T2: closed valley"),
    ("T3", "T3: flat terrain, slopes below 5 % (normal)"),
    ("T4", "T4: slopes between 5 and 10 %"),
    ("T5", "T5: hilltops, slopes above 10 %"),
)

#: Labels of :data:`opensees_studio.core.wind.OPENINGS`, in its order.
WIND_OPENINGS: tuple[str, ...] = (
    "Closed building",
    "Openings spread over the four walls",
    "Openings mainly in the side wall at the smallest X",
    "Openings mainly in the side wall at the largest X",
    "Openings mainly in the end wall at the smallest Y",
    "Openings mainly in the end wall at the largest Y",
)


class WarehousePreview(QWidget):
    """An isometric wireframe of the warehouse, one colour per member group."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lines: list[tuple[QColor, list[tuple[QPointF, QPointF]]]] = []
        self._bounds = (0.0, 0.0, 1.0, 1.0)
        self.setMinimumSize(300, 260)

    def sizeHint(self) -> QSize:
        return QSize(340, 320)

    def line_count(self) -> int:
        """Members drawn (for the tests)."""
        return sum(len(lines) for _colour, lines in self._lines)

    def set_warehouse(self, warehouse: Warehouse | None) -> None:
        """Draw ``warehouse``; None clears the preview."""
        self._lines = []
        if warehouse is not None:
            ox, oy, oz = warehouse.spec.origin

            def project(coords: tuple[float, ...]) -> QPointF:
                x, y, z = coords[0] - ox, coords[1] - oy, coords[2] - oz
                return QPointF((x + y) * _COS30, (y - x) * 0.5 + z)

            points = {node.id: project(node.coords) for node in warehouse.nodes}
            ends = {e.id: e.nodes for e in warehouse.elements}
            for key in GROUPS:
                segments = [
                    (points[ends[eid][0]], points[ends[eid][1]]) for eid in warehouse.members[key]
                ]
                if segments:
                    self._lines.append((QColor(GROUP_COLOURS[key]), segments))
            us = [p.x() for p in points.values()]
            vs = [p.y() for p in points.values()]
            self._bounds = (min(us), min(vs), max(us), max(vs))
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self.palette().base())
        if not self._lines:
            return
        u0, v0, u1, v1 = self._bounds
        margin = 12.0
        scale = min(
            (self.width() - 2 * margin) / max(u1 - u0, 1e-9),
            (self.height() - 2 * margin) / max(v1 - v0, 1e-9),
        )
        left = (self.width() - (u1 - u0) * scale) / 2.0
        top = (self.height() - (v1 - v0) * scale) / 2.0

        def screen(p: QPointF) -> QPointF:
            return QPointF(left + (p.x() - u0) * scale, top + (v1 - p.y()) * scale)

        for colour, segments in self._lines:
            painter.setPen(QPen(colour, 1.2))
            for a, b in segments:
                painter.drawLine(screen(a), screen(b))
        painter.end()


class WarehouseWizard(QWizard):
    """Collects a warehouse's geometry, sections and loads."""

    def __init__(
        self,
        sections: list[Any],
        *,
        units: UnitSystem = UnitSystem.SI_M_N,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sections = sections
        self._units = units
        labels = labels_for(units)
        self._unit = labels.length
        self._force = labels.force
        self._pressure = f"{labels.force}/{labels.length}²"
        self._error = ""
        self.setWindowTitle("Warehouse Wizard")
        self.setProperty(TOPIC_PROPERTY, "define.warehouse")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self._preview = WarehousePreview()
        self.setSideWidget(self._preview)

        self._build_geometry_page()
        self._build_secondary_page()
        self._build_sections_page()
        self._build_loads_page()
        self._build_wind_page()
        for index, page in enumerate(
            (
                self._page_geometry,
                self._page_secondary,
                self._page_sections,
                self._page_loads,
                self._page_wind,
            )
        ):
            self.setPage(index, page)
        self._on_code_changed()
        self._refresh()
        self.resize(880, 640)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not event.spontaneous():
            fit_to_available_screen(self)

    def _length(self, metres: float, *, minimum: float = 0.0) -> Any:
        value = length_from_m(metres, self._units)
        return _field(
            value, minimum=minimum, maximum=1e9, step=length_from_m(0.5, self._units), suffix=self._unit
        )  # fmt: skip

    # ── pages ───────────────────────────────────────────────────────
    def _build_geometry_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not self._error
        page.setTitle("Geometry")
        page.setSubTitle("Naves across, frames along, eave height and roof profile.")
        form = QFormLayout(page)

        self._roof = QComboBox()
        for label, _roof, _has_slope in ROOF_CHOICES:
            self._roof.addItem(tr(label))
        self._span = self._length(20.0)
        self._n_naves = QSpinBox()
        self._n_naves.setRange(1, 10)
        self._n_naves.setToolTip("Naves side by side, with a column line between them.")
        self._n_frames = QSpinBox()
        self._n_frames.setRange(2, 200)
        self._n_frames.setValue(6)
        self._n_frames.setToolTip("Portal frames along the building, the two end frames included.")
        self._frame_spacing = self._length(6.0)
        self._eave_height = self._length(6.0)
        self._slope = _field(10.0, minimum=0.0, maximum=99.0, step=1.0, suffix="%")
        self._support = QComboBox()
        for label, _support in SUPPORT_CHOICES:
            self._support.addItem(tr(label))
        self._support.setCurrentIndex(1)

        form.addRow("Roof:", self._roof)
        form.addRow("Nave span:", self._span)
        form.addRow("Number of naves:", self._n_naves)
        form.addRow("Number of frames:", self._n_frames)
        form.addRow("Distance between frames:", self._frame_spacing)
        form.addRow("Eave height:", self._eave_height)
        form.addRow("Slope:", self._slope)
        form.addRow("Column bases:", self._support)

        self._geometry_summary = QLabel()
        self._geometry_summary.setWordWrap(True)
        form.addRow(self._geometry_summary)

        for field in (self._span, self._frame_spacing, self._eave_height, self._slope):
            field.valueChanged.connect(self._refresh)
        for spin in (self._n_naves, self._n_frames):
            spin.valueChanged.connect(self._refresh)
        for combo in (self._roof, self._support):
            combo.currentIndexChanged.connect(self._refresh)
        self._page_geometry = page

    def _build_secondary_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not self._error
        page.setTitle("Purlins, girts and bracing")
        page.setSubTitle("The members between the frames, and which of them brace the frames.")
        form = QFormLayout(page)

        self._purlin_spacing = self._length(1.5)
        self._purlin_spacing.setToolTip(
            "Largest distance between purlin lines, on the roof surface. Each roof slope "
            "is divided into equal parts no longer than this."
        )
        self._rafter_fly = QSpinBox()
        self._rafter_fly.setRange(0, 50)
        self._rafter_fly.setSpecialValueText(tr("None"))
        self._rafter_fly.setToolTip(
            "A purlin alone does not brace the rafter: it sits on the top flange. Enter 1 "
            "when every purlin has a stabilising angle to the bottom flange, 2 for every "
            "second purlin, and so on. The steel check takes the rafter's unbraced length "
            "between those purlins; with none, from the eave to the ridge."
        )
        self._girt_spacing = self._length(1.5)
        self._girt_spacing.setToolTip(
            "Largest distance between girt lines on the two side walls; 0 builds no girts."
        )
        self._column_fly = QSpinBox()
        self._column_fly.setRange(0, 50)
        self._column_fly.setSpecialValueText(tr("None"))
        self._column_fly.setToolTip(
            "As for the purlins: a girt braces the column only where it has a stabilising "
            "angle to the inner flange."
        )
        self._end_wall_spacing = self._length(5.0)
        self._end_wall_spacing.setToolTip(
            "Largest distance between the columns of the two end walls; 0 builds none. Each "
            "nave is divided into equal parts and each column stands under the nearest "
            "purlin line, pinned at both ends. With end wall columns the end walls also get "
            "girts, at the girt spacing."
        )
        self._roof_bracing = QCheckBox("X bracing in the roof")
        self._roof_bracing.setChecked(True)
        self._wall_bracing = QCheckBox("X bracing in the side walls")
        self._wall_bracing.setChecked(True)
        self._braced_bays = QLineEdit()
        self._braced_bays.setPlaceholderText("First and last bay")
        self._braced_bays.setToolTip(
            "Bay numbers with bracing, separated by commas (bay 1 is between the first two "
            "frames). Leave empty for the first and the last bay."
        )

        form.addRow("Purlin spacing:", self._purlin_spacing)
        form.addRow("Stabilising angle every (purlins):", self._rafter_fly)
        form.addRow("Girt spacing:", self._girt_spacing)
        form.addRow("Stabilising angle every (girts):", self._column_fly)
        form.addRow("End wall column spacing:", self._end_wall_spacing)
        form.addRow(self._roof_bracing)
        form.addRow(self._wall_bracing)
        form.addRow("Braced bays:", self._braced_bays)

        note = QLabel(
            "<i>Purlins, girts and braces are pinned at both ends: they carry their load "
            "to the frames and add no bending or torsional restraint to them.</i>"
        )
        note.setWordWrap(True)
        form.addRow(note)
        self._secondary_summary = QLabel()
        self._secondary_summary.setWordWrap(True)
        form.addRow(self._secondary_summary)

        for field in (self._purlin_spacing, self._girt_spacing, self._end_wall_spacing):
            field.valueChanged.connect(self._refresh)
        for spin in (self._rafter_fly, self._column_fly):
            spin.valueChanged.connect(self._refresh)
        for box in (self._roof_bracing, self._wall_bracing):
            box.toggled.connect(self._refresh)
        self._braced_bays.textChanged.connect(self._refresh)
        self._page_secondary = page

    def _build_sections_page(self) -> None:
        page = QWizardPage()
        page.setTitle("Sections")
        page.setSubTitle("One section for each kind of member.")
        form = QFormLayout(page)
        self._section_combos: dict[str, QComboBox] = {}
        for key, label in SECTION_KEYS.items():
            combo = QComboBox()
            combo.addItem(
                tr("{name} (will be created)").format(name=default_section_name(key)),
                userData=CREATE_DEFAULT,
            )
            for section in self._sections:
                combo.addItem(f"#{section.id}  {section.name or '(unnamed)'}", userData=section.id)
            self._section_combos[key] = combo
            form.addRow(tr(label) + ":", combo)
        note = QLabel(
            "<i>The sections that do not exist yet are created with the warehouse, as the "
            "same undoable step: columns, rafters and braces from the AISC library, purlins "
            "and girts as a cold-formed lipped channel. The end wall column section is used "
            "only when the warehouse has end wall columns.</i>"
        )
        note.setWordWrap(True)
        form.addRow(note)
        self._page_sections = page

    def _build_loads_page(self) -> None:
        page = QWizardPage()
        page.setTitle("Loads and design code")
        page.setSubTitle("What the roof carries, and the code that combines it.")
        form = QFormLayout(page)

        self._code = QComboBox()
        for key in CODE_PRESETS:
            self._code.addItem(CODES[key].label, userData=key)
        self._roof_dead = _field(
            pressure_from_kpa(DEFAULT_ROOF_DEAD_KPA, self._units),
            minimum=0.0, maximum=1e12, step=0.0, suffix=self._pressure,
        )  # fmt: skip
        self._roof_dead.setToolTip(
            "Weight of the cladding and its fixings per area of roof surface. The self "
            "weight of the steel members is already in the dead load case."
        )
        self._roof_live = _field(0.0, minimum=0.0, maximum=1e12, step=0.0, suffix=self._pressure)
        self._point = _field(0.0, minimum=0.0, maximum=1e12, step=0.0, suffix=self._force)
        self._point.setToolTip(
            "A concentrated live load at mid-span of each nave of every frame, in the roof "
            "live load case."
        )
        self._combinations = QCheckBox("Generate the load combinations of the code")
        self._combinations.setChecked(True)
        self._design_lengths = QCheckBox("Set the unbraced lengths of the steel check")
        self._design_lengths.setChecked(True)
        self._design_lengths.setToolTip(
            "Writes, for every rafter and side column, the distance between purlins or "
            "girts with a stabilising angle as its unbraced length (Design → Steel Frame "
            "Check)."
        )

        form.addRow("Design code:", self._code)
        form.addRow("Roof dead load:", self._roof_dead)
        form.addRow("Roof live load:", self._roof_live)
        form.addRow("Live load at mid-span:", self._point)
        form.addRow(self._combinations)
        form.addRow(self._design_lengths)
        self._code_note = QLabel()
        self._code_note.setWordWrap(True)
        form.addRow(self._code_note)
        note = QLabel(
            "<i>The loads are applied to the purlins, as uniform loads over their "
            "tributary width. The wind is on the next page; earthquake cases are not "
            "created here.</i>"
        )
        note.setWordWrap(True)
        form.addRow(note)
        self._code.currentIndexChanged.connect(self._on_code_changed)
        self._page_loads = page

    def _build_wind_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not self._wind_error
        page.setTitle("Wind")
        page.setSubTitle("The wind cases on the walls and the roof, one or two per direction.")
        form = QFormLayout(page)
        self._wind_error = ""

        self._wind_on = QCheckBox("Create the wind load cases")
        self._wind_on.setChecked(True)
        self._wind_method = QComboBox()
        for key, label in WIND_METHODS.items():
            self._wind_method.addItem(tr(label), userData=key)
        self._wind_zone = QComboBox()
        for zone, speeds in RNC07_REGIONAL_SPEEDS.items():
            for group, speed in zip(("B", "A"), speeds, strict=True):
                self._wind_zone.addItem(
                    tr("Zone {zone}, Group {group}: {speed} m/s").format(
                        zone=zone, group=group, speed=f"{speed:g}"
                    ),
                    userData=speed,
                )
        self._wind_zone.addItem(tr("Other velocity"), userData=None)
        self._wind_zone.setToolTip(
            "RNC-07 Tabla 5: regional velocity per wind zone (Figura 7), 50 years of return "
            "period for Group B and 200 years for Group A."
        )
        self._wind_speed = _field(45.0, minimum=0.0, maximum=200.0, step=1.0, suffix="m/s")
        self._wind_exposure = QComboBox()
        self._wind_topography = QComboBox()
        for key, label in WIND_TOPOGRAPHIES:
            self._wind_topography.addItem(tr(label), userData=key)
        self._wind_topography.setCurrentIndex(2)
        self._wind_kzt = _field(1.0, minimum=0.0, maximum=10.0, step=0.1)
        self._wind_kzt.setToolTip("ASCE 7-16 26.8: 1 on flat terrain.")
        self._wind_openings = QComboBox()
        for label in WIND_OPENINGS:
            self._wind_openings.addItem(tr(label))
        self._wind_openings.setToolTip(
            "RNC-07 Art. 55 adds internal pressure when the openings of a wall exceed 30 % "
            "of it. ASCE 7-16 takes ±0.18 for an enclosed building and ±0.55 with a "
            "dominant opening in one wall (partially enclosed)."
        )
        self._wind_directions: dict[str, QCheckBox] = {}
        directions = QHBoxLayout()
        for direction in DIRECTIONS:
            box = QCheckBox(direction)
            box.setChecked(True)
            box.toggled.connect(self._refresh_wind)
            self._wind_directions[direction] = box
            directions.addWidget(box)
        directions.addStretch(1)

        for combo in (
            self._wind_method,
            self._wind_zone,
            self._wind_exposure,
            self._wind_topography,
            self._wind_openings,
        ):
            # A long description must not widen the page past the wizard.
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(24)
        form.addRow(self._wind_on)
        form.addRow("Procedure:", self._wind_method)
        form.addRow("Wind zone:", self._wind_zone)
        form.addRow("Wind speed:", self._wind_speed)
        form.addRow("Exposure:", self._wind_exposure)
        form.addRow("Topography:", self._wind_topography)
        form.addRow("Topographic factor Kzt:", self._wind_kzt)
        form.addRow("Openings:", self._wind_openings)
        form.addRow("Wind towards:", directions)
        self._wind_summary = QLabel()
        self._wind_summary.setWordWrap(True)
        form.addRow(self._wind_summary)
        note = QLabel(
            "<i>The pressures are those of the main structure, applied to the purlins, the "
            "girts and the columns. Purlins, girts and cladding also need the local "
            "pressures of the code, which are not created here.</i>"
        )
        note.setWordWrap(True)
        form.addRow(note)

        self._wind_on.toggled.connect(self._refresh_wind)
        self._wind_method.currentIndexChanged.connect(self._on_wind_method_changed)
        self._wind_zone.currentIndexChanged.connect(self._on_wind_zone_changed)
        self._wind_speed.valueChanged.connect(self._on_wind_speed_edited)
        self._wind_kzt.valueChanged.connect(self._refresh_wind)
        for combo in (self._wind_exposure, self._wind_topography, self._wind_openings):
            combo.currentIndexChanged.connect(self._refresh_wind)
        self._page_wind = page
        self._on_wind_method_changed()

    # ── live state ──────────────────────────────────────────────────
    def _on_code_changed(self, _index: int = 0) -> None:
        preset = CODE_PRESETS[self._code.currentData()]
        self._roof_live.setValue(pressure_from_kpa(preset.roof_live_kpa, self._units))
        self._point.setValue(force_from_kn(preset.midspan_point_kn, self._units))
        self._roof_live.setToolTip(
            tr("Live load per area of horizontal projection.") + "\n" + tr(preset.source)
        )
        self._code_note.setText("<i>" + tr(preset.source) + "</i>")
        index = self._wind_method.findData(preset.wind_method)
        if index != self._wind_method.currentIndex():
            self._wind_method.setCurrentIndex(index)
        else:
            self._on_wind_method_changed()

    def _on_wind_method_changed(self, _index: int = 0) -> None:
        method = str(self._wind_method.currentData())
        rnc = method == "rnc07"
        self._wind_exposure.blockSignals(True)
        self._wind_exposure.clear()
        for key, label in WIND_EXPOSURES[method]:
            self._wind_exposure.addItem(tr(label), userData=key)
        self._wind_exposure.setCurrentIndex(self._wind_exposure.findData(DEFAULT_EXPOSURE[method]))
        self._wind_exposure.blockSignals(False)
        self._wind_zone.setEnabled(rnc)
        self._wind_topography.setEnabled(rnc)
        self._wind_kzt.setEnabled(not rnc)
        preset = CODE_PRESETS[self._code.currentData()]
        if rnc:
            self._wind_speed.setToolTip(
                "RNC-07 Art. 50: the regional velocity VR, a 3 second gust at 10 m with 50 "
                "years of return period (200 for Group A)."
            )
            self._wind_zone.setCurrentIndex(2)
            self._on_wind_zone_changed()
        else:
            self._wind_speed.setToolTip(
                "ASCE 7-16 26.5: the basic wind speed V of the building's risk category. It "
                "is an ultimate speed: a 50 year velocity, such as RNC-07's, is multiplied by "
                "1.26 (the square root of 1.6) before it is entered here."
            )
            self._wind_speed.setValue(preset.wind_speed if preset.wind_method == "asce7" else 57.0)
        self._refresh_wind()

    def _on_wind_zone_changed(self, _index: int = 0) -> None:
        speed = self._wind_zone.currentData()
        if speed is not None and self._wind_zone.isEnabled():
            self._wind_speed.blockSignals(True)
            self._wind_speed.setValue(float(speed))
            self._wind_speed.blockSignals(False)
        self._refresh_wind()

    def _on_wind_speed_edited(self, *_args: object) -> None:
        """A typed velocity that is not the zone's moves the zone to "Other velocity"."""
        if self._wind_zone.isEnabled():
            index = self._wind_zone.findData(self._wind_speed.value())
            self._wind_zone.blockSignals(True)
            self._wind_zone.setCurrentIndex(index if index >= 0 else self._wind_zone.count() - 1)
            self._wind_zone.blockSignals(False)
        self._refresh_wind()

    def wind(self) -> WarehouseWind | None:
        """The wind the fields describe; None when no wind cases are wanted.

        Raises:
            WarehouseError: if they do not describe one.
        """
        if not self._wind_on.isChecked():
            return None
        return WarehouseWind(
            method=str(self._wind_method.currentData()),
            speed=self._wind_speed.value(),
            exposure=str(self._wind_exposure.currentData()),
            topography=str(self._wind_topography.currentData()),
            topographic_factor=self._wind_kzt.value(),
            openings=OPENINGS[self._wind_openings.currentIndex()],
            directions=tuple(d for d, box in self._wind_directions.items() if box.isChecked()),
        )

    def _refresh_wind(self, *_args: object) -> None:
        if not hasattr(self, "_page_wind"):
            return
        on = self._wind_on.isChecked()
        rnc = self._wind_method.currentData() == "rnc07"
        for widget, enabled in (
            (self._wind_method, True),
            (self._wind_zone, rnc),
            (self._wind_speed, True),
            (self._wind_exposure, True),
            (self._wind_topography, rnc),
            (self._wind_kzt, not rnc),
            (self._wind_openings, True),
            *((box, True) for box in self._wind_directions.values()),
        ):
            widget.setEnabled(on and enabled)
        self._wind_error = ""
        text = ""
        try:
            wind = self.wind()
            if wind is not None and not self._error:
                spec = self.spec()
                cases = warehouse_wind_cases(spec, wind, self._units)
                metres = length_from_m(1.0, self._units)
                eave = spec.eave_height / metres
                windward = cases[0].walls[
                    {"+X": "x0", "-X": "x1", "+Y": "y0", "-Y": "y1"}[cases[0].direction]
                ]
                pressure = pressure_from_kpa(windward.at(eave) / 1e3, self._units)
                text = tr(
                    "<b>{cases}</b> wind cases. Net pressure on the windward wall at the "
                    "eave, {name}: <b>{pressure} {unit}</b>."
                ).format(
                    cases=len(cases),
                    name=cases[0].name,
                    pressure=f"{pressure:.4g}",
                    unit=self._pressure,
                )
        except WarehouseError as exc:
            self._wind_error = str(exc)
            text = "<b>" + tr("Check the numbers:") + f"</b> {tr(self._wind_error)}"
        self._wind_summary.setText(text)
        self._page_wind.completeChanged.emit()

    def _bays(self) -> tuple[int, ...] | None:
        text = self._braced_bays.text().strip()
        if not text:
            return None
        try:
            return tuple(
                int(part) - 1 for part in text.replace(";", ",").split(",") if part.strip()
            )
        except ValueError:
            raise WarehouseError(
                "The braced bays are numbers separated by commas, for example 1, 6."
            ) from None

    def spec(self) -> WarehouseSpec:
        """The warehouse the fields describe.

        Raises:
            WarehouseError: if they do not describe one.
        """
        _label, roof, has_slope = ROOF_CHOICES[self._roof.currentIndex()]
        return WarehouseSpec(
            span=self._span.value(),
            eave_height=self._eave_height.value(),
            frame_spacing=self._frame_spacing.value(),
            n_frames=self._n_frames.value(),
            n_naves=self._n_naves.value(),
            roof=roof,
            slope=self._slope.value() / 100.0 if has_slope else 0.0,
            support=SUPPORT_CHOICES[self._support.currentIndex()][1],
            purlin_spacing=self._purlin_spacing.value(),
            girt_spacing=self._girt_spacing.value(),
            rafter_fly_brace_every=self._rafter_fly.value(),
            column_fly_brace_every=self._column_fly.value(),
            roof_bracing=self._roof_bracing.isChecked(),
            wall_bracing=self._wall_bracing.isChecked(),
            braced_bays=self._bays(),
            end_wall_column_spacing=self._end_wall_spacing.value(),
        )

    def _refresh(self, *_args: object) -> None:
        try:
            spec = self.spec()
            warehouse = build_warehouse(
                spec, dict.fromkeys(SECTION_KEYS, 1), first_node_id=1, first_element_id=1
            )
        except WarehouseError as exc:
            self._error = str(exc)
            message = "<b>" + tr("Check the numbers:") + f"</b> {tr(self._error)}"
            self._geometry_summary.setText(message)
            self._secondary_summary.setText(message)
            self._preview.set_warehouse(None)
        else:
            self._error = ""
            self._preview.set_warehouse(warehouse)
            self._geometry_summary.setText(
                tr(
                    "Plan <b>{width} × {length} {unit}</b>, ridge at <b>{ridge} {unit}</b>, "
                    "{frames} frames."
                ).format(
                    width=f"{spec.width:g}",
                    length=f"{spec.length:g}",
                    ridge=f"{spec.ridge_height:g}",
                    unit=self._unit,
                    frames=spec.n_frames,
                )
            )
            lengths = sorted(
                {round(warehouse.unbraced[e], 9) for e in warehouse.rafter_elements[0]}
            )
            self._secondary_summary.setText(
                tr(
                    "<b>{lines}</b> purlin lines. Rafter unbraced length for the steel "
                    "check: <b>{longest} {unit}</b>. {nodes} nodes, {elements} elements."
                ).format(
                    lines=len(warehouse.stations),
                    longest=f"{lengths[-1]:.4g}",
                    unit=self._unit,
                    nodes=len(warehouse.nodes),
                    elements=len(warehouse.elements),
                )
            )
        for page in (self._page_geometry, self._page_secondary):
            page.completeChanged.emit()
        self._refresh_wind()

    # ── results ─────────────────────────────────────────────────────
    def section_choice(self) -> dict[str, int | None]:
        """Section id per member kind; None means "create the default one"."""
        out: dict[str, int | None] = {}
        for key, combo in self._section_combos.items():
            data = combo.currentData()
            out[key] = None if data in (None, CREATE_DEFAULT) else int(data)
        return out

    def loads(self) -> WarehouseLoads:
        """The roof loads, the code and what to derive from them."""
        return WarehouseLoads(
            code=str(self._code.currentData()),
            roof_dead=self._roof_dead.value(),
            roof_live=self._roof_live.value(),
            midspan_point=self._point.value(),
            combinations=self._combinations.isChecked(),
            design_lengths=self._design_lengths.isChecked(),
            wind=self.wind(),
        )


__all__ = ["CREATE_DEFAULT", "WarehousePreview", "WarehouseWizard"]
