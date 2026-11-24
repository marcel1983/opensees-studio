"""Building wizard: a multi-storey frame building from a few numbers.

Four pages, in the order the questions come up: the bays and the storeys, what
the members are made of, what the floors carry under which design code, and
the earthquake. A wireframe preview on the side follows every field.

Everything it builds comes from :mod:`opensees_studio.core.building`; the
wizard is fields, the preview and their translation into a
:class:`~opensees_studio.core.building.BuildingSpec`, a section choice and a
:class:`~opensees_studio.core.building.BuildingLoads`. The caller plans and
inserts the result (``commands.building``), so cancelling leaves nothing
behind. Given a ``planner``, the last page plans the building as the fields
stand and shows what the project would gain (the seismic weight and the base
shear of each direction), or why it cannot be built.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QWidget,
    QWizard,
    QWizardPage,
)

from opensees_studio.core.building import (
    ACCIDENTAL_ECCENTRICITY,
    BUILDING_CODES,
    BUILDING_SEISMIC_METHODS,
    FRAME_MATERIALS,
    GROUP_COLOURS,
    OCCUPANCIES,
    SECTION_KEYS,
    SLAB_SPANS,
    Building,
    BuildingError,
    BuildingLoads,
    BuildingPlan,
    BuildingSeismic,
    BuildingSpec,
    build_building,
    default_section_name,
    live_load_family,
    occupancy_loads,
)
from opensees_studio.core.code_combinations import CODES
from opensees_studio.core.help import TOPIC_PROPERTY
from opensees_studio.core.rnc07 import RNC07_REGULARITY_LABELS
from opensees_studio.core.units import UnitSystem, labels_for
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    SEISMIC_DIRECTIONS,
    length_from_m,
    pressure_from_kpa,
)
from opensees_studio.views.dialogs.frame_wizard import SUPPORT_CHOICES, _CompletablePage, _field
from opensees_studio.views.dialogs.warehouse_wizard import (
    DEFAULT_A0,
    DEFAULT_CLASS,
    DEFAULT_SOIL,
    SEISMIC_CLASSES,
    SEISMIC_SOILS,
)
from opensees_studio.views.dialogs.wireframe_preview import WireframePreview
from opensees_studio.views.dialogs.wizard_sections import (
    DefineSections,
    chosen_section,
    define_sections_button,
    fill_section_combo,
    new_section_combo,
)
from opensees_studio.views.i18n import tr
from opensees_studio.views.screen_fit import fit_to_available_screen

#: What plans the building the fields describe: ``(spec, sections, loads)``.
Planner = Callable[[BuildingSpec, Mapping[str, int | None], BuildingLoads], BuildingPlan]

#: Labels of :data:`opensees_studio.core.building.FRAME_MATERIALS`, in its order.
FRAME_LABELS: tuple[str, ...] = ("Steel", "Reinforced concrete")

#: Labels of :data:`opensees_studio.core.building.SLAB_SPANS`, in its order.
SLAB_LABELS: tuple[str, ...] = (
    "Two-way slab",
    "One-way slab spanning along X",
    "One-way slab spanning along Y",
)

#: (label, local axis angle of the columns in degrees).
COLUMN_ANGLES: tuple[tuple[str, float], ...] = (
    ("Depth along X", 0.0),
    ("Depth along Y", 90.0),
)

#: Labels of :data:`opensees_studio.core.building.SECTION_KEYS`.
SECTION_LABELS: dict[str, str] = {
    "column": "Columns",
    "beam_x": "Beams along X",
    "beam_y": "Beams along Y",
}

#: Labels of :data:`opensees_studio.core.building.OCCUPANCIES`.
OCCUPANCY_LABELS: dict[str, str] = {
    "residential": "Residential",
    "classrooms": "Classrooms",
    "hospital": "Hospital",
    "office": "Offices",
    "assembly": "Assembly",
}
DEFAULT_OCCUPANCY = "office"

#: Where the live loads of each family of codes come from, for the loads page.
LIVE_LOAD_SOURCES: dict[str, str] = {
    "rnc07": (
        "RNC-07 Tabla 1: the maximum live load CV, and the reduced CVR that goes with "
        "the earthquake (Art. 10)."
    ),
    "nscm": "NSCM Tabla 7.1.1, with 0.15 CV in the seismic weight (9.6 a).",
    "asce7": (
        "ASCE 7-16 Table 4.3-1, before any reduction; no live load in the seismic "
        "weight outside storage (12.7.2)."
    ),
}

#: Slab, finishes and partitions a floor and the roof start with, kN/m².
DEFAULT_FLOOR_DEAD_KPA = 4.5
DEFAULT_ROOF_DEAD_KPA = 3.5

#: Q, Ro or R each method starts with: an ordinary moment frame of the
#: material (RNC-07 Art. 21; NSCM Tabla 5.5.1 C; ASCE 7-16 Table 12.2-1).
DEFAULT_REDUCTION: dict[tuple[str, str], float] = {
    ("rnc07", "steel"): 2.0,
    ("rnc07", "concrete"): 2.0,
    ("nscm", "steel"): 3.5,
    ("nscm", "concrete"): 3.0,
    ("asce7", "steel"): 3.5,
    ("asce7", "concrete"): 3.0,
}


def _closing_note(note: QLabel) -> QLabel:
    """``note`` as the last row of a page: wrapped, and given the height left below it.

    A wrapped label in a form is measured at the width it would like, not the
    one it gets, and loses its last line when the text runs longer in another
    language.
    """
    note.setWordWrap(True)
    note.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    note.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
    return note


class BuildingPreview(WireframePreview):
    """An isometric wireframe of the building: columns and the beams each way."""

    def set_building(self, building: Building | None) -> None:
        """Draw ``building``; None clears the preview."""
        if building is None:
            self.clear()
            return
        self.set_members(
            building.nodes,
            building.elements,
            building.members,
            GROUP_COLOURS,
            origin=building.spec.origin,
        )


class BuildingWizard(QWizard):
    """Collects a building's geometry, sections, floor loads and earthquake."""

    def __init__(
        self,
        sections: list[Any],
        *,
        units: UnitSystem = UnitSystem.SI_M_N,
        planner: Planner | None = None,
        define_sections: DefineSections | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sections = sections
        self._define_sections = define_sections
        self._units = units
        self._planner = planner
        labels = labels_for(units)
        self._unit = labels.length
        self._force = labels.force
        self._pressure = f"{labels.force}/{labels.length}²"
        self._error = ""
        self._loads_error = ""
        self._seismic_error = ""
        self._plan_error = ""
        self.setWindowTitle("Building Wizard")
        self.setProperty(TOPIC_PROPERTY, "define.building")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self._preview = BuildingPreview()
        self.setSideWidget(self._preview)

        self._build_geometry_page()
        self._build_sections_page()
        self._build_loads_page()
        self._build_seismic_page()
        for index, page in enumerate(
            (self._page_geometry, self._page_sections, self._page_loads, self._page_seismic)
        ):
            self.setPage(index, page)
        self._on_code_changed()
        self._refresh()
        self.currentIdChanged.connect(self._on_page_changed)
        self.resize(880, 680)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not event.spontaneous():
            fit_to_available_screen(self)

    def _length(self, metres: float) -> Any:
        return _field(
            length_from_m(metres, self._units),
            minimum=0.0, maximum=1e9, step=length_from_m(0.5, self._units), suffix=self._unit,
        )  # fmt: skip

    def _load(self, kpa: float) -> Any:
        return _field(
            pressure_from_kpa(kpa, self._units),
            minimum=0.0, maximum=1e12, step=0.0, suffix=self._pressure,
        )  # fmt: skip

    # ── pages ───────────────────────────────────────────────────────
    def _build_geometry_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not self._error
        page.setTitle("Geometry")
        page.setSubTitle("Bays each way, storeys, and how the floors are built.")
        form = QFormLayout(page)

        self._bays_x = QSpinBox()
        self._bays_x.setRange(1, 60)
        self._bays_x.setValue(3)
        self._bay_x = self._length(6.0)
        self._widths_x = QLineEdit()
        self._bays_y = QSpinBox()
        self._bays_y.setRange(1, 60)
        self._bays_y.setValue(3)
        self._bay_y = self._length(5.0)
        self._widths_y = QLineEdit()
        for edit in (self._widths_x, self._widths_y):
            edit.setPlaceholderText("Equal bays")
            edit.setToolTip(
                "The width of each bay when they differ, separated by spaces, for example "
                "6 4.5 6. It replaces the number of bays and their width. Empty: equal bays."
            )
        self._storeys = QSpinBox()
        self._storeys.setRange(1, 100)
        self._storeys.setValue(3)
        self._storey_height = self._length(3.0)
        self._first_height = self._length(3.0)
        self._first_height.setToolTip(
            "Height of the first storey, from the base to the first floor. The other "
            "storeys take the storey height."
        )
        self._support = QComboBox()
        for label, _support in SUPPORT_CHOICES:
            self._support.addItem(tr(label))
        self._frame = QComboBox()
        for label in FRAME_LABELS:
            self._frame.addItem(tr(label))
        self._frame.setToolTip(
            "What the frame is made of: it sets the sections created when none is "
            "chosen and the empirical period of the earthquake."
        )
        self._column_angle = QComboBox()
        for label, _angle in COLUMN_ANGLES:
            self._column_angle.addItem(tr(label))
        self._column_angle.setToolTip(
            "Which way the depth of the column section lies: along X the frames along X "
            "bend the columns about their strong axis."
        )
        self._slab = QComboBox()
        for label in SLAB_LABELS:
            self._slab.addItem(tr(label))
        self._slab.setToolTip(
            "How each floor panel hands its load to the beams around it: to the four of "
            "them, or only to the two it spans between (a slab spanning along X rests on "
            "the beams along Y)."
        )
        self._diaphragms = QCheckBox("Rigid diaphragm on every floor")
        self._diaphragms.setChecked(True)
        self._diaphragms.setToolTip(
            "Ties each floor in its own plane to a node at the centre of its mass, where "
            "the earthquake forces and the accidental torque are applied."
        )

        form.addRow("Bays along X:", self._bays_x)
        form.addRow("Bay width along X:", self._bay_x)
        form.addRow("Unequal widths along X:", self._widths_x)
        form.addRow("Bays along Y:", self._bays_y)
        form.addRow("Bay width along Y:", self._bay_y)
        form.addRow("Unequal widths along Y:", self._widths_y)
        form.addRow("Number of storeys:", self._storeys)
        form.addRow("Storey height:", self._storey_height)
        form.addRow("First storey height:", self._first_height)
        form.addRow("Column bases:", self._support)
        form.addRow("Frame material:", self._frame)
        form.addRow("Column section:", self._column_angle)
        form.addRow("Floors:", self._slab)
        form.addRow(self._diaphragms)

        self._geometry_summary = QLabel()
        self._geometry_summary.setWordWrap(True)
        form.addRow(self._geometry_summary)

        for field in (self._bay_x, self._bay_y, self._storey_height, self._first_height):
            field.valueChanged.connect(self._refresh)
        for spin in (self._bays_x, self._bays_y, self._storeys):
            spin.valueChanged.connect(self._refresh)
        for edit in (self._widths_x, self._widths_y):
            edit.textChanged.connect(self._refresh)
        for combo in (self._support, self._column_angle, self._slab):
            combo.currentIndexChanged.connect(self._refresh)
        self._frame.currentIndexChanged.connect(self._on_frame_changed)
        self._diaphragms.toggled.connect(self._refresh)
        self._page_geometry = page

    def _build_sections_page(self) -> None:
        page = QWizardPage()
        page.setTitle("Sections")
        page.setSubTitle("One section for each kind of member.")
        form = QFormLayout(page)
        self._section_combos: dict[str, QComboBox] = {}
        for key in SECTION_KEYS:
            combo = new_section_combo("", self._sections)
            combo.currentIndexChanged.connect(self._refresh_plan)
            self._section_combos[key] = combo
            form.addRow(tr(SECTION_LABELS[key]) + ":", combo)
        button = define_sections_button(self, self._define_sections, self.set_sections)
        if button is not None:
            form.addRow(button)
        note = QLabel(
            "<i>The sections that do not exist yet are created with the building, as the "
            "same undoable step: shapes of the AISC library for a steel frame, solid "
            "rectangles with their gross stiffness for a concrete one. They are a starting "
            "point, not a design.</i>"
        )
        form.addRow(_closing_note(note))
        self._page_sections = page
        self._name_default_sections()

    def _build_loads_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not self._loads_error
        page.setTitle("Floor loads and design code")
        page.setSubTitle("What the floors and the roof carry, and the code that combines it.")
        form = QFormLayout(page)

        self._code = QComboBox()
        for key in BUILDING_CODES:
            self._code.addItem(CODES[key].label, userData=key)
        self._use = QComboBox()
        for key in OCCUPANCIES:
            self._use.addItem(tr(OCCUPANCY_LABELS[key]), userData=key)
        self._use.setCurrentIndex(self._use.findData(DEFAULT_OCCUPANCY))
        self._use.setToolTip("The use of the floors: it sets their live load by the design code.")
        self._floor_dead = self._load(DEFAULT_FLOOR_DEAD_KPA)
        self._floor_dead.setToolTip(
            "Slab, finishes, ceilings and partitions per area of floor. The self weight "
            "of the beams and columns is already in the dead load case."
        )
        self._roof_dead = self._load(DEFAULT_ROOF_DEAD_KPA)
        self._roof_dead.setToolTip("The same on the roof slab.")
        self._floor_live = self._load(0.0)
        self._roof_live = self._load(0.0)
        self._floor_live_seismic = self._load(0.0)
        self._floor_live_seismic.setToolTip(
            "The part of the floor live load that counts as seismic weight: the CVR of "
            "RNC-07 Tabla 1, 0.15 CV by NSCM 9.6 a, none by ASCE 7-16 12.7.2 outside "
            "storage."
        )
        self._roof_live_seismic = self._load(0.0)
        self._roof_live_seismic.setToolTip("The same part of the roof live load.")
        self._combinations = QCheckBox("Generate the load combinations of the code")
        self._combinations.setChecked(True)

        form.addRow("Design code:", self._code)
        form.addRow("Use of the floors:", self._use)
        form.addRow("Floor dead load:", self._floor_dead)
        form.addRow("Roof dead load:", self._roof_dead)
        form.addRow("Floor live load:", self._floor_live)
        form.addRow("Roof live load:", self._roof_live)
        form.addRow("Floor live load in the seismic weight:", self._floor_live_seismic)
        form.addRow("Roof live load in the seismic weight:", self._roof_live_seismic)
        form.addRow(self._combinations)
        self._code_note = QLabel()
        self._code_note.setWordWrap(True)
        form.addRow(self._code_note)
        self._loads_summary = QLabel()
        self._loads_summary.setWordWrap(True)
        form.addRow(self._loads_summary)
        note = QLabel(
            "<i>The slab is not modelled: these loads are floor panels that hand their "
            "load to the beams. The mass of each floor is the dead load case plus this "
            "part of the live load (Define → Mass Source).</i>"
        )
        form.addRow(_closing_note(note))
        self._code.currentIndexChanged.connect(self._on_code_changed)
        self._use.currentIndexChanged.connect(self._on_use_changed)
        for field in (
            self._floor_dead,
            self._roof_dead,
            self._floor_live,
            self._roof_live,
            self._floor_live_seismic,
            self._roof_live_seismic,
        ):
            field.valueChanged.connect(self._refresh_loads)
        self._page_loads = page

    def _build_seismic_page(self) -> None:
        page = _CompletablePage()
        page.complete_check = lambda: not (self._seismic_error or self._plan_error)
        page.setTitle("Earthquake")
        page.setSubTitle("The equivalent lateral force of the code, at every floor.")
        form = QFormLayout(page)

        self._seismic_on = QCheckBox("Create the earthquake load cases")
        self._seismic_on.setChecked(True)
        self._seismic_method = QComboBox()
        for key, label in BUILDING_SEISMIC_METHODS.items():
            self._seismic_method.addItem(tr(label), userData=key)
        self._seismic_a0 = _field(0.3, minimum=0.0, maximum=2.0, step=0.05, suffix="g")
        self._seismic_a0.setToolTip(
            "Peak ground acceleration a0. RNC-07 Art. 24: zone A 0.1, B 0.2, C 0.3 g, or the "
            "value of the map of Anexo C. NSCM Tabla 14.2 per municipality: Managua 0.36667 g."
        )
        self._seismic_soil = QComboBox()
        self._seismic_soil.setToolTip(
            "RNC-07 Art. 25: soil type I (rock) to III (soft). NSCM Tabla 6.4.1: site class "
            "A to D. A softer soil needs a site study."
        )
        self._seismic_class = QComboBox()
        self._seismic_class.setToolTip(
            "RNC-07 Art. 20: group A (essential, forces times 1.5), B or C. NSCM Tabla 5.2.1: "
            "risk category I to IV."
        )
        self._seismic_reduction = _field(2.0, minimum=0.01, maximum=20.0, step=0.5)
        self._seismic_reduction.setToolTip(
            "Q of RNC-07 Art. 21, Ro of NSCM Tabla 5.5.1 or R of ASCE 7-16 Table 12.2-1. "
            "It starts at the value of an ordinary moment frame; raise it only for a "
            "system detailed for more ductility."
        )
        self._seismic_regularity = QComboBox()
        for key, label in RNC07_REGULARITY_LABELS.items():
            self._seismic_regularity.addItem(tr(label), userData=key)
        self._seismic_sds = _field(1.0, minimum=0.0, maximum=10.0, step=0.1, suffix="g")
        self._seismic_sds.setToolTip(
            "ASCE 7-16 11.4.5: design spectral acceleration at short periods, SDS."
        )
        self._seismic_sd1 = _field(0.6, minimum=0.0, maximum=10.0, step=0.1, suffix="g")
        self._seismic_sd1.setToolTip("ASCE 7-16 11.4.5: design spectral acceleration at 1 s, SD1.")
        self._seismic_ie = _field(1.0, minimum=0.01, maximum=10.0, step=0.25)
        self._seismic_ie.setToolTip("ASCE 7-16 Table 1.5-2: importance factor Ie.")
        self._period_x = _field(0.0, minimum=0.0, maximum=100.0, step=0.1, suffix="s")
        self._period_y = _field(0.0, minimum=0.0, maximum=100.0, step=0.1, suffix="s")
        for field in (self._period_x, self._period_y):
            field.setToolTip(
                "Fundamental period in this direction, for example from a modal case. "
                "0 takes the empirical period of the code (NSCM and ASCE 7) or the plateau "
                "of the spectrum (RNC-07, which has no empirical period)."
            )
        self._eccentricity = _field(0.1, minimum=0.0, maximum=0.5, step=0.05)
        self._eccentricity.setToolTip(
            "Accidental eccentricity as a fraction of the floor's dimension across the "
            "earthquake: 0.1 by RNC-07 Art. 32 d, 0.05 by NSCM 9.8 and ASCE 7-16 12.8.4.2. "
            "Each direction then has two cases, one to each side; 0 leaves the torsion out. "
            "It needs the rigid diaphragms."
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
        form.addRow("Reduction factor (Q, Ro or R):", self._seismic_reduction)
        form.addRow("Regularity:", self._seismic_regularity)
        form.addRow("SDS:", self._seismic_sds)
        form.addRow("SD1:", self._seismic_sd1)
        form.addRow("Importance factor Ie:", self._seismic_ie)
        form.addRow("Period along X:", self._period_x)
        form.addRow("Period along Y:", self._period_y)
        form.addRow("Accidental eccentricity:", self._eccentricity)
        form.addRow("Earthquake along:", directions)
        self._seismic_form = form
        self._seismic_summary = QLabel()
        self._seismic_summary.setWordWrap(True)
        form.addRow(self._seismic_summary)
        note = QLabel(
            "<i>The base shear is the coefficient of the code times the seismic weight, "
            "shared between the floors by weight and height and applied at each "
            "diaphragm's node. The stiffness is the gross one: reduce it as your code "
            "asks before you read drifts.</i>"
        )
        form.addRow(_closing_note(note))

        self._seismic_on.toggled.connect(self._refresh_seismic)
        self._seismic_method.currentIndexChanged.connect(self._on_seismic_method_changed)
        for field in (
            self._seismic_a0,
            self._seismic_reduction,
            self._seismic_sds,
            self._seismic_sd1,
            self._seismic_ie,
            self._period_x,
            self._period_y,
            self._eccentricity,
        ):
            field.valueChanged.connect(self._refresh_seismic)
        for combo in (self._seismic_soil, self._seismic_class, self._seismic_regularity):
            combo.currentIndexChanged.connect(self._refresh_seismic)
        self._page_seismic = page
        self._on_seismic_method_changed()

    # ── live state ──────────────────────────────────────────────────
    def _frame_material(self) -> str:
        return FRAME_MATERIALS[self._frame.currentIndex()]

    def _default_section_text(self, key: str) -> str:
        name = default_section_name(key, self._frame_material())
        return tr("{name} (will be created)").format(name=name)

    def _name_default_sections(self) -> None:
        for key, combo in self._section_combos.items():
            combo.setItemText(0, self._default_section_text(key))

    def set_sections(self, sections: list[Any]) -> None:
        """Offer ``sections`` (after Section Library…), keeping each choice still there."""
        self._sections = sections
        for key, combo in self._section_combos.items():
            fill_section_combo(combo, self._default_section_text(key), sections)

    def _on_frame_changed(self, _index: int = 0) -> None:
        self._name_default_sections()
        self._seismic_reduction.setValue(
            DEFAULT_REDUCTION[str(self._seismic_method.currentData()), self._frame_material()]
        )
        self._refresh()

    def _on_code_changed(self, _index: int = 0) -> None:
        code = str(self._code.currentData())
        self._code_note.setText("<i>" + tr(LIVE_LOAD_SOURCES[live_load_family(code)]) + "</i>")
        self._on_use_changed()
        index = self._seismic_method.findData(CODE_PRESETS[code].seismic_method)
        if index >= 0 and index != self._seismic_method.currentIndex():
            self._seismic_method.setCurrentIndex(index)

    def _on_use_changed(self, _index: int = 0) -> None:
        live = occupancy_loads(
            str(self._code.currentData()), str(self._use.currentData()), self._units
        )
        for name, value in live.items():
            field = getattr(self, f"_{name}")
            field.blockSignals(True)
            field.setValue(value)
            field.blockSignals(False)
        self._refresh_loads()

    def _refresh_loads(self, *_args: object) -> None:
        self._loads_error = ""
        text = ""
        try:
            self._gravity_loads()
        except BuildingError as exc:
            self._loads_error = str(exc)
            text = "<b>" + tr("Check the numbers:") + f"</b> {tr(self._loads_error)}"
        self._loads_summary.setText(text)
        self._loads_summary.setVisible(bool(text))
        self._page_loads.completeChanged.emit()

    def _on_seismic_method_changed(self, _index: int = 0) -> None:
        method = str(self._seismic_method.currentData())
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
            (self._seismic_reduction, DEFAULT_REDUCTION[method, self._frame_material()]),
            (self._eccentricity, ACCIDENTAL_ECCENTRICITY[method]),
        ):
            field.blockSignals(True)
            field.setValue(value)
            field.blockSignals(False)
        self._refresh_seismic()

    def _on_page_changed(self, _page_id: int) -> None:
        self._refresh_plan()

    def _refresh(self, *_args: object) -> None:
        for edit, count, width in (
            (self._widths_x, self._bays_x, self._bay_x),
            (self._widths_y, self._bays_y, self._bay_y),
        ):
            equal = not edit.text().strip()
            count.setEnabled(equal)
            width.setEnabled(equal)
        try:
            spec = self.spec()
            building = build_building(
                spec, dict.fromkeys(SECTION_KEYS, 1), first_node_id=1, first_element_id=1
            )
        except BuildingError as exc:
            self._error = str(exc)
            self._geometry_summary.setText(
                "<b>" + tr("Check the numbers:") + f"</b> {tr(self._error)}"
            )
            self._preview.set_building(None)
        else:
            self._error = ""
            self._preview.set_building(building)
            self._geometry_summary.setText(
                tr(
                    "Plan <b>{width} × {depth} {unit}</b>, <b>{storeys}</b> storeys, "
                    "<b>{height} {unit}</b> high: {nodes} joints, {elements} members."
                ).format(
                    width=f"{spec.width:g}",
                    depth=f"{spec.depth:g}",
                    unit=self._unit,
                    storeys=spec.n_storeys,
                    height=f"{spec.height:g}",
                    nodes=len(building.nodes),
                    elements=len(building.elements),
                )
            )
        self._page_geometry.completeChanged.emit()
        self._refresh_seismic()

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
            (self._seismic_sd1, asce),
            (self._seismic_ie, asce),
            (self._period_x, self._seismic_directions["X"].isChecked()),
            (self._period_y, self._seismic_directions["Y"].isChecked()),
            (self._eccentricity, self._diaphragms.isChecked()),
            *((box, True) for box in self._seismic_directions.values()),
        ):
            widget.setEnabled(on and enabled)
        # A method's own numbers only: the page has to fit with its summary.
        for widget, shown in (
            (self._seismic_a0, not asce),
            (self._seismic_soil, not asce),
            (self._seismic_class, not asce),
            (self._seismic_regularity, method == "rnc07"),
            (self._seismic_sds, asce),
            (self._seismic_sd1, asce),
            (self._seismic_ie, asce),
        ):
            self._seismic_form.setRowVisible(widget, shown)
        self._seismic_error = ""
        try:
            self.seismic()
        except BuildingError as exc:
            self._seismic_error = str(exc)
        self._refresh_plan()

    def _refresh_plan(self, *_args: object) -> None:
        """Plan the building as the fields stand, when the last page is the one in sight.

        The plan copies the project and weighs every floor, so it is not made
        on every keystroke of the earlier pages.
        """
        if not hasattr(self, "_page_seismic"):
            return
        self._plan_error = ""
        text = ""
        if self._seismic_error:
            text = "<b>" + tr("Check the numbers:") + f"</b> {tr(self._seismic_error)}"
        elif (
            self._planner is not None
            and not self._error
            and self.currentPage() is self._page_seismic
        ):
            try:
                plan = self._planner(self.spec(), self.section_choice(), self.loads())
            except ValueError as exc:  # BuildingError, or a plan that does not fit
                self._plan_error = str(exc)
                text = "<b>" + tr("Cannot create the building:") + f"</b> {tr(self._plan_error)}"
            else:
                text = self._plan_summary(plan)
        self._seismic_summary.setText(text)
        self._page_seismic.completeChanged.emit()

    def _plan_summary(self, plan: BuildingPlan) -> str:
        lines = [
            tr(
                "<b>{nodes}</b> joints, <b>{elements}</b> members, <b>{cases}</b> new load "
                "cases and <b>{combinations}</b> combinations."
            ).format(
                nodes=len(plan.building.nodes) + len(plan.retained_nodes),
                elements=len(plan.building.elements),
                cases=len(plan.cases),
                combinations=len(plan.combinations),
            )
        ]
        for direction, result in plan.lateral.items():
            lines.append(
                tr(
                    "Earthquake along {direction}: seismic weight <b>{weight} {force}</b>, "
                    "base shear <b>{shear} {force}</b> ({c} of the weight)."
                ).format(
                    direction=direction,
                    weight=f"{result.total_weight:.5g}",
                    shear=f"{result.base_shear:.5g}",
                    force=self._force,
                    c=f"{result.coefficient:.4g}",
                )
            )
        return "<br>".join(lines)

    # ── results ─────────────────────────────────────────────────────
    def _spans(self, edit: QLineEdit, count: QSpinBox, width: Any) -> tuple[float, ...]:
        text = edit.text().strip()
        if not text:
            return (width.value(),) * count.value()
        try:
            return tuple(float(part.replace(",", ".")) for part in text.replace(";", " ").split())
        except ValueError:
            raise BuildingError(
                "The bay widths are numbers separated by spaces, for example 6 4.5 6."
            ) from None

    def spec(self) -> BuildingSpec:
        """The building the fields describe.

        Raises:
            BuildingError: if they do not describe one.
        """
        heights = [self._storey_height.value()] * self._storeys.value()
        heights[0] = self._first_height.value()
        return BuildingSpec(
            spans_x=self._spans(self._widths_x, self._bays_x, self._bay_x),
            spans_y=self._spans(self._widths_y, self._bays_y, self._bay_y),
            storey_heights=tuple(heights),
            base=SUPPORT_CHOICES[self._support.currentIndex()][1],
            frame=self._frame_material(),
            slab=SLAB_SPANS[self._slab.currentIndex()],
            diaphragms=self._diaphragms.isChecked(),
            column_angle=COLUMN_ANGLES[self._column_angle.currentIndex()][1],
        )

    def section_choice(self) -> dict[str, int | None]:
        """Section id per member kind; None means "create the default one"."""
        out: dict[str, int | None] = {}
        for key, combo in self._section_combos.items():
            out[key] = chosen_section(combo)
        return out

    def seismic(self) -> BuildingSeismic | None:
        """The earthquake the fields describe; None when no earthquake cases are wanted.

        Raises:
            BuildingError: if they do not describe one.
        """
        if not self._seismic_on.isChecked():
            return None
        return BuildingSeismic(
            method=str(self._seismic_method.currentData()),
            a0=self._seismic_a0.value(),
            soil=str(self._seismic_soil.currentData() or ""),
            importance_class=str(self._seismic_class.currentData() or ""),
            reduction=self._seismic_reduction.value(),
            regularity=str(self._seismic_regularity.currentData()),
            sds=self._seismic_sds.value(),
            sd1=self._seismic_sd1.value(),
            importance=self._seismic_ie.value(),
            period_x=self._period_x.value(),
            period_y=self._period_y.value(),
            eccentricity=self._eccentricity.value(),
            directions=tuple(d for d, box in self._seismic_directions.items() if box.isChecked()),
        )

    def loads(self) -> BuildingLoads:
        """The floor loads, the code and the earthquake.

        Raises:
            BuildingError: if the numbers do not describe them.
        """
        return self._gravity_loads(self.seismic())

    def _gravity_loads(self, seismic: BuildingSeismic | None = None) -> BuildingLoads:
        return BuildingLoads(
            code=str(self._code.currentData()),
            floor_dead=self._floor_dead.value(),
            roof_dead=self._roof_dead.value(),
            floor_live=self._floor_live.value(),
            roof_live=self._roof_live.value(),
            floor_live_seismic=self._floor_live_seismic.value(),
            roof_live_seismic=self._roof_live_seismic.value(),
            combinations=self._combinations.isChecked(),
            seismic=seismic,
        )


__all__ = ["BuildingPreview", "BuildingWizard"]
