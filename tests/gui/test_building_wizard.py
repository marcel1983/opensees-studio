"""Define → Create Building: the wizard, the preview, one undo step.

The geometry, the loads and the plan are pinned in ``tests/unit/test_building.py``;
here it is the wiring: the fields reach the core spec and loads, the last page
plans the building as the fields stand, the building arrives as one undoable
step with its storeys, diaphragms, mass source, cases and combinations, and a
plan that does not fit is refused before anything is pushed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox

from opensees_studio.commands.building import insert_building_plan, plan_problems
from opensees_studio.core.building import (
    GROUPS,
    BuildingLoads,
    BuildingSeismic,
    BuildingSpec,
    plan_building,
)
from opensees_studio.core.frames import SupportCondition
from opensees_studio.core.sections import ElasticSection
from opensees_studio.core.units import UnitSystem
from opensees_studio.views.controllers.generators import GeneratorsController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.building_wizard import BuildingWizard

pytestmark = pytest.mark.gui

KGF = 9.80665  # N


def _window(qtbot, *, ndm: int = 3, ndf: int = 6):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=ndm, ndf=ndf, dead_case=True, default_materials=True)
    return mw


def _accept(monkeypatch, setup=lambda wizard: None) -> None:  # type: ignore[no-untyped-def]
    def _fake_exec(self: BuildingWizard) -> int:
        setup(self)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(BuildingWizard, "exec", _fake_exec)


def _small(wizard: BuildingWizard) -> None:
    wizard._bays_x.setValue(2)
    wizard._bays_y.setValue(1)
    wizard._storeys.setValue(2)


# ─────────────────────────────── the wizard ───────────────────────────────
def test_the_fields_reach_the_spec(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = BuildingWizard([])
    qtbot.addWidget(wizard)
    wizard._bays_x.setValue(4)
    wizard._bay_x.setValue(7.0)
    wizard._bays_y.setValue(2)
    wizard._bay_y.setValue(5.5)
    wizard._storeys.setValue(5)
    wizard._storey_height.setValue(3.2)
    wizard._first_height.setValue(4.0)
    wizard._support.setCurrentIndex(1)  # pinned
    wizard._frame.setCurrentIndex(1)  # concrete
    wizard._column_angle.setCurrentIndex(1)  # depth along Y
    wizard._slab.setCurrentIndex(2)  # one way along Y
    wizard._diaphragms.setChecked(False)

    spec = wizard.spec()
    assert spec.spans_x == (7.0,) * 4 and spec.spans_y == (5.5, 5.5)
    assert spec.storey_heights == (4.0, 3.2, 3.2, 3.2, 3.2)
    assert spec.base is SupportCondition.PINNED
    assert (spec.frame, spec.slab, spec.diaphragms) == ("concrete", "one_way_y", False)
    assert spec.column_angle == 90.0
    # The default sections follow the material.
    assert wizard._section_combos["column"].itemText(0).startswith("COL 500x500")
    assert wizard.section_choice() == {"column": None, "beam_x": None, "beam_y": None}


def test_unequal_bays_replace_the_count_and_bad_numbers_block_next(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = BuildingWizard([])
    qtbot.addWidget(wizard)
    assert wizard._page_geometry.isComplete()
    before = wizard._preview.line_count()
    assert before > 0

    wizard._widths_x.setText("6 4,5; 6 3")
    assert wizard.spec().spans_x == (6.0, 4.5, 6.0, 3.0)
    assert not wizard._bays_x.isEnabled() and not wizard._bay_x.isEnabled()
    assert wizard._bays_y.isEnabled()
    assert wizard._preview.line_count() > before
    assert "19.5 × 15 m" in wizard._geometry_summary.text()

    wizard._widths_x.setText("6 wide")
    assert not wizard._page_geometry.isComplete()
    assert wizard._preview.line_count() == 0
    assert "separated by spaces" in wizard._geometry_summary.text()
    wizard._widths_x.setText("")
    wizard._storey_height.setValue(0.0)
    assert not wizard._page_geometry.isComplete()
    wizard._storey_height.setValue(3.0)
    assert wizard._page_geometry.isComplete()
    wizard.grab()  # the preview paints


def test_the_code_and_the_use_set_the_live_loads_in_project_units(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = BuildingWizard([])
    qtbot.addWidget(wizard)
    loads = wizard.loads()
    assert loads.code == "rnc07"  # offices, RNC-07 Tabla 1: 250 / 100 kg/m²
    assert loads.floor_live == pytest.approx(250 * KGF)
    assert loads.floor_live_seismic == pytest.approx(100 * KGF)
    assert loads.roof_live == pytest.approx(100 * KGF)
    assert loads.floor_dead == pytest.approx(4500.0) and loads.roof_dead == pytest.approx(3500.0)

    wizard._use.setCurrentIndex(wizard._use.findData("assembly"))
    assert wizard.loads().floor_live == pytest.approx(400 * KGF)
    wizard._code.setCurrentIndex(wizard._code.findData("nscm"))
    loads = wizard.loads()
    assert loads.floor_live_seismic == pytest.approx(0.15 * 400 * KGF)
    assert loads.seismic is not None and loads.seismic.method == "nscm"
    assert "NSCM Tabla 7.1.1" in wizard._code_note.text()
    # The Eurocode has no table of live loads by use here: it is not offered.
    assert wizard._code.findData("en1990") == -1

    # More live load in the seismic weight than there is: the page says so.
    wizard._floor_live_seismic.setValue(wizard._floor_live.value() * 2)
    assert not wizard._page_loads.isComplete()
    assert "cannot exceed" in wizard._loads_summary.text()
    wizard._use.setCurrentIndex(wizard._use.findData("office"))
    assert wizard._page_loads.isComplete() and wizard._loads_summary.text() == ""

    imperial = BuildingWizard([], units=UnitSystem.US_FT_KIP)
    qtbot.addWidget(imperial)
    imperial._code.setCurrentIndex(imperial._code.findData("asce7_lrfd"))
    assert imperial.loads().floor_live == pytest.approx(0.050, rel=1e-3)  # 50 psf, offices
    assert imperial._bay_x.value() == pytest.approx(6.0 / 0.3048)


def test_the_earthquake_page_follows_the_code_and_reaches_the_loads(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = BuildingWizard([])
    qtbot.addWidget(wizard)
    seismic = wizard.seismic()
    assert seismic == BuildingSeismic(
        method="rnc07", a0=0.3, soil="II", importance_class="B", reduction=2.0, eccentricity=0.1
    )
    assert wizard._seismic_regularity.isEnabled() and not wizard._seismic_sds.isEnabled()

    wizard._code.setCurrentIndex(wizard._code.findData("nscm"))
    seismic = wizard.seismic()
    assert (seismic.method, seismic.soil, seismic.importance_class) == ("nscm", "C", "II")
    assert seismic.a0 == pytest.approx(0.36667)
    assert seismic.reduction == 3.5 and seismic.eccentricity == 0.05  # ordinary steel frame
    wizard._frame.setCurrentIndex(1)
    assert wizard.seismic().reduction == 3.0  # ordinary concrete frame

    wizard._code.setCurrentIndex(wizard._code.findData("asce7_lrfd"))
    assert wizard._seismic_method.currentData() == "asce7"
    assert wizard._seismic_sds.isEnabled() and wizard._seismic_sd1.isEnabled()
    assert not wizard._seismic_a0.isEnabled() and not wizard._seismic_soil.isEnabled()
    wizard._seismic_sds.setValue(0.9)
    wizard._seismic_sd1.setValue(0.4)
    wizard._seismic_ie.setValue(1.25)
    wizard._period_x.setValue(0.8)
    wizard._eccentricity.setValue(0.0)
    wizard._seismic_directions["Y"].setChecked(False)
    assert not wizard._period_y.isEnabled()
    seismic = wizard.seismic()
    assert (seismic.sds, seismic.sd1, seismic.importance) == (0.9, 0.4, 1.25)
    assert (seismic.period_x, seismic.eccentricity, seismic.directions) == (0.8, 0.0, ("X",))

    wizard._seismic_directions["X"].setChecked(False)
    assert not wizard._page_seismic.isComplete()
    assert "at least one earthquake direction" in wizard._seismic_summary.text()
    wizard._seismic_on.setChecked(False)
    assert wizard._page_seismic.isComplete() and wizard.loads().seismic is None


def test_the_last_page_plans_the_building_as_the_fields_stand(qtbot) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    project = mw._vm.project
    calls: list[BuildingSpec] = []

    def planner(spec, sections, loads):  # type: ignore[no-untyped-def]
        calls.append(spec)
        return plan_building(project, spec, sections=sections, loads=loads)

    wizard = BuildingWizard([], units=project.meta.units, planner=planner)
    qtbot.addWidget(wizard)
    _small(wizard)
    before = project.model_dump()
    assert calls == []  # nothing is planned while the first pages are in sight

    wizard.show()
    for _ in range(3):
        wizard.next()
    assert wizard.currentPage() is wizard._page_seismic
    assert len(calls) == 1
    summary = wizard._seismic_summary.text()
    assert "<b>20</b> joints, <b>26</b> members" in summary  # 18 joints and 2 diaphragm nodes
    assert "Earthquake along X" in summary and "Earthquake along Y" in summary
    assert "base shear" in summary and wizard._page_seismic.isComplete()
    assert project.model_dump() == before  # planned, not built

    # A field of the page plans again; what cannot be planned blocks Finish and says why.
    wizard._seismic_a0.setValue(0.2)
    assert len(calls) == 2 and wizard._seismic_summary.text() != summary
    wizard._seismic_a0.setValue(0.0)
    assert not wizard._page_seismic.isComplete()
    assert "Cannot create the building" in wizard._seismic_summary.text()
    wizard._seismic_on.setChecked(False)
    assert wizard._page_seismic.isComplete()
    assert "Earthquake along" not in wizard._seismic_summary.text()
    wizard.close()


# ──────────────────────────── through the menu ────────────────────────────
def test_the_menu_builds_the_building_in_one_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: pytest.fail(str(a[2])))
    _accept(monkeypatch, _small)
    project = mw._vm.project
    before = project.model_dump()
    index = mw._vm.undo_stack.index()
    mw._refresh_action_enablement()
    action = mw.action("define.building_wizard")
    assert action.isEnabled() and action is mw._act_building_wizard
    assert isinstance(mw.generators, GeneratorsController)

    action.trigger()

    assert mw._vm.undo_stack.index() == index + 1  # one step
    assert mw._vm.undo_stack.undoText() == "Create building"
    assert len(project.elements) == 26  # 12 columns, 8 beams along X and 6 along Y
    assert [g.name for g in project.groups] == list(GROUPS.values())
    grouped = {eid for g in project.groups for eid in g.element_ids}
    assert grouped == {e.id for e in project.elements}
    assert {s.name for s in project.sections} >= {"W14X90", "W18X50"}
    assert [s.name for s in project.storeys] == ["Storey 1", "Roof"]
    assert len(project.diaphragms) == 2
    retained = {d.retained_node for d in project.diaphragms}
    assert retained <= {n.id for n in project.nodes} and len(project.nodes) == 18 + 2
    assert [c.name for c in project.analyses] == [
        "DEAD", "LIVE", "ROOF LIVE", "EQ X +e", "EQ X -e", "EQ Y +e", "EQ Y -e"
    ]  # fmt: skip
    assert project.mass_source is not None and len(project.mass_source.patterns) == 3
    assert project.combinations and project.coord_systems[-1].name == "Building"
    log = mw._console.toPlainText()
    assert "Building 12 x 5" in log and "2 storey(s) and 2 rigid diaphragm(s)" in log
    assert "Earthquake along X by RNC-07 Art. 32" in log

    mw._vm.undo_stack.undo()
    assert project.model_dump() == before
    mw._vm.undo_stack.redo()
    assert len(project.elements) == len(grouped)
    project.validate_references()


def test_the_chosen_sections_are_used_and_only_the_others_are_created(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    _accept(monkeypatch, _small)
    mw.action("define.building_wizard").trigger()
    project = mw._vm.project
    column, beam = (
        next(s.id for s in project.sections if s.name == name) for name in ("W14X90", "W18X50")
    )
    sections = len(project.sections)
    elastic = [s for s in project.sections if isinstance(s, ElasticSection)]
    seen: dict[str, object] = {}

    def choose(wizard: BuildingWizard) -> None:
        _small(wizard)
        seen["items"] = wizard._section_combos["column"].count()
        wizard._section_combos["column"].setCurrentIndex(
            wizard._section_combos["column"].findData(beam)
        )
        wizard._section_combos["beam_x"].setCurrentIndex(
            wizard._section_combos["beam_x"].findData(column)
        )
        wizard._seismic_on.setChecked(False)
        seen["choice"] = wizard.section_choice()

    _accept(monkeypatch, choose)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: pytest.fail(str(a[2])))
    first = max(e.id for e in project.elements)
    mw.action("define.building_wizard").trigger()
    assert seen["items"] == 1 + len(elastic)
    assert seen["choice"] == {"column": beam, "beam_x": column, "beam_y": None}
    assert len(project.sections) == sections + 1  # only the one of the beams along Y
    new = [e for e in project.elements if e.id > first]
    assert {e.section_id for e in new} == {column, beam, project.sections[-1].id}
    # The second building stands on the first: its floors keep their storeys.
    assert len(project.storeys) == 2


def test_cancelling_leaves_the_project_alone(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    monkeypatch.setattr(BuildingWizard, "exec", lambda self: int(QDialog.DialogCode.Rejected))
    before = mw._vm.project.model_dump()
    mw.action("define.building_wizard").trigger()
    assert mw._vm.project.model_dump() == before
    assert mw._vm.undo_stack.count() == 0


def test_a_2d_project_is_told_why_not(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot, ndm=2, ndf=3)
    seen: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _p, _t, text: seen.append(text) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(BuildingWizard, "exec", lambda self: pytest.fail("the wizard opened"))
    mw.action("define.building_wizard").trigger()
    assert seen and "ndm = 2" in seen[0]
    assert mw._vm.project.nodes == []


def test_what_cannot_be_built_is_reported_and_nothing_is_pushed(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    told: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda _p, _t, text: told.append(text))

    def no_ground_motion(wizard: BuildingWizard) -> None:
        _small(wizard)
        wizard._seismic_a0.setValue(0.0)

    _accept(monkeypatch, no_ground_motion)
    before = mw._vm.project.model_dump()
    mw.action("define.building_wizard").trigger()
    assert told and "a0" in told[0]
    assert mw._vm.project.model_dump() == before
    assert mw._vm.undo_stack.count() == 0


def test_the_new_model_template_opens_the_wizard(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.core.templates import TEMPLATE_NDF, TEMPLATES
    from opensees_studio.views.dialogs.new_model import NewModelDialog

    assert TEMPLATES["building"] == "Building" and TEMPLATE_NDF["building"] == (3, 6)
    dialog = NewModelDialog()
    qtbot.addWidget(dialog)
    dialog.select_template("building")
    assert dialog.template() == "building" and "Building Wizard" in dialog.hint.text()

    mw = _window(qtbot)
    _accept(monkeypatch, _small)
    mw._start_template("building", UnitSystem.SI_MM_N, None)
    project = mw._vm.project
    assert project.meta.units is UnitSystem.SI_MM_N
    assert max(n.coords[0] for n in project.nodes) == pytest.approx(12_000.0)
    assert project.elements and project.diaphragms


def test_the_command_is_in_the_menu_the_ribbon_and_the_help(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.core.help import ACTION_TOPICS, TOPICS
    from opensees_studio.views.ribbon.icons import command_icon_name, has_icon
    from opensees_studio.views.ribbon.layout import RIBBON_LAYOUT

    mw = _window(qtbot)
    action = mw.action("define.building_wizard")
    define = next(m for m in mw.menuBar().actions() if "Define" in m.text().replace("&", ""))
    entries = define.menu().actions()
    assert entries.index(action) == entries.index(mw._act_warehouse_wizard) + 1
    placed = [
        name for _tab, _key, groups in RIBBON_LAYOUT for _g, names in groups for name in names
    ]
    assert "_act_building_wizard" in placed
    assert has_icon(command_icon_name("_act_building_wizard"))
    assert ACTION_TOPICS["_act_building_wizard"] == "define.building"
    assert "define.building" in TOPICS["define.warehouse"].see_also


# ─────────────────────────── the insertion ───────────────────────────
def test_a_plan_that_does_not_fit_is_refused_before_anything_is_pushed(qtbot) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    project = mw._vm.project
    spec = BuildingSpec.regular(
        bays_x=1, bay_x=6.0, bays_y=1, bay_y=5.0, storeys=2, storey_height=3.0
    )
    plan = plan_building(project, spec, loads=BuildingLoads(floor_dead=3000.0, roof_dead=3000.0))
    assert plan_problems(project, plan) == []
    insert_building_plan(mw._vm, plan)
    before = project.model_dump()
    index = mw._vm.undo_stack.index()

    # The same plan again: every id it carries is now taken.
    problems = plan_problems(project, plan)
    assert any("Node id" in p for p in problems) and any("Storey id" in p for p in problems)
    with pytest.raises(ValueError, match="already in use"):
        insert_building_plan(mw._vm, plan)
    assert project.model_dump() == before
    assert mw._vm.undo_stack.index() == index


# ─────────────────── the controller, without the main window ───────────────────
def test_the_controller_runs_on_a_bare_window(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.viewmodels import ProjectViewModel

    class Canvas:
        reframed = 0

        def reframe(self) -> None:
            self.reframed += 1

    window = QMainWindow()
    qtbot.addWidget(window)
    vm = ProjectViewModel()
    vm.new_project(ndm=3, ndf=6, dead_case=True, default_materials=True)
    canvas, log = Canvas(), []
    controller = GeneratorsController(
        Shell(
            window=window,
            vm=vm,
            canvas=lambda: canvas,
            log=log.append,
            refresh_actions=lambda: None,
        )
    )
    _accept(monkeypatch, _small)
    controller.create_building()
    assert len(vm.project.elements) == 26 and vm.undo_stack.count() == 1
    assert canvas.reframed == 1
    assert log[0].startswith("Building 12 x 5") and any("combination" in line for line in log)
