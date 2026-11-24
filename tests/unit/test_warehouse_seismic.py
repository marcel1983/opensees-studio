"""The warehouse's static earthquake: coefficient, seismic weight, forces, the plan."""

from __future__ import annotations

import math

import numpy as np
import pytest

from opensees_studio.core.default_materials import default_materials
from opensees_studio.core.defaults import ensure_dead_load_case
from opensees_studio.core.project import Project
from opensees_studio.core.self_weight import weight_per_length
from opensees_studio.core.units import UnitSystem
from opensees_studio.core.warehouse import (
    CODE_PRESETS,
    SEISMIC_METHODS,
    WarehouseError,
    WarehouseLoads,
    WarehouseSeismic,
    WarehouseSpec,
    WarehouseWind,
    build_warehouse,
    plan_warehouse,
    pressure_from_kpa,
    roof_weights,
    seismic_coefficient,
    seismic_loads,
)
from opensees_studio.core.wind import KGF

SECTIONS = {"column": 1, "rafter": 2, "purlin": 3, "girt": 4, "brace": 5, "end_column": 6}
SI = UnitSystem.SI_M_N
#: RNC-07 Art. 11 a: the reduced roof live load, 10 kg/m², in N/m².
CVR = 10.0 * KGF


def _spec(**fields):  # type: ignore[no-untyped-def]
    values = {
        "span": 20.0, "eave_height": 6.0, "frame_spacing": 6.0, "n_frames": 5, "slope": 0.1,
        "girt_spacing": 1.5, **fields,
    }  # fmt: skip
    return WarehouseSpec(**values)


def _project(units: UnitSystem = SI) -> Project:
    project = Project(ndm=3, ndf=6)
    project.meta.units = units
    project.materials.extend(default_materials(project.next_material_id(), units))
    ensure_dead_load_case(project)
    return project


def _steel_weight(project: Project) -> float:
    nodes = {n.id: np.asarray(n.coords) for n in project.nodes}
    return sum(
        weight_per_length(project, e) * float(np.linalg.norm(nodes[e.nodes[1]] - nodes[e.nodes[0]]))
        for e in project.elements
    )


# ───────────────────────────── the coefficient ─────────────────────────────
def test_rnc07_takes_the_plateau_of_art_32_and_its_minimum() -> None:
    # Zone C (a0 = 0.3 g), soil II (S = 1.5), Group B, regular. With Q = 2 the
    # reduced plateau S·2.7a0/(Q'Ω) = 0.304 is below the minimum S·a0 (Ec. 3).
    c, clause = seismic_coefficient(WarehouseSeismic())
    assert c == pytest.approx(1.5 * 0.3)
    assert clause.startswith("RNC-07") and "minimum" in clause
    # Q = 1 (elastic): the plateau governs, with the overstrength Ω = 2.
    c, clause = seismic_coefficient(WarehouseSeismic(reduction=1.0))
    assert c == pytest.approx(1.5 * 2.7 * 0.3 / (1.0 * 2.0))
    assert "minimum" not in clause
    # Group A: forces times 1.5 (Art. 20). Rock: S = 1.
    essential, _ = seismic_coefficient(WarehouseSeismic(reduction=1.0, importance_class="A"))
    assert essential == pytest.approx(1.5 * c)
    rock, _ = seismic_coefficient(WarehouseSeismic(reduction=1.0, soil="I"))
    assert rock == pytest.approx(2.7 * 0.3 / 2.0)
    # An irregular building reduces less: Q' = 0.9 Q.
    regular, _ = seismic_coefficient(WarehouseSeismic(reduction=1.25))
    irregular, _ = seismic_coefficient(WarehouseSeismic(reduction=1.25, regularity="irregular_one"))
    assert irregular == pytest.approx(regular / 0.9)


def test_nscm_takes_the_plateau_of_its_spectrum() -> None:
    from opensees_studio.core.nscm import NscmSite

    seismic = WarehouseSeismic(method="nscm", a0=0.36667, soil="C", importance_class="II")
    c, clause = seismic_coefficient(seismic)
    site = NscmSite(a0=0.36667, site_class="C", risk_category="II", r0=2.0)
    _tb, tc, _td = site.corner_periods()
    assert c == pytest.approx(site.seismic_coefficient(0.5 * tc)[0])  # anywhere on the plateau
    assert c == pytest.approx(0.572, abs=1e-3)
    assert clause.startswith("NSCM")
    # No category given: category II, the ordinary building.
    assert seismic_coefficient(WarehouseSeismic(method="nscm", a0=0.36667, soil="C"))[0] == c
    essential = WarehouseSeismic(method="nscm", a0=0.36667, soil="C", importance_class="IV")
    assert seismic_coefficient(essential)[0] > c


