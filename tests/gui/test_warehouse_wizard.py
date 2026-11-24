"""Define → Create Warehouse: the wizard, the preview, one undo step.

The geometry, the loads and the plan are pinned in ``tests/unit/test_warehouse.py``;
here it is the wiring: the fields reach the core spec, the warehouse arrives as
one undoable step with its sections, groups, cases and combinations, and a plan
that does not fit is refused before anything is pushed.
"""

from __future__ import annotations

import dataclasses

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands.warehouse import insert_warehouse_plan, plan_problems
from opensees_studio.core.frames import RoofType, SupportCondition
from opensees_studio.core.trusses import TrussType
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    GROUPS,
    TRUSS_GROUPS,
    WarehouseSeismic,
    WarehouseSnow,
    WarehouseSpec,
    WarehouseWind,
    plan_warehouse,
)
from opensees_studio.core.wind import KGF
from opensees_studio.views.dialogs.frame_wizard import ROOF_CHOICES
from opensees_studio.views.dialogs.warehouse_wizard import WarehouseWizard


def _window(qtbot, *, ndm: int = 3, ndf: int = 6):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=ndm, ndf=ndf, dead_case=True, default_materials=True)
    return mw


def _accept(monkeypatch, setup=lambda wizard: None) -> None:  # type: ignore[no-untyped-def]
    def _fake_exec(self: WarehouseWizard) -> int:
        setup(self)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(WarehouseWizard, "exec", _fake_exec)


