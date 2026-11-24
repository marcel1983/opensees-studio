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

from typing import Any

from PySide6.QtGui import QShowEvent
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
from opensees_studio.core.nscm import NSCM_IMPORTANCE
from opensees_studio.core.rnc07 import RNC07_REGULARITY_LABELS, RNC07_SOILS, RNC07_ZONE_A0
from opensees_studio.core.snow import ASH_LOAD_KPA
from opensees_studio.core.trusses import TRUSS_TYPE_LABELS
from opensees_studio.core.units import UnitSystem, labels_for
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    DEFAULT_ROOF_DEAD_KPA,
    EN1998_IMPORTANCE,
    EN1998_SOIL_FACTORS,
    GROUP_COLOURS,
    GROUPS,
    ROOF_STRUCTURES,
    ROOF_TRUSS_TYPES,
    SECTION_KEYS,
    SEISMIC_DIRECTIONS,
    SEISMIC_METHODS,
    SNOW_METHODS,
    TRUSS_BOTTOMS,
    TRUSS_SECTION_KEYS,
    WIND_METHODS,
    Warehouse,
    WarehouseError,
    WarehouseLoads,
    WarehouseSeismic,
    WarehouseSnow,
    WarehouseSpec,
    WarehouseWind,
    build_warehouse,
    default_section_name,
    force_from_kn,
    length_from_m,
    pressure_from_kpa,
    seismic_coefficient,
    warehouse_snow_cases,
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
from opensees_studio.views.dialogs.wireframe_preview import WireframePreview
from opensees_studio.views.dialogs.wizard_sections import (
    CREATE_DEFAULT,
    DefineSections,
    chosen_section,
    define_sections_button,
    fill_section_combo,
    new_section_combo,
)
from opensees_studio.views.i18n import tr
from opensees_studio.views.screen_fit import fit_to_available_screen

#: Labels of :data:`opensees_studio.core.warehouse.ROOF_STRUCTURES`, in its order.
ROOF_STRUCTURE_LABELS: tuple[str, ...] = ("Rafters", "Roof trusses")

#: Labels of :data:`opensees_studio.core.warehouse.TRUSS_BOTTOMS`, in its order.
TRUSS_BOTTOM_LABELS: tuple[str, ...] = ("Horizontal chord", "Chord parallel to the roof")

#: (label, type) of the web patterns a roof truss can have.
ROOF_TRUSS_LABELS = [(label, kind) for label, kind in TRUSS_TYPE_LABELS if kind in ROOF_TRUSS_TYPES]

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
    "en1991": (
        ("0", "0: sea, coast exposed to the open sea"),
        ("I", "I: lakes, flat country without obstacles"),
        ("II", "II: low vegetation, isolated obstacles"),
        ("III", "III: villages, suburbs, permanent forest"),
        ("IV", "IV: at least 15 % covered with buildings over 15 m"),
    ),
}
#: The exposure each procedure starts with.
DEFAULT_EXPOSURE: dict[str, str] = {"rnc07": "R2", "asce7": "C", "en1991": "II"}
#: The wind speed a procedure starts with when the design code brings another one, m/s.
DEFAULT_WIND_SPEED: dict[str, float] = {"asce7": 57.0, "en1991": 26.0}

#: RNC-07 Tabla 7: (key, label).
WIND_TOPOGRAPHIES: tuple[tuple[str, str], ...] = (
    ("T1", "T1: sheltered base of a hill, leeward side"),
    ("T2", "T2: closed valley"),
    ("T3", "T3: flat terrain, slopes below 5 % (normal)"),
    ("T4", "T4: slopes between 5 and 10 %"),
    ("T5", "T5: hilltops, slopes above 10 %"),
)

#: Soil choices per seismic method: RNC-07 soil types, NSCM and ASCE site classes.
SEISMIC_SOILS: dict[str, tuple[str, ...]] = {
    "rnc07": RNC07_SOILS,
    "nscm": ("A", "B", "C", "D"),
    "asce7": (),
    "en1998": tuple(EN1998_SOIL_FACTORS),
}
#: The soil each method starts with.
DEFAULT_SOIL: dict[str, str] = {"rnc07": "II", "nscm": "C", "en1998": "C"}