def test_asce7_takes_sds_over_r_over_ie() -> None:
    c, clause = seismic_coefficient(WarehouseSeismic(method="asce7", sds=1.0, reduction=3.0))
    assert c == pytest.approx(1.0 / 3.0)
    assert clause.startswith("ASCE 7-16") and "12.8-2" in clause
    c, _ = seismic_coefficient(
        WarehouseSeismic(method="asce7", sds=0.8, reduction=3.25, importance=1.5)
    )
    assert c == pytest.approx(0.8 * 1.5 / 3.25)


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"method": "eurocode"}, "Unknown seismic method"),
        ({"reduction": 0.0}, "reduction factor must be positive"),
        ({"roof_live": -1.0}, "positive, downward"),
        ({"directions": ()}, "at least one earthquake direction"),
        ({"directions": ("X", "Z")}, "Unknown earthquake direction"),
    ],
)
def test_seismic_settings_are_checked(fields: dict, message: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(WarehouseError, match=message):
        WarehouseSeismic(**fields)


@pytest.mark.parametrize(
    ("seismic", "message"),
    [
        (WarehouseSeismic(method="asce7", sds=0.0), "SDS must be positive"),
        (WarehouseSeismic(method="nscm", soil="C", importance_class="II", reduction=0.5), "Ro"),
        (WarehouseSeismic(soil="IV"), "site-specific"),
    ],
)
def test_what_the_code_refuses_is_a_warehouse_error(
    seismic: WarehouseSeismic, message: str
) -> None:
    with pytest.raises(WarehouseError, match=message):
        seismic_coefficient(seismic)


# ───────────────────────── the weight and the forces ─────────────────────────
def test_the_roof_weight_is_the_pressure_times_the_roof() -> None:
    warehouse = build_warehouse(_spec(), SECTIONS, first_node_id=1, first_element_id=1)
    length = 4 * 6.0
    on_slope = roof_weights(warehouse, 100.0, projected=False)
    assert sum(on_slope.values()) == pytest.approx(100.0 * 2 * math.hypot(10.0, 1.0) * length)
    on_plan = roof_weights(warehouse, 100.0, projected=True)
    assert sum(on_plan.values()) == pytest.approx(100.0 * 20.0 * length)
    # Half of each purlin's strip goes to each of its ends: all of it is on the frames.
    purlin_nodes = {
        n for e in warehouse.elements if e.id in warehouse.purlin_station for n in e.nodes
    }
    assert set(on_plan) == purlin_nodes
    assert roof_weights(warehouse, 0.0, projected=True) == {}


@pytest.mark.parametrize(("direction", "axis"), [("X", 0), ("Y", 1)])
def test_the_base_shear_is_shared_by_weight_and_height(direction: str, axis: int) -> None:
    warehouse = build_warehouse(
        _spec(origin=(5.0, -3.0, 2.0)), SECTIONS, first_node_id=1, first_element_id=1
    )
    heights = {n.id: n.coords[2] - 2.0 for n in warehouse.nodes}
    rng = np.random.default_rng(7)
    weights = {
        n: float(w) for n, w in zip(heights, rng.uniform(50.0, 500.0, len(heights)), strict=True)
    }
    loads = seismic_loads(warehouse, weights, 0.25, direction)
    by_node = {load.node_id: load.forces for load in loads}
    total = sum(weights.values())
    assert sum(f[axis] for f in by_node.values()) == pytest.approx(0.25 * total)
    for forces in by_node.values():
        assert [v for k, v in enumerate(forces) if k != axis] == [0.0] * 5
    # Nothing at the bases, and Fi / (Wi hi) is the same everywhere else.
    assert set(by_node) == {n for n, h in heights.items() if h > 0.0}
    ratios = [by_node[n][axis] / (weights[n] * heights[n]) for n in by_node]
    assert ratios == pytest.approx([ratios[0]] * len(ratios))
    moment = sum(weights[n] * heights[n] for n in heights)
    assert ratios[0] == pytest.approx(0.25 * total / moment)
    assert seismic_loads(warehouse, {}, 0.25, direction) == []


# ──────────────────────────────── the plan ────────────────────────────────
def test_the_plan_adds_one_case_per_direction_with_the_seismic_weight() -> None:
    project = _project()
    before = project.model_dump()
    loads = WarehouseLoads(
        code="rnc07", roof_dead=100.0, roof_live=98.0, seismic=WarehouseSeismic(roof_live=CVR)
    )
    plan = plan_warehouse(project, _spec(), loads=loads)
    assert project.model_dump() == before
    plan.apply(project)
    assert [c.name for c in project.analyses] == ["DEAD", "LIVE", "EQ X", "EQ Y"]
    # Steel, the roof dead load on the slope and the 10 kg/m² of Art. 11 a on plan.
    weight = _steel_weight(project) + 100.0 * 2 * math.hypot(10.0, 1.0) * 24.0 + CVR * 20.0 * 24.0
    patterns = {p.name: p for p in project.load_patterns}
    for name, axis in (("EQ X", 0), ("EQ Y", 1)):
        pattern = patterns[name]
        assert pattern.self_weight == 0.0 and not pattern.element_loads
        shear = sum(load.forces[axis] for load in pattern.nodal_loads)
        assert shear == pytest.approx(0.45 * weight, rel=1e-9)
        assert all(load.forces[1 - axis] == 0.0 for load in pattern.nodal_loads)
    note = next(n for n in plan.notes if "earthquake case(s)" in n)
    assert "RNC-07 Art. 32" in note and "c = 0.45" in note
    assert f"seismic weight {weight:.6g}" in note
    assert "period is not used" in note and "accidental torsion" in note

    # Art. 32 f: each direction with 30 % of the other, in every sign.
    names = [c.name for c in project.combinations]
    assert names[:2] == ["1.4CM", "1.2CM+1.6CV"]
    assert names[-1] == "RNC-07 ultimate envelope"
    with_e = names[2:-1]
    assert len(with_e) == 2 * 2 * 2 * 2  # two sets, two main directions, four signs
    for name in (
        "1.2CM+Fs:EQ X+0.3Fs:EQ Y+CV",
        "1.2CM-Fs:EQ X-0.3Fs:EQ Y+CV",
        "1.2CM+Fs:EQ Y-0.3Fs:EQ X+CV",
        "0.9CM-Fs:EQ Y+0.3Fs:EQ X",
    ):
        assert name in with_e, with_e
    Project.model_validate(project.model_dump())

    # A second warehouse beside the first gets its own earthquake case.
    again = plan_warehouse(
        project, WarehouseSpec(span=10.0, eave_height=4.0, frame_spacing=5.0, origin=(40.0, 0, 0)),
        loads=WarehouseLoads(seismic=WarehouseSeismic(directions=("Y",))),
    )  # fmt: skip
    assert [c.name for c in again.cases] == ["EQ Y (2)"]
    own = {n.id for n in again.warehouse.nodes}
    assert {load.node_id for _id, _field, loads_ in again.pattern_loads for load in loads_} <= own


def test_no_earthquake_no_earthquake_cases() -> None:
    plan = plan_warehouse(_project(), _spec(), loads=WarehouseLoads(roof_live=98.0))
    assert [c.name for c in plan.cases] == ["LIVE"]
    assert not any("earthquake" in note for note in plan.notes)


def test_nscm_combines_each_direction_with_30_percent_of_the_other() -> None:
    seismic = WarehouseSeismic(method="nscm", a0=0.36667, soil="C", importance_class="II")
    plan = plan_warehouse(
        _project(), _spec(), loads=WarehouseLoads(code="nscm", roof_live=500.0, seismic=seismic)
    )
    eq = {c.name: c.id for c in plan.cases if c.name.startswith("EQ")}
    assert set(eq) == {"EQ X", "EQ Y"}
    with_e = [
        c
        for c in plan.combinations
        if c.combination_type != "Envelope" and any(t.ref_id in eq.values() for t in c.terms)
    ]
    # (1.2 + Ev)CM + Eh and (0.9 - Ev)CM + Eh; two main directions, two signs each,
    # two of the other.
    assert len(with_e) == 2 * 2 * 2 * 2
    for combination in with_e:
        factors = sorted(abs(t.factor) for t in combination.terms if t.ref_id in eq.values())
        assert factors == [0.3, 1.0]
    # The vertical component of the site, Ev = 0.2 a0 Fas CM (Ec. 7.8-4), Fas = 1.3
    # for class C: in the dead load factor.
    ev = 0.2 * round(0.36667 * 1.3, 4)
    dead = {round(t.factor, 6) for c in with_e for t in c.terms if t.ref_id not in eq.values()}
    assert dead == {round(1.2 + ev, 6), round(0.9 - ev, 6)}
    assert "1.29534CM+Eh:EQ X-0.3Eh:EQ Y" in [c.name for c in with_e]

    # One direction only: nothing to combine it with.
    alone = WarehouseSeismic(
        method="nscm", a0=0.36667, soil="C", importance_class="II", directions=("X",)
    )
    plan = plan_warehouse(_project(), _spec(), loads=WarehouseLoads(code="nscm", seismic=alone))
    names = [c.name for c in plan.combinations]
    assert names == [
        "1.4CM",
        "1.29534CM+Eh",
        "1.29534CM-Eh",
        "0.80466CM+Eh",
        "0.80466CM-Eh",
        "NSCM LRFD envelope",
    ]

    # RNC-07 earthquake under the NSCM combinations: the generator's own Ev.
    plan = plan_warehouse(
        _project(),
        _spec(),
        loads=WarehouseLoads(code="nscm", seismic=WarehouseSeismic(directions=("X",))),
    )
    assert "1.3CM+Eh" in [c.name for c in plan.combinations]


@pytest.mark.parametrize(
    ("code", "expected", "per_case"),
    [
        ("asce7_lrfd", [], 4),  # named by case id: 1.2D ± E and 0.9D ± E
        ("asce7_asd", ["D+0.7E:EQ X", "D-0.525E:EQ Y", "0.6D-0.7E:EQ X"], 6),
    ],
)
def test_asce7_counts_no_roof_live_load_and_combines_both_signs(
    code: str, expected: list[str], per_case: int
) -> None:
    project = _project()
    preset = CODE_PRESETS[code]
    assert preset.seismic_method == "asce7" and preset.seismic_live_kpa == 0.0
    seismic = WarehouseSeismic(method="asce7", sds=1.0, reduction=preset.seismic_reduction)
    plan = plan_warehouse(
        project,
        _spec(),
        loads=WarehouseLoads(code=code, roof_dead=100.0, roof_live=500.0, seismic=seismic),
    )
    plan.apply(project)
    weight = _steel_weight(project) + 100.0 * 2 * math.hypot(10.0, 1.0) * 24.0
    pattern = next(p for p in project.load_patterns if p.name == "EQ X")
    assert sum(load.forces[0] for load in pattern.nodal_loads) == pytest.approx(weight / 3.0)
    eq = [c.id for c in plan.cases if c.name.startswith("EQ")]
    names = [c.name for c in plan.combinations]
    for name in expected:
        assert name in names, names
    for case_id in eq:
        terms = [
            t.factor
            for c in plan.combinations
            if c.combination_type != "Envelope"
            for t in c.terms
            if t.ref_id == case_id
        ]
        assert len(terms) == per_case
        assert sorted(terms) == pytest.approx(sorted(-f for f in terms))


def test_the_presets_carry_the_earthquake_of_their_code() -> None:
    assert {p.seismic_method for p in CODE_PRESETS.values()} <= set(SEISMIC_METHODS)
    # RNC-07 Art. 11 a: 10 kg/m² of the roof live load count for the earthquake.
    assert CODE_PRESETS["rnc07"].seismic_live_kpa == pytest.approx(10.0 * KGF / 1e3)
    # NSCM 9.6 b, warehouses: W = CM + 0.3 CV.
    assert CODE_PRESETS["nscm"].seismic_live_kpa == pytest.approx(
        0.3 * CODE_PRESETS["nscm"].roof_live_kpa
    )
    assert CODE_PRESETS["nscm"].seismic_method == "nscm"


def test_wind_and_earthquake_go_into_the_same_combinations_set() -> None:
    loads = WarehouseLoads(
        code="rnc07",
        roof_live=98.0,
        wind=WarehouseWind(directions=("+X",)),
        seismic=WarehouseSeismic(directions=("X",)),
    )
    plan = plan_warehouse(_project(), _spec(), loads=loads)
    assert [c.name for c in plan.cases] == ["LIVE", "WIND +X", "EQ X"]
    names = [c.name for c in plan.combinations]
    # The wind with its own sign only; the earthquake both ways.
    assert "0.9CM+1.6Pz" in names and "0.9CM-1.6Pz" not in names
    assert "0.9CM+Fs" in names and "0.9CM-Fs" in names


def test_the_weights_follow_the_project_units() -> None:
    si = plan_warehouse(
        _project(),
        _spec(),
        loads=WarehouseLoads(roof_dead=100.0, seismic=WarehouseSeismic(roof_live=CVR)),
    )
    kn = _project(UnitSystem.SI_M_KN)
    units = kn.meta.units
    other = plan_warehouse(
        kn,
        _spec(),
        loads=WarehouseLoads(
            roof_dead=pressure_from_kpa(0.1, units),
            seismic=WarehouseSeismic(roof_live=pressure_from_kpa(CVR / 1e3, units)),
        ),
    )

    def shear(plan) -> float:  # type: ignore[no-untyped-def]
        nodal = [loads for _id, field, loads in plan.pattern_loads if field == "nodal_loads"]
        assert len(nodal) == 2
        return sum(load.forces[0] for load in nodal[0])

    assert shear(other) == pytest.approx(shear(si) / 1e3, rel=1e-9)
