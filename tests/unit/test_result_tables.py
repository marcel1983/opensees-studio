"""Result tables: unit-named headers and a CSV that reads back the exact result values."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    ElasticUniaxial,
    Node,
    Project,
    TrussElement,
)
from opensees_studio.core.project import ProjectMeta
from opensees_studio.core.units import UnitSystem
from opensees_studio.services.result_tables import (
    display_text,
    modal_tables,
    pushover_tables,
    static_tables,
    write_csv,
)
from opensees_studio.services.results import ModalResults, PushoverResults, StaticResults

# Values a six-digit display cannot tell apart, and a few that need all 17 digits.
AWKWARD = [0.1 + 0.2, 1e-10, 1.0 / 3.0, -2.0322856141383964e-06, 123456789.01234567, 0.0]


def _project() -> Project:
    return Project(
        ndm=2,
        ndf=3,
        meta=ProjectMeta(units=UnitSystem.US_IN_KIP),
        nodes=[Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(1, 0, 0))],
        materials=[ElasticUniaxial(id=1, E=29000.0)],
        sections=[ElasticSection(id=1, E=29000.0, A=1.0, Iz=1.0)],
        elements=[
            ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1),
            TrussElement(id=2, nodes=(1, 2), area=1.0, material_id=1),
        ],
    )


def _static() -> StaticResults:
    rng = np.random.default_rng(7)
    return StaticResults(
        case_id=1,
        case_name="gravity",
        n_steps=2,
        node_disp={1: rng.normal(size=(2, 3)), 2: np.array([[0.0] * 3, AWKWARD[:3]])},
        node_reaction={1: np.array([[0.0] * 3, AWKWARD[3:]]), 2: rng.normal(size=(2, 3))},
        element_forces={1: rng.normal(size=(2, 6)), 2: rng.normal(size=(2, 6)) * 1e-9},
    )


def _read(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def test_static_headers_name_the_units() -> None:
    disp, reactions, forces = static_tables(_static(), _project())
    assert disp.columns == ["Node", "U1 [in]", "U2 [in]", "R3 [rad]"]
    assert reactions.columns == ["Node", "F1 [kip]", "F2 [kip]", "M3 [kip·in]"]
    assert forces.columns == ["Element", "Type", "Component", "Unit", "Value"]
    frame = [row for row in forces.rows if row[0] == 1]
    assert [(r[2], r[3]) for r in frame] == [
        ("N i", "kip"),
        ("V i", "kip"),
        ("M i", "kip·in"),
        ("N j", "kip"),
        ("V j", "kip"),
        ("M j", "kip·in"),
    ]
    truss = [row for row in forces.rows if row[0] == 2]
    assert truss[0][1] == "TrussElement"
    assert [r[2] for r in truss[:3]] == ["node 1 DOF 1", "node 1 DOF 2", "node 1 DOF 3"]
    assert [r[3] for r in truss[:3]] == ["kip", "kip", "kip·in"]


def test_static_csv_reads_back_the_result_object_exactly(tmp_path: Path) -> None:
    results = _static()
    disp, reactions, forces = static_tables(results, _project())

    header, rows = _read(write_csv(disp, tmp_path / "disp.csv"))
    assert header == disp.columns
    for row in rows:
        values = np.array([float(v) for v in row[1:]])
        assert np.array_equal(values, results.node_disp[int(row[0])][-1])

    _header, rows = _read(write_csv(reactions, tmp_path / "reactions.csv"))
    for row in rows:
        values = np.array([float(v) for v in row[1:]])
        assert np.array_equal(values, results.node_reaction[int(row[0])][-1])
    assert [float(v) for v in rows[0][1:]] == AWKWARD[3:]

    _header, rows = _read(write_csv(forces, tmp_path / "forces.csv"))
    for eid, recorded in results.element_forces.items():
        exported = [float(r[4]) for r in rows if int(r[0]) == eid]
        assert np.array_equal(exported, recorded[-1])


def test_display_rounds_and_export_does_not(tmp_path: Path) -> None:
    value = 0.1 + 0.2
    assert display_text(value, 6) == "0.3"
    assert display_text(value, 15) == "0.3"
    assert display_text(value, 17) == "0.30000000000000004"
    assert display_text(12, 3) == "12"
    disp = static_tables(_static(), _project())[0]
    text = write_csv(disp, tmp_path / "d.csv").read_text(encoding="utf-8")
    assert "0.30000000000000004" in text


def test_pushover_curve_and_modal_tables(tmp_path: Path) -> None:
    pushover = PushoverResults(
        case_id=3,
        case_name="push",
        n_steps=2,
        control_node=2,
        control_dof=1,
        control_disp=np.array([0.0, 0.1, 0.2 + 1e-17]),
        base_shear=np.array([0.0, AWKWARD[0], AWKWARD[2]]),
        node_disp={2: np.zeros((3, 3))},
    )
    curve = pushover_tables(pushover, _project())[0]
    assert curve.columns == ["Step", "Control U1 [in]", "Base shear [kip]"]
    _header, rows = _read(write_csv(curve, tmp_path / "curve.csv"))
    assert [float(r[2]) for r in rows] == list(pushover.base_shear)

    modal = ModalResults(case_id=4, case_name="modes", eigenvalues=np.array([AWKWARD[2], 4.0]))
    table = modal_tables(modal)[0]
    assert table.columns[1:] == ["Eigenvalue [rad²/s²]", "ω [rad/s]", "f [Hz]", "T [s]"]
    _header, rows = _read(write_csv(table, tmp_path / "modal.csv"))
    assert float(rows[0][1]) == AWKWARD[2]
    assert float(rows[1][4]) == float(modal.periods[1])