# ─────────────────────────────── the wizard ───────────────────────────────
@pytest.mark.gui
def test_the_fields_reach_the_spec(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([])
    qtbot.addWidget(wizard)
    wizard._roof.setCurrentIndex(1)  # one slope
    wizard._span.setValue(15.0)
    wizard._n_naves.setValue(2)
    wizard._n_frames.setValue(8)
    wizard._frame_spacing.setValue(5.0)
    wizard._eave_height.setValue(7.0)
    wizard._slope.setValue(12.0)
    wizard._support.setCurrentIndex(0)
    wizard._purlin_spacing.setValue(1.2)
    wizard._girt_spacing.setValue(0.0)
    wizard._rafter_fly.setValue(3)
    assert wizard._purlin_rods.value() == 1  # a line at mid-bay unless told otherwise
    assert wizard._sheeting.isChecked()
    wizard._purlin_rods.setValue(2)
    wizard._girt_rods.setValue(1)
    wizard._sheeting.setChecked(False)
    wizard._end_wall_spacing.setValue(4.0)
    wizard._wall_bracing.setChecked(False)
    wizard._braced_bays.setText("1, 4; 7")

    spec = wizard.spec()
    assert spec == WarehouseSpec(
        span=15.0,
        eave_height=7.0,
        frame_spacing=5.0,
        n_frames=8,
        n_naves=2,
        roof=RoofType.MONO_PITCH,
        slope=0.12,
        support=SupportCondition.FIXED,
        purlin_spacing=1.2,
        girt_spacing=0.0,
        rafter_fly_brace_every=3,
        roof_bracing=True,
        wall_bracing=False,
        braced_bays=(0, 3, 6),
        end_wall_column_spacing=4.0,
        sheeting=False,
        purlin_sag_rods=2,
        girt_sag_rods=1,
    )
    assert wizard.section_choice() == dict.fromkeys(
        ("column", "rafter", "purlin", "girt", "brace", "end_column")
    )


@pytest.mark.gui
def test_the_truss_fields_reach_the_spec_and_follow_the_roof_structure(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([])
    qtbot.addWidget(wizard)
    truss_fields = (
        wizard._truss_type, wizard._truss_bottom, wizard._truss_depth, wizard._chord_ties
    )  # fmt: skip
    assert not any(w.isEnabled() for w in truss_fields)
    assert wizard._rafter_fly.isEnabled()
    assert not wizard.spec().has_truss
    rafter_lines = wizard._preview.line_count()

    wizard._roof_structure.setCurrentIndex(1)
    assert all(w.isEnabled() for w in truss_fields)
    assert not wizard._rafter_fly.isEnabled()  # a purlin is fixed to the top chord
    wizard._truss_type.setCurrentIndex(1)
    wizard._truss_bottom.setCurrentIndex(1)
    wizard._truss_depth.setValue(1.2)
    wizard._chord_ties.setValue(3)
    spec = wizard.spec()
    assert spec.has_truss
    assert (spec.truss_type, spec.truss_bottom) == (TrussType.HOWE, "parallel")
    assert (spec.truss_depth, spec.bottom_chord_tie_every) == (1.2, 3)
    assert wizard._preview.line_count() > rafter_lines
    assert "Clear height under the trusses" in wizard._geometry_summary.text()
    assert "Bottom chord unbraced length" in wizard._secondary_summary.text()
    assert list(wizard.section_choice()) == [
        "column", "purlin", "girt", "brace", "end_column",
        "top_chord", "bottom_chord", "truss_web", "chord_tie",
    ]  # fmt: skip
    form = wizard._sections_form
    assert not form.isRowVisible(wizard._section_combos["rafter"])
    assert form.isRowVisible(wizard._section_combos["top_chord"])

    wizard._truss_depth.setValue(6.0)  # as deep as the eave is high
    assert not wizard._page_geometry.isComplete()
    assert "less than the eave height" in wizard._geometry_summary.text()
    wizard._roof_structure.setCurrentIndex(0)  # with rafters the depth does not matter
    assert wizard._page_geometry.isComplete()
    assert form.isRowVisible(wizard._section_combos["rafter"])
    assert not form.isRowVisible(wizard._section_combos["top_chord"])


@pytest.mark.gui
def test_the_preview_follows_the_fields_and_bad_numbers_block_next(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([])
    qtbot.addWidget(wizard)
    assert wizard._page_geometry.isComplete()
    before = wizard._preview.line_count()
    assert before > 0
    wizard._n_frames.setValue(wizard._n_frames.value() + 2)
    assert wizard._preview.line_count() > before

    wizard._span.setValue(0.0)
    assert not wizard._page_geometry.isComplete()
    assert wizard._preview.line_count() == 0
    assert "must be positive" in wizard._geometry_summary.text()
    wizard._span.setValue(20.0)
    wizard._braced_bays.setText("two")
    assert not wizard._page_secondary.isComplete()
    wizard._braced_bays.setText("99")
    assert not wizard._page_secondary.isComplete()
    wizard._braced_bays.setText("")
    assert wizard._page_secondary.isComplete()
    wizard.grab()  # the preview paints


@pytest.mark.gui
def test_the_code_sets_the_roof_live_defaults_in_project_units(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([], units=UnitSystem.US_FT_KIP)
    qtbot.addWidget(wizard)
    assert wizard.loads().code == "rnc07"
    assert wizard._roof_live.value() == pytest.approx(10 * 9.80665 / 47880.26, rel=1e-4)  # ksf
    assert wizard._point.value() == pytest.approx(200 * 9.80665 / 4448.222, rel=1e-6)  # kip
    wizard._code.setCurrentIndex(wizard._code.findData("asce7_lrfd"))
    loads = wizard.loads()
    assert loads.code == "asce7_lrfd"
    assert loads.roof_live == pytest.approx(0.020, rel=1e-3)  # 20 psf
    assert loads.midspan_point == 0.0
    assert wizard._span.value() == pytest.approx(20.0 / 0.3048)


# ──────────────────────────── through the menu ────────────────────────────
@pytest.mark.gui
def test_the_menu_builds_the_warehouse_in_one_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: pytest.fail(str(a[2])))
    _accept(monkeypatch, lambda w: w._n_frames.setValue(3))
    project = mw._vm.project
    before = project.model_dump()
    index = mw._vm.undo_stack.index()
    mw._refresh_action_enablement()
    assert mw._act_warehouse_wizard.isEnabled()

    mw._act_warehouse_wizard.trigger()

    assert mw._vm.undo_stack.index() == index + 1  # one step
    assert len({n.coords[1] for n in project.nodes}) == 3
    assert [g.name for g in project.groups] == [
        name for key, name in GROUPS.items() if key not in TRUSS_GROUPS
    ]
    grouped = {eid for g in project.groups for eid in g.element_ids}
    assert grouped == {e.id for e in project.elements}
    assert {s.name for s in project.sections} >= {
        "W14X48", "W16X40", "C150X50X15X2.38", "W8X31"
    }  # fmt: skip
    assert [c.name for c in project.analyses] == [
        "DEAD", "LIVE", "WIND +X", "WIND -X", "WIND +Y", "WIND -Y"
    ]  # fmt: skip
    names = [c.name for c in project.combinations]
    assert names[:2] == ["1.4CM", "1.2CM+1.6CV"]
    # A wind case enters with its own sign only: reversing a suction is not a wind.
    assert "1.2CM+1.6Pz:WIND +X+CV" in names and "0.9CM+1.6Pz:WIND -Y" in names
    assert not any("-1.6Pz" in name for name in names)
    assert project.design is not None and project.design.members
    assert project.coord_systems[-1].name == "Warehouse"
    assert "Warehouse 20 x 12" in mw._console.toPlainText()

    mw._vm.undo_stack.undo()
    assert project.model_dump() == before
    mw._vm.undo_stack.redo()
    assert len(project.elements) == len(grouped)


@pytest.mark.gui
def test_cancelling_leaves_the_project_alone(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    monkeypatch.setattr(WarehouseWizard, "exec", lambda self: int(QDialog.DialogCode.Rejected))
    before = mw._vm.project.model_dump()
    mw._act_warehouse_wizard.trigger()
    assert mw._vm.project.model_dump() == before


@pytest.mark.gui
def test_a_2d_project_is_told_why_not(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot, ndm=2, ndf=3)
    seen: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _p, _t, text: seen.append(text) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(WarehouseWizard, "exec", lambda self: pytest.fail("the wizard opened"))
    mw._act_warehouse_wizard.trigger()
    assert seen and "ndm = 2" in seen[0]
    assert mw._vm.project.nodes == []


@pytest.mark.gui
def test_the_new_model_template_opens_the_wizard(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.core.templates import TEMPLATE_NDF, TEMPLATES

    assert TEMPLATES["warehouse"] == "Warehouse" and TEMPLATE_NDF["warehouse"] == (3, 6)
    mw = _window(qtbot)
    _accept(monkeypatch, lambda w: w._n_frames.setValue(2))
    mw._start_template("warehouse", UnitSystem.SI_MM_N, None)
    project = mw._vm.project
    assert project.meta.units is UnitSystem.SI_MM_N
    assert max(n.coords[0] for n in project.nodes) == pytest.approx(20_000.0)
    assert project.elements


# ─────────────────────────── the insertion ───────────────────────────
@pytest.mark.gui
def test_a_plan_that_does_not_fit_is_refused_before_anything_is_pushed(qtbot) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    project = mw._vm.project
    spec = WarehouseSpec(span=10.0, eave_height=4.0, frame_spacing=5.0, n_frames=2)
    plan = plan_warehouse(project, spec)
    assert plan_problems(project, plan) == []
    insert_warehouse_plan(mw._vm, plan)
    before = project.model_dump()
    index = mw._vm.undo_stack.index()

    # The same plan again: every id it carries is now taken.
    problems = plan_problems(project, plan)
    assert any("Node id" in p for p in problems) and any("Element id" in p for p in problems)
    with pytest.raises(ValueError, match="already in use"):
        insert_warehouse_plan(mw._vm, plan)
    assert project.model_dump() == before
    assert mw._vm.undo_stack.index() == index


@pytest.mark.gui
def test_the_wind_page_follows_the_code_and_reaches_the_loads(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([])
    qtbot.addWidget(wizard)
    wind = wizard.loads().wind
    # RNC-07 by default: zone 2, Group B, roughness R2, flat terrain.
    assert wind == WarehouseWind(method="rnc07", speed=45.0, exposure="R2", topography="T3")
    assert not wizard._wind_kzt.isEnabled() and wizard._wind_topography.isEnabled()
    assert "4</b>" in wizard._wind_summary.text()

    wizard._wind_zone.setCurrentIndex(5)  # zone 3, Group A
    assert wizard._wind_speed.value() == 70.0
    wizard._wind_speed.setValue(50.0)  # not a value of Tabla 5
    assert wizard._wind_zone.currentIndex() == wizard._wind_zone.count() - 1

    wizard._code.setCurrentIndex(wizard._code.findData("asce7_lrfd"))
    assert wizard._wind_method.currentData() == "asce7"
    assert wizard._wind_speed.value() == 57.0  # an ultimate speed, not RNC-07's 50 year one
    assert [wizard._wind_exposure.itemData(i) for i in range(3)] == ["B", "C", "D"]
    assert wizard._wind_kzt.isEnabled() and not wizard._wind_zone.isEnabled()
    wizard._wind_openings.setCurrentIndex(4)  # mainly in the end wall at the smallest Y
    wizard._wind_directions["-X"].setChecked(False)
    wizard._wind_directions["-Y"].setChecked(False)
    assert wizard.loads().wind == WarehouseWind(
        method="asce7", speed=57.0, exposure="C", openings="y0", directions=("+X", "+Y")
    )
    assert "4</b>" in wizard._wind_summary.text()  # two cases per direction

    for box in wizard._wind_directions.values():
        box.setChecked(False)
    assert not wizard._page_wind.isComplete()  # a wind with no direction
    wizard._wind_on.setChecked(False)
    assert wizard._page_wind.isComplete() and wizard.loads().wind is None
    assert not wizard._wind_speed.isEnabled()


@pytest.mark.gui
def test_the_eurocode_brings_its_wind_snow_and_earthquake(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([])
    qtbot.addWidget(wizard)
    wizard._code.setCurrentIndex(wizard._code.findData("en1990"))
    loads = wizard.loads()
    assert loads.code == "en1990"
    # EN 1991-1-1 Table 6.10, category H: 0.4 kN/m² and no point load with it.
    assert loads.roof_live == pytest.approx(400.0) and loads.midspan_point == 0.0
    assert loads.wind == WarehouseWind(method="en1991", speed=26.0, exposure="II")
    assert [wizard._wind_exposure.itemData(i) for i in range(5)] == ["0", "I", "II", "III", "IV"]
    assert wizard._wind_kzt.isEnabled() and not wizard._wind_zone.isEnabled()
    assert not wizard._wind_topography.isEnabled()
    # The default roof is a gable at 10 %: four cases across the ridge, two along it.
    assert "12</b>" in wizard._wind_summary.text()
    wizard._wind_kzt.setValue(1.1)  # the orography factor
    wind = wizard.loads().wind
    assert wind is not None and wind.topographic_factor == 1.1

    wizard._seismic_on.setChecked(True)
    seismic = wizard.loads().seismic
    assert seismic == WarehouseSeismic(
        method="en1998", a0=0.15, soil="C", importance_class="II", reduction=1.5
    )
    assert [wizard._seismic_soil.itemData(i) for i in range(5)] == ["A", "B", "C", "D", "E"]
    assert "c = 0.2875" in wizard._seismic_summary.text()  # 2.5 x 0.15 x 1.15 / 1.5
    assert not wizard._seismic_sds.isEnabled() and not wizard._seismic_regularity.isEnabled()

    wizard._snow_on.setChecked(True)
    snow = wizard.loads().snow
    assert snow is not None and snow.method == "en1991"
    assert snow.ground == pytest.approx(1000.0)  # sk = 1 kN/m² to start with
    # Back to RNC-07: its own procedures again.
    wizard._code.setCurrentIndex(wizard._code.findData("rnc07"))
    assert wizard._wind_method.currentData() == "rnc07" and wizard._wind_speed.value() == 45.0
    assert wizard._seismic_method.currentData() == "rnc07"


@pytest.mark.gui
def test_the_menu_builds_a_trussed_warehouse_in_one_undo_step(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: pytest.fail(str(a[2])))

    def setup(wizard: WarehouseWizard) -> None:
        wizard._n_frames.setValue(3)
        wizard._roof_structure.setCurrentIndex(1)

    _accept(monkeypatch, setup)
    project = mw._vm.project
    before = project.model_dump()
    index = mw._vm.undo_stack.index()

    mw._act_warehouse_wizard.trigger()

    assert mw._vm.undo_stack.index() == index + 1
    names = [g.name for g in project.groups]
    assert GROUPS["rafters"] not in names
    assert names[-len(TRUSS_GROUPS) :] == [GROUPS[key] for key in TRUSS_GROUPS]
    grouped = {eid for g in project.groups for eid in g.element_ids}
    assert grouped == {e.id for e in project.elements}
    assert {s.name for s in project.sections} >= {"HSS6X6X1_4", "HSS3X3X3_16"}
    assert "W16X40" not in {s.name for s in project.sections}  # no rafter, no rafter section
    assert project.design is not None and project.design.members
    project.validate_references()

    mw._vm.undo_stack.undo()
    assert project.model_dump() == before


@pytest.mark.gui
def test_the_earthquake_page_follows_the_code_and_reaches_the_loads(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([])
    qtbot.addWidget(wizard)
    # Off until asked for: a0, the soil and Q belong to the site and the structure.
    assert wizard.loads().seismic is None
    assert wizard._page_seismic.isComplete() and not wizard._seismic_a0.isEnabled()
    assert wizard._seismic_summary.text() == ""

    def chosen() -> WarehouseSeismic:
        seismic = wizard.loads().seismic
        assert seismic is not None
        return dataclasses.replace(seismic, roof_live=round(seismic.roof_live, 6))

    cvr = round(10.0 * KGF, 6)  # 10 kg/m², in N/m²
    wizard._seismic_on.setChecked(True)
    # RNC-07 by default: zone C, soil II, Group B, Q = 2, 10 kg/m² of roof live load.
    assert chosen() == WarehouseSeismic(
        method="rnc07", a0=0.3, soil="II", importance_class="B", roof_live=cvr
    )
    assert "c = 0.45" in wizard._seismic_summary.text()
    assert wizard._seismic_regularity.isEnabled() and not wizard._seismic_sds.isEnabled()
    wizard._seismic_soil.setCurrentIndex(wizard._seismic_soil.findData("I"))
    wizard._seismic_reduction.setValue(1.0)
    assert "c = 0.405" in wizard._seismic_summary.text()

    wizard._code.setCurrentIndex(wizard._code.findData("nscm"))
    assert wizard._seismic_method.currentData() == "nscm"
    assert [wizard._seismic_soil.itemData(i) for i in range(4)] == ["A", "B", "C", "D"]
    assert not wizard._seismic_regularity.isEnabled()
    assert chosen() == WarehouseSeismic(
        method="nscm",
        a0=0.36667,
        soil="C",
        importance_class="II",
        roof_live=round(0.3 * cvr, 6),  # NSCM 9.6 b: 0.3 CV in a warehouse
    )
    wizard._seismic_reduction.setValue(0.5)  # Ro below 1: the code refuses it
    assert not wizard._page_seismic.isComplete()
    assert "Ro" in wizard._seismic_summary.text()

    wizard._code.setCurrentIndex(wizard._code.findData("asce7_lrfd"))
    assert wizard._page_seismic.isComplete()
    assert wizard._seismic_sds.isEnabled() and not wizard._seismic_a0.isEnabled()
    assert not wizard._seismic_soil.isEnabled() and wizard._seismic_soil.count() == 0
    wizard._seismic_sds.setValue(0.9)
    wizard._seismic_ie.setValue(1.25)
    wizard._seismic_directions["Y"].setChecked(False)
    assert chosen() == WarehouseSeismic(
        method="asce7", a0=0.0, soil="", reduction=3.0, sds=0.9, importance=1.25,
        directions=("X",),
    )  # fmt: skip
    assert "<b>1</b>" in wizard._seismic_summary.text()
    assert "c = 0.375" in wizard._seismic_summary.text()

    wizard._seismic_directions["X"].setChecked(False)
    assert not wizard._page_seismic.isComplete()  # an earthquake with no direction
    wizard._seismic_on.setChecked(False)
    assert wizard._page_seismic.isComplete() and wizard.loads().seismic is None


@pytest.mark.gui
def test_the_menu_adds_the_earthquake_cases_to_the_warehouse(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: pytest.fail(str(a[2])))

    def setup(wizard: WarehouseWizard) -> None:
        wizard._n_frames.setValue(3)
        wizard._wind_on.setChecked(False)
        wizard._seismic_on.setChecked(True)

    _accept(monkeypatch, setup)
    project = mw._vm.project
    before = project.model_dump()

    mw._act_warehouse_wizard.trigger()

    assert [c.name for c in project.analyses] == ["DEAD", "LIVE", "EQ X", "EQ Y"]
    patterns = {p.name: p for p in project.load_patterns}
    assert patterns["EQ X"].nodal_loads and patterns["EQ Y"].nodal_loads
    names = [c.name for c in project.combinations]
    assert "0.9CM+Fs:EQ X+0.3Fs:EQ Y" in names and "0.9CM-Fs:EQ Y-0.3Fs:EQ X" in names
    assert "2 earthquake case(s) by RNC-07 Art. 32" in mw._console.toPlainText()
    project.validate_references()

    mw._vm.undo_stack.undo()
    assert project.model_dump() == before


@pytest.mark.gui
def test_the_ash_and_snow_page_follows_the_code_and_reaches_the_loads(qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = WarehouseWizard([])
    qtbot.addWidget(wizard)
    # Off until asked for.
    assert wizard.loads().snow is None
    assert wizard._page_snow.isComplete() and not wizard._snow_ground.isEnabled()
    assert wizard._snow_summary.text() == ""

    def chosen() -> WarehouseSnow:
        snow = wizard.loads().snow
        assert snow is not None
        return dataclasses.replace(snow, ground=round(snow.ground, 4))

    wizard._snow_on.setChecked(True)
    # RNC-07 by default: 20 kg/m² of wet ash (Art. 14), one case.
    assert chosen() == WarehouseSnow(method="ash", ground=round(20.0 * KGF, 4))
    assert wizard._snow_ground.isEnabled() and not wizard._snow_ce.isEnabled()
    assert not wizard._snow_unbalanced.isEnabled() and not wizard._snow_slippery.isEnabled()
    assert wizard._snow_summary.text().startswith("Load case ASH: <b>196.1 ")
    wizard._code.setCurrentIndex(wizard._code.findData("nscm"))
    assert wizard._snow_method.currentData() == "ash"

    wizard._code.setCurrentIndex(wizard._code.findData("asce7_lrfd"))
    assert wizard._snow_method.currentData() == "asce7"
    assert chosen() == WarehouseSnow(method="asce7", ground=957.6)  # 20 psf
    assert wizard._snow_is.isEnabled() and wizard._snow_slippery.isEnabled()
    # The default roof is a gable at 10 %: the balanced load and the two drifts.
    assert "SNOW, SNOW +X, SNOW -X" in wizard._snow_summary.text()
    wizard._snow_unbalanced.setChecked(False)
    assert wizard._snow_summary.text().startswith("Load case SNOW:")
    wizard._snow_ce.setValue(0.9)
    wizard._snow_ct.setValue(1.2)
    wizard._snow_is.setValue(1.1)
    wizard._snow_slippery.setChecked(True)
    assert chosen() == WarehouseSnow(
        method="asce7", ground=957.6, exposure=0.9, thermal=1.2, importance=1.1,
        slippery=True, unbalanced=False,
    )  # fmt: skip

    wizard._snow_method.setCurrentIndex(wizard._snow_method.findData("en1991"))
    assert chosen().ground == 1000.0  # sk = 1 kN/m²
    assert wizard._snow_ce.isEnabled() and not wizard._snow_is.isEnabled()
    wizard._snow_unbalanced.setChecked(True)
    assert "SNOW, SNOW +X, SNOW -X" in wizard._snow_summary.text()
    # The cases follow the roof: a single slope has the one arrangement.
    wizard._roof.setCurrentIndex(
        next(i for i, choice in enumerate(ROOF_CHOICES) if choice[1] is RoofType.MONO_PITCH)
    )
    assert wizard._snow_summary.text().startswith("Load case SNOW:")
    wizard._snow_ground.setValue(0.0)
    assert wizard._snow_summary.text() != "" and "<b>" not in wizard._snow_summary.text()
    wizard._snow_on.setChecked(False)
    assert wizard.loads().snow is None and wizard._snow_summary.text() == ""


@pytest.mark.gui
def test_the_menu_adds_the_ash_case_to_the_warehouse(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: pytest.fail(str(a[2])))

    def setup(wizard: WarehouseWizard) -> None:
        wizard._n_frames.setValue(3)
        wizard._wind_on.setChecked(False)
        wizard._code.setCurrentIndex(wizard._code.findData("nscm"))
        wizard._snow_on.setChecked(True)

    _accept(monkeypatch, setup)
    project = mw._vm.project
    before = project.model_dump()

    mw._act_warehouse_wizard.trigger()

    assert [c.name for c in project.analyses] == ["DEAD", "ROOF LIVE", "ASH"]
    patterns = {p.name: p for p in project.load_patterns}
    assert len(patterns["ASH"].element_loads) == len(patterns["ROOF LIVE"].element_loads)
    # NSCM 7.5.1: the ash has its own load, CCV.
    assert any("CCV" in c.name for c in project.combinations)
    assert "1 case(s) by Volcanic ash" in mw._console.toPlainText()
    project.validate_references()

    mw._vm.undo_stack.undo()
    assert project.model_dump() == before