#: Importance choices per seismic method: RNC-07 groups, NSCM risk categories.
SEISMIC_CLASSES: dict[str, tuple[str, ...]] = {
    "rnc07": ("A", "B", "C"),
    "nscm": tuple(NSCM_IMPORTANCE),
    "asce7": (),
    "en1998": tuple(EN1998_IMPORTANCE),
}
DEFAULT_CLASS: dict[str, str] = {"rnc07": "B", "nscm": "II", "en1998": "II"}

#: a0 each method starts with, g: RNC-07 zone C; NSCM Tabla 14.2, Managua; an
#: agR of moderate seismicity for EN 1998-1 (the National Annex has the map).
DEFAULT_A0: dict[str, float] = {
    "rnc07": RNC07_ZONE_A0["C"],
    "nscm": 0.36667,
    "asce7": 0.0,
    "en1998": 0.15,
}

#: Load each rule of the ash and snow page starts with, kN/m²: 20 kg/m² of wet
#: ash (RNC-07 Art. 14); 20 psf of ground snow; a characteristic sk of 1 kN/m².
DEFAULT_SNOW_KPA: dict[str, float] = {"ash": ASH_LOAD_KPA, "asce7": 0.9576, "en1991": 1.0}

#: Labels of :data:`opensees_studio.core.wind.OPENINGS`, in its order.
WIND_OPENINGS: tuple[str, ...] = (
    "Closed building",
    "Openings spread over the four walls",
    "Openings mainly in the side wall at the smallest X",
    "Openings mainly in the side wall at the largest X",
    "Openings mainly in the end wall at the smallest Y",
    "Openings mainly in the end wall at the largest Y",
)


class WarehousePreview(WireframePreview):
    """An isometric wireframe of the warehouse, one colour per member group."""

    def set_warehouse(self, warehouse: Warehouse | None) -> None:
        """Draw ``warehouse``; None clears the preview."""
        if warehouse is None:
            self.clear()
            return
        self.set_members(
            warehouse.nodes,
            warehouse.elements,
            warehouse.members,
            {key: GROUP_COLOURS[key] for key in GROUPS},
            origin=warehouse.spec.origin,
        )


class WarehouseWizard(QWizard):
    """Collects a warehouse's geometry, sections and loads."""

    def __init__(
        self,
        sections: list[Any],
        *,
        units: UnitSystem = UnitSystem.SI_M_N,
        define_sections: DefineSections | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sections = sections
        self._define_sections = define_sections
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
        self._build_seismic_page()
        self._build_snow_page()
        for index, page in enumerate(
            (
                self._page_geometry,
                self._page_secondary,
                self._page_sections,
                self._page_loads,
                self._page_wind,
                self._page_seismic,
                self._page_snow,
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
        self._roof_structure = QComboBox()
        for label in ROOF_STRUCTURE_LABELS:
            self._roof_structure.addItem(tr(label))
        self._roof_structure.setToolTip(
            "What carries the roof in each frame: a rafter, or a truss whose top chord "
            "follows the roof with a panel point under every purlin line."
        )
        self._truss_type = QComboBox()
        for label, _kind in ROOF_TRUSS_LABELS:
            self._truss_type.addItem(tr(label))
        self._truss_type.setToolTip(
            "Pratt: the diagonals run down towards mid-span, in tension under gravity. "
            "Howe: up towards mid-span. Warren: alternating. All three have a vertical "
            "under every purlin line."
        )
        self._truss_bottom = QComboBox()
        for label in TRUSS_BOTTOM_LABELS:
            self._truss_bottom.addItem(tr(label))
        self._truss_depth = self._length(1.0)
        self._truss_depth.setToolTip(
            "Depth of the truss, measured plumb: at the eave with a horizontal bottom "
            "chord, everywhere with a parallel one. The eave height stays the top of the "
            "roof line, so the clear height under the truss is the eave height less this "
            "depth."
        )

        form.addRow("Roof:", self._roof)
        form.addRow("Nave span:", self._span)
        form.addRow("Number of naves:", self._n_naves)
        form.addRow("Number of frames:", self._n_frames)
        form.addRow("Distance between frames:", self._frame_spacing)
        form.addRow("Eave height:", self._eave_height)
        form.addRow("Slope:", self._slope)
        form.addRow("Column bases:", self._support)
        form.addRow("Roof structure:", self._roof_structure)
        form.addRow("Truss web:", self._truss_type)
        form.addRow("Bottom chord:", self._truss_bottom)
        form.addRow("Truss depth:", self._truss_depth)

        self._geometry_summary = QLabel()
        self._geometry_summary.setWordWrap(True)
        form.addRow(self._geometry_summary)

        for field in (
            self._span,
            self._frame_spacing,
            self._eave_height,
            self._slope,
            self._truss_depth,
        ):
            field.valueChanged.connect(self._refresh)
        for spin in (self._n_naves, self._n_frames):
            spin.valueChanged.connect(self._refresh)
        for combo in (
            self._roof,
            self._support,
            self._roof_structure,
            self._truss_type,
            self._truss_bottom,
        ):
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
        self._purlin_rods = QSpinBox()
        self._purlin_rods.setRange(0, 10)
        self._purlin_rods.setValue(1)
        self._purlin_rods.setSpecialValueText(tr("None"))
        self._purlin_rods.setToolTip(
            "Lines of sag rods in each bay, holding every purlin sideways: 1 is a line at "
            "mid-span, 2 at the third points. They are not modelled; the steel check takes "
            "the purlin's minor-axis and lateral-torsional lengths between them."
        )
        self._girt_rods = QSpinBox()
        self._girt_rods.setRange(0, 10)
        self._girt_rods.setSpecialValueText(tr("None"))
        self._girt_rods.setToolTip("As for the purlins: lines of sag rods in each bay of wall.")
        self._sheeting = QCheckBox("Sheeting screwed to the purlins and girts")
        self._sheeting.setChecked(True)
        self._sheeting.setToolTip(
            "A roof and wall sheeting fastened through to every purlin and girt braces the "
            "flange it sits on: the steel check takes that flange as held when it is in "
            "compression (gravity on a purlin, pressure on a girt). Under uplift or suction "
            "the free flange is in compression and the member counts on its sag rods, or on "
            "the R factor of AISI S100 I6.2.1 where the section is within its limits. Untick "
            "for a standing seam roof."
        )
        self._end_wall_spacing = self._length(5.0)
        self._end_wall_spacing.setToolTip(
            "Largest distance between the columns of the two end walls; 0 builds none. Each "
            "nave is divided into equal parts and each column stands under the nearest "
            "purlin line, pinned at both ends. With end wall columns the end walls also get "
            "girts, at the girt spacing."
        )
        self._chord_ties = QSpinBox()
        self._chord_ties.setRange(0, 50)
        self._chord_ties.setValue(4)
        self._chord_ties.setSpecialValueText(tr("Columns and ridge only"))
        self._chord_ties.setToolTip(
            "With roof trusses: every n-th panel point of the bottom chord is tied to the "
            "next frame; the column lines and the ridge always are. In the braced bays "
            "each tie line gets a vertical X between the two chords. The steel check "
            "takes the bottom chord's unbraced length between tie lines: it is the chord "
            "in compression when the wind lifts the roof."
        )
        self._roof_bracing = QCheckBox("X bracing in the roof")
        self._roof_bracing.setChecked(True)
        self._wall_bracing = QCheckBox("X bracing in the side walls")
        self._wall_bracing.setChecked(True)
        self._tension_only = QCheckBox("Braces work in tension only")
        self._tension_only.setChecked(True)
        self._tension_only.setToolTip(
            "Rods and slender angles buckle at once in compression: each X then holds with "
            "the diagonal the load stretches. The braces become tension-only members, and "
            "each load combination is analysed as a case of its own (Newton iteration), "
            "because which diagonal works depends on the whole load. Untick for braces "
            "that also take compression."
        )
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
        form.addRow("Sag rod lines per bay (purlins):", self._purlin_rods)
        form.addRow("Sag rod lines per bay (girts):", self._girt_rods)
        form.addRow(self._sheeting)
        form.addRow("End wall column spacing:", self._end_wall_spacing)
        form.addRow("Bottom chord tie every (panel points):", self._chord_ties)
        form.addRow(self._roof_bracing)
        form.addRow(self._wall_bracing)
        form.addRow(self._tension_only)
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
        for spin in (
            self._rafter_fly,
            self._column_fly,
            self._chord_ties,
            self._purlin_rods,
            self._girt_rods,
        ):
            spin.valueChanged.connect(self._refresh)
        for box in (self._roof_bracing, self._wall_bracing, self._sheeting, self._tension_only):
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
            combo = new_section_combo(self._default_section_text(key), self._sections)
            self._section_combos[key] = combo
            form.addRow(tr(label) + ":", combo)
        self._sections_form = form
        button = define_sections_button(self, self._define_sections, self.set_sections)
        if button is not None:
            form.addRow(button)
        note = QLabel(
            "<i>The sections that do not exist yet are created with the warehouse, as the "
            "same undoable step: columns, rafters, truss members and braces from the AISC "
            "library, purlins and girts as a cold-formed lipped channel. The end wall "
            "column section is used only when the warehouse has end wall columns.</i>"
        )
        note.setWordWrap(True)
        form.addRow(note)
        self._page_sections = page

    @staticmethod
    def _default_section_text(key: str) -> str:
        return tr("{name} (will be created)").format(name=default_section_name(key))

    def set_sections(self, sections: list[Any]) -> None:
        """Offer ``sections`` (after Section Library…), keeping each choice still there."""
        self._sections = sections
        for key, combo in self._section_combos.items():
            fill_section_combo(combo, self._default_section_text(key), sections)

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
        page.setSubTitle("The wind cases on the walls and the roof, one to four per direction.")
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
        self._wind_kzt.setToolTip(
            "Kzt of ASCE 7-16 26.8 or the orography factor co of EN 1991-1-4 4.3.3: 1 on "
            "flat terrain."
        )
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
        form.addRow("Topographic factor (Kzt, co):", self._wind_kzt)
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

    def _build_seismic_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not self._seismic_error
        page.setTitle("Earthquake")
        page.setSubTitle("The static earthquake forces, one case per direction.")
        form = QFormLayout(page)
        self._seismic_error = ""

        self._seismic_on = QCheckBox("Create the earthquake load cases")
        self._seismic_method = QComboBox()
        for key, label in SEISMIC_METHODS.items():
            self._seismic_method.addItem(tr(label), userData=key)
        self._seismic_a0 = _field(0.3, minimum=0.0, maximum=2.0, step=0.05, suffix="g")
        self._seismic_a0.setToolTip(
            "Peak ground acceleration a0. RNC-07 Art. 24: zone A 0.1, B 0.2, C 0.3 g, or the "
            "value of the map of Anexo C. NSCM Tabla 14.2 per municipality: Managua 0.36667 g. "
            "EN 1998-1 3.2.1: the reference acceleration agR on type A ground, from the "
            "National Annex."
        )
        self._seismic_soil = QComboBox()
        self._seismic_soil.setToolTip(
            "RNC-07 Art. 25: soil type I (rock) to III (soft). NSCM Tabla 6.4.1: site class "
            "A to D. EN 1998-1 Table 3.1: ground type A to E, with the soil factor S of the "
            "Type 1 spectrum. A softer soil needs a site study."
        )
        self._seismic_class = QComboBox()
        self._seismic_class.setToolTip(
            "RNC-07 Art. 20: group A (essential, forces times 1.5), B or C. NSCM Tabla 5.2.1: "
            "risk category I to IV. EN 1998-1 Table 4.3: importance class I to IV (0.8, 1.0, "
            "1.2, 1.4)."
        )
        self._seismic_reduction = _field(2.0, minimum=0.01, maximum=20.0, step=0.5)
        self._seismic_reduction.setToolTip(
            "Q of RNC-07 Art. 21, Ro of NSCM (Ec. 6.6-1), R of ASCE 7-16 Table 12.2-1 or the "
            "behaviour factor q of EN 1998-1 6.3.2, for the lateral system of the warehouse "
            "in the direction that has the least."
        )
        self._seismic_regularity = QComboBox()
        for key, label in RNC07_REGULARITY_LABELS.items():
            self._seismic_regularity.addItem(tr(label), userData=key)
        self._seismic_sds = _field(1.0, minimum=0.0, maximum=10.0, step=0.1, suffix="g")
        self._seismic_sds.setToolTip(
            "ASCE 7-16 11.4.5: design spectral acceleration at short periods, SDS."
        )
        self._seismic_ie = _field(1.0, minimum=0.01, maximum=10.0, step=0.25)
        self._seismic_ie.setToolTip("ASCE 7-16 Table 1.5-2: importance factor Ie.")
        self._seismic_live = _field(
            0.0, minimum=0.0, maximum=1e9, step=pressure_from_kpa(0.05, self._units),
            suffix=self._pressure,
        )  # fmt: skip
        self._seismic_live.setToolTip(
            "Roof live load that counts as seismic weight, per area of horizontal "
            "projection. RNC-07 Art. 11 a: 10 kg/m² on light roofs (CVR). NSCM 9.6: 0.3 CV "
            "in warehouses and storage, 0.15 CV elsewhere. ASCE 7-16 12.7.2 and EN 1998-1 "
            "3.2.4 (ψ2 = 0 on a roof) count none."
        )
        self._seismic_directions: dict[str, QCheckBox] = {}
        directions = QHBoxLayout()
        for direction in SEISMIC_DIRECTIONS:
            box = QCheckBox(direction)
            box.setChecked(True)
            box.toggled.connect(self._refresh_seismic)
            self._seismic_directions[direction] = box
            directions.addWidget(box)
        directions.addStretch(1)

        for combo in (self._seismic_method, self._seismic_regularity):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(24)
        form.addRow(self._seismic_on)
        form.addRow("Method:", self._seismic_method)
        form.addRow("Ground acceleration a0:", self._seismic_a0)
        form.addRow("Soil:", self._seismic_soil)
        form.addRow("Group or risk category:", self._seismic_class)
        form.addRow("Reduction factor (Q, Ro, R or q):", self._seismic_reduction)
        form.addRow("Regularity:", self._seismic_regularity)
        form.addRow("SDS:", self._seismic_sds)
        form.addRow("Importance factor Ie:", self._seismic_ie)
        form.addRow("Roof live load in the seismic weight:", self._seismic_live)
        form.addRow("Earthquake along:", directions)
        self._seismic_summary = QLabel()
        self._seismic_summary.setWordWrap(True)
        form.addRow(self._seismic_summary)
        note = QLabel(
            "<i>The base shear is the coefficient times the weight of the steel, the roof "
            "dead load and this part of the roof live load, shared between the joints by "
            "weight and height. The coefficient is that of the plateau of the spectrum: the "
            "period is not used. Accidental torsion is not included.</i>"
        )
        note.setWordWrap(True)
        form.addRow(note)

        self._seismic_on.toggled.connect(self._refresh_seismic)
        self._seismic_method.currentIndexChanged.connect(self._on_seismic_method_changed)
        for field in (
            self._seismic_a0,
            self._seismic_reduction,
            self._seismic_sds,
            self._seismic_ie,
            self._seismic_live,
        ):
            field.valueChanged.connect(self._refresh_seismic)
        for combo in (self._seismic_soil, self._seismic_class, self._seismic_regularity):
            combo.currentIndexChanged.connect(self._refresh_seismic)
        self._page_seismic = page
        self._on_seismic_method_changed()

    def _build_snow_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not self._snow_error
        page.setTitle("Ash and snow")
        page.setSubTitle("What settles on the roof: volcanic ash, or snow.")
        form = QFormLayout(page)
        self._snow_error = ""

        self._snow_on = QCheckBox("Create the ash or snow load cases")
        self._snow_method = QComboBox()
        for key, label in SNOW_METHODS.items():
            self._snow_method.addItem(tr(label), userData=key)
        self._snow_method.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._snow_method.setMinimumContentsLength(34)
        self._snow_ground = _field(0.0, minimum=0.0, maximum=1e12, step=0.0, suffix=self._pressure)
        self._snow_ground.setToolTip(
            "Per area of horizontal projection. Volcanic ash: the load itself, 20 kg/m² of "
            "wet ash when there is no local record (RNC-07 Art. 14, NSCM 7.3; mandatory in "
            "León, Chinandega, Carazo, Ometepe and Masaya). ASCE 7-16: the ground snow "
            "load pg of Fig. 7.2-1. EN 1991-1-3: the characteristic value sk of the "
            "National Annex."
        )
        self._snow_ce = _field(1.0, minimum=0.01, maximum=10.0, step=0.1)
        self._snow_ce.setToolTip(
            "ASCE 7-16 Table 7.3-1: 0.9 fully exposed (0.8 in terrain D), 1.0 partially "
            "exposed, 1.2 sheltered in terrain B (1.1 in C, 1.0 in D). EN 1991-1-3 Table "
            "5.1: 0.8 windswept, 1.0 normal, 1.2 sheltered."
        )
        self._snow_ct = _field(1.0, minimum=0.01, maximum=10.0, step=0.1)
        self._snow_ct.setToolTip(
            "ASCE 7-16 Table 7.3-2: 1.0 heated, 1.1 kept just above freezing or cold and "
            "ventilated, 1.2 unheated or open, 1.3 kept below freezing. EN 1991-1-3 5.2 (8): "
            "1.0 unless the roof loses much heat."
        )
        self._snow_is = _field(1.0, minimum=0.01, maximum=10.0, step=0.1)
        self._snow_is.setToolTip(
            "ASCE 7-16 Table 1.5-2: 0.8, 1.0, 1.1 or 1.2 for risk category I to IV."
        )
        self._snow_slippery = QCheckBox("Slippery roof the snow can slide off")
        self._snow_slippery.setToolTip(
            "ASCE 7-16 7.4: an unobstructed metal or membrane roof with room below the "
            "eaves for the snow. It sheds snow from a lower slope."
        )
        self._snow_unbalanced = QCheckBox("Also the unbalanced arrangements")
        self._snow_unbalanced.setChecked(True)
        self._snow_unbalanced.setToolTip(
            "ASCE 7-16 7.6.1: the drift to either side of the ridge of a gable roof. "
            "EN 1991-1-3 5.3.3: half the snow on one slope."
        )
        form.addRow(self._snow_on)
        form.addRow("Rule:", self._snow_method)
        form.addRow("Ash load, or snow load on the ground:", self._snow_ground)
        form.addRow("Exposure factor Ce:", self._snow_ce)
        form.addRow("Thermal factor Ct:", self._snow_ct)
        form.addRow("Importance factor Is:", self._snow_is)
        form.addRow(self._snow_slippery)
        form.addRow(self._snow_unbalanced)
        self._snow_summary = QLabel()
        self._snow_summary.setWordWrap(True)
        form.addRow(self._snow_summary)
        note = QLabel(
            "<i>The load falls on the horizontal projection of the roof and goes to the "
            "purlins. A balanced and an unbalanced case never enter the same combination. "
            "Build-up against parapets or taller walls and in gutters is not included, and "
            "neither is the part of the snow some codes count as seismic weight.</i>"
        )
        note.setWordWrap(True)
        form.addRow(note)

        self._snow_on.toggled.connect(self._refresh_snow)
        self._snow_method.currentIndexChanged.connect(self._on_snow_method_changed)
        for field in (self._snow_ground, self._snow_ce, self._snow_ct, self._snow_is):
            field.valueChanged.connect(self._refresh_snow)
        self._snow_slippery.toggled.connect(self._refresh_snow)
        self._snow_unbalanced.toggled.connect(self._refresh_snow)
        self._page_snow = page
        self._on_snow_method_changed()

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
        index = self._seismic_method.findData(preset.seismic_method)
        if index != self._seismic_method.currentIndex():
            self._seismic_method.setCurrentIndex(index)
        else:
            self._on_seismic_method_changed()
        index = self._snow_method.findData(preset.snow_method)
        if index != self._snow_method.currentIndex():
            self._snow_method.setCurrentIndex(index)
        else:
            self._on_snow_method_changed()

    def _on_snow_method_changed(self, _index: int = 0) -> None:
        method = str(self._snow_method.currentData())
        self._snow_ground.blockSignals(True)
        self._snow_ground.setValue(pressure_from_kpa(DEFAULT_SNOW_KPA[method], self._units))
        self._snow_ground.blockSignals(False)
        self._refresh_snow()

    def snow(self) -> WarehouseSnow | None:
        """The ash or snow the fields describe; None when no such cases are wanted.

        Raises:
            WarehouseError: if they do not describe one.
        """
        if not self._snow_on.isChecked():
            return None
        return WarehouseSnow(
            method=str(self._snow_method.currentData()),
            ground=self._snow_ground.value(),
            exposure=self._snow_ce.value(),
            thermal=self._snow_ct.value(),
            importance=self._snow_is.value(),
            slippery=self._snow_slippery.isChecked(),
            unbalanced=self._snow_unbalanced.isChecked(),
        )

    def _refresh_snow(self, *_args: object) -> None:
        if not hasattr(self, "_page_snow"):
            return
        on = self._snow_on.isChecked()
        method = self._snow_method.currentData()
        ash, asce = method == "ash", method == "asce7"
        for widget, enabled in (
            (self._snow_method, True),
            (self._snow_ground, True),
            (self._snow_ce, not ash),
            (self._snow_ct, not ash),
            (self._snow_is, asce),
            (self._snow_slippery, asce),
            (self._snow_unbalanced, not ash),
        ):
            widget.setEnabled(on and enabled)
        self._snow_error = ""
        text = ""
        try:
            snow = self.snow()
            if snow is not None and not self._error:
                cases = warehouse_snow_cases(self.spec(), snow, self._units)
                if len(cases) == 1:
                    text = tr(
                        "Load case {names}: <b>{pressure} {unit}</b> on the whole roof."
                    ).format(
                        names=cases[0].name,
                        pressure=f"{cases[0].peak:.4g}",
                        unit=self._pressure,
                    )
                elif cases:
                    text = tr(
                        "<b>{cases}</b> load cases: {names}. On the whole roof "
                        "<b>{pressure} {unit}</b>, up to <b>{peak} {unit}</b>."
                    ).format(
                        cases=len(cases),
                        names=", ".join(case.name for case in cases),
                        pressure=f"{cases[0].points[0][1]:.4g}",
                        peak=f"{max(case.peak for case in cases):.4g}",
                        unit=self._pressure,
                    )
                else:
                    text = tr("No load: nothing is created.")
        except WarehouseError as exc:
            self._snow_error = str(exc)
            text = "<b>" + tr("Check the numbers:") + f"</b> {tr(self._snow_error)}"
        self._snow_summary.setText(text)
        self._page_snow.completeChanged.emit()

    def _on_seismic_method_changed(self, _index: int = 0) -> None:
        method = str(self._seismic_method.currentData())
        chosen = CODE_PRESETS[self._code.currentData()]
        # The numbers of the method, also when the combinations follow another code.
        preset = next(p for p in (chosen, *CODE_PRESETS.values()) if p.seismic_method == method)
        for combo, choices, default in (
            (self._seismic_soil, SEISMIC_SOILS[method], DEFAULT_SOIL.get(method, "")),
            (self._seismic_class, SEISMIC_CLASSES[method], DEFAULT_CLASS.get(method, "")),
        ):
            combo.blockSignals(True)
            combo.clear()
            for item in choices:
                combo.addItem(item, userData=item)
            combo.setCurrentIndex(max(0, combo.findData(default)))
            combo.blockSignals(False)
        for field, value in (
            (self._seismic_a0, DEFAULT_A0[method]),
            (self._seismic_reduction, preset.seismic_reduction),
            (self._seismic_live, pressure_from_kpa(preset.seismic_live_kpa, self._units)),
        ):
            field.blockSignals(True)
            field.setValue(value)
            field.blockSignals(False)
        self._refresh_seismic()

    def seismic(self) -> WarehouseSeismic | None:
        """The earthquake the fields describe; None when no earthquake cases are wanted.

        Raises:
            WarehouseError: if they do not describe one.
        """
        if not self._seismic_on.isChecked():
            return None
        return WarehouseSeismic(
            method=str(self._seismic_method.currentData()),
            a0=self._seismic_a0.value(),
            soil=str(self._seismic_soil.currentData() or ""),
            importance_class=str(self._seismic_class.currentData() or ""),
            reduction=self._seismic_reduction.value(),
            regularity=str(self._seismic_regularity.currentData()),
            sds=self._seismic_sds.value(),
            importance=self._seismic_ie.value(),
            roof_live=self._seismic_live.value(),
            directions=tuple(d for d, box in self._seismic_directions.items() if box.isChecked()),
        )

    def _refresh_seismic(self, *_args: object) -> None:
        if not hasattr(self, "_page_seismic"):
            return
        on = self._seismic_on.isChecked()
        method = self._seismic_method.currentData()
        asce = method == "asce7"
        for widget, enabled in (
            (self._seismic_method, True),
            (self._seismic_a0, not asce),
            (self._seismic_soil, not asce),
            (self._seismic_class, not asce),
            (self._seismic_reduction, True),
            (self._seismic_regularity, method == "rnc07"),
            (self._seismic_sds, asce),
            (self._seismic_ie, asce),
            (self._seismic_live, True),
            *((box, True) for box in self._seismic_directions.values()),
        ):
            widget.setEnabled(on and enabled)
        self._seismic_error = ""
        text = ""
        try:
            seismic = self.seismic()
            if seismic is not None:
                coefficient, clause = seismic_coefficient(seismic)
                text = tr(
                    "<b>{cases}</b> earthquake cases. Seismic coefficient "
                    "<b>c = {c}</b> of the weight ({clause})."
                ).format(cases=len(seismic.directions), c=f"{coefficient:.4g}", clause=clause)
        except WarehouseError as exc:
            self._seismic_error = str(exc)
            text = "<b>" + tr("Check the numbers:") + f"</b> {tr(self._seismic_error)}"
        self._seismic_summary.setText(text)
        self._page_seismic.completeChanged.emit()

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
                "EN 1991-1-4 4.2: the basic wind velocity vb, a 10 minute mean at 10 m over "
                "open country with 50 years of return period, from the National Annex. A 3 "
                "second gust, such as RNC-07's, is about 1.5 times larger."
                if method == "en1991"
                else "ASCE 7-16 26.5: the basic wind speed V of the building's risk category. "
                "It is an ultimate speed: a 50 year velocity, such as RNC-07's, is multiplied "
                "by 1.26 (the square root of 1.6) before it is entered here."
            )
            self._wind_speed.setValue(
                preset.wind_speed if preset.wind_method == method else DEFAULT_WIND_SPEED[method]
            )
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

    def _has_truss(self) -> bool:
        return ROOF_STRUCTURES[self._roof_structure.currentIndex()] == "truss"

    def _uses_section(self, key: str) -> bool:
        """The member kind ``key`` exists with the roof structure chosen."""
        return key != "rafter" if self._has_truss() else key not in TRUSS_SECTION_KEYS

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
        truss: dict[str, Any] = {}
        if self._has_truss():
            truss = {
                "roof_structure": "truss",
                "truss_type": ROOF_TRUSS_LABELS[self._truss_type.currentIndex()][1],
                "truss_bottom": TRUSS_BOTTOMS[self._truss_bottom.currentIndex()],
                "truss_depth": self._truss_depth.value(),
                "bottom_chord_tie_every": self._chord_ties.value(),
            }
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
            sheeting=self._sheeting.isChecked(),
            tension_only_braces=self._tension_only.isChecked(),
            purlin_sag_rods=self._purlin_rods.value(),
            girt_sag_rods=self._girt_rods.value(),
            **truss,
        )

    def _refresh(self, *_args: object) -> None:
        truss = self._has_truss()
        for widget in (self._truss_type, self._truss_bottom, self._truss_depth, self._chord_ties):
            widget.setEnabled(truss)
        self._rafter_fly.setEnabled(not truss)
        self._tension_only.setEnabled(
            self._roof_bracing.isChecked() or self._wall_bracing.isChecked()
        )
        for key, combo in self._section_combos.items():
            self._sections_form.setRowVisible(combo, self._uses_section(key))
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
            summary = tr(
                "Plan <b>{width} × {length} {unit}</b>, ridge at <b>{ridge} {unit}</b>, "
                "{frames} frames."
            ).format(
                width=f"{spec.width:g}",
                length=f"{spec.length:g}",
                ridge=f"{spec.ridge_height:g}",
                unit=self._unit,
                frames=spec.n_frames,
            )
            if spec.has_truss:
                summary += " " + tr(
                    "Clear height under the trusses: <b>{clear} {unit}</b>."
                ).format(clear=f"{spec.eave_height - spec.truss_depth:g}", unit=self._unit)
            self._geometry_summary.setText(summary)
            chord = warehouse.bottom_chord_elements if spec.has_truss else warehouse.rafter_elements
            lengths = sorted({round(warehouse.unbraced[e], 9) for e in chord[0]})
            text = (
                tr(
                    "<b>{lines}</b> purlin lines. Bottom chord unbraced length for the steel "
                    "check: <b>{longest} {unit}</b>. {nodes} nodes, {elements} elements."
                )
                if spec.has_truss
                else tr(
                    "<b>{lines}</b> purlin lines. Rafter unbraced length for the steel "
                    "check: <b>{longest} {unit}</b>. {nodes} nodes, {elements} elements."
                )
            )
            self._secondary_summary.setText(
                text.format(
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
        self._refresh_snow()

    # ── results ─────────────────────────────────────────────────────
    def section_choice(self) -> dict[str, int | None]:
        """Section id per member kind; None means "create the default one"."""
        out: dict[str, int | None] = {}
        for key, combo in self._section_combos.items():
            if not self._uses_section(key):
                continue
            out[key] = chosen_section(combo)
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
            seismic=self.seismic(),
            snow=self.snow(),
        )


__all__ = ["CREATE_DEFAULT", "WarehousePreview", "WarehouseWizard"]
