"""Reading and writing the SAP2000 text format (``.s2k`` / ``.$2k``).

The fixtures in ``tests/fixtures/s2k`` are hand-written from the table format:
a 2D portal in kN-m and a one-storey 3D frame in kip-in with a slab, releases,
a local-axis angle, partial and point loads, a scaled pattern and combinations.
Smaller cases are written inline, each the smallest file that shows one rule.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from opensees_studio.core import UnitSystem
from opensees_studio.core.analysis import StaticCase
from opensees_studio.core.combinations import CombinationTerm, LoadCombination
from opensees_studio.core.geometry.elements import ElasticBeamColumn, ShellMITC4Element
from opensees_studio.core.geometry.frame_options import EndRelease, FrameReleases
from opensees_studio.core.geometry.node import Node
from opensees_studio.core.loads import (
    LinearTimeSeries,
    NodalLoad,
    PlainLoadPattern,
    PointElementLoad,
    TrapezoidalElementLoad,
    UniformElementLoad,
)
from opensees_studio.core.project import Project, ProjectMeta
from opensees_studio.core.sections import (
    ElasticMembranePlateSection,
    ElasticSection,
    RectShape,
    WideFlangeShape,
)
from opensees_studio.services.sap2000_text import (
    S2kFile,
    Sap2000TextError,
    export_s2k,
    import_s2k,
    parse_tables,
    project_to_s2k,
    read_s2k,
    s2k_to_project,
    sap_local_axes,
    unit_scale,
    writer_angle,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "s2k"
PORTAL = FIXTURES / "portal_2d.s2k"
FRAME = FIXTURES / "frame_3d.s2k"


def _write(tmp_path: Path, body: str, name: str = "model.s2k") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


_CANTILEVER = """\
TABLE:  "PROGRAM CONTROL"
   ProgramName=SAP2000   CurrUnits="{units}"
TABLE:  "JOINT COORDINATES"
   Joint=A   CoordSys=GLOBAL   CoordType=Cartesian   XorR=0   Y=0   Z=0
   Joint=B   CoordSys=GLOBAL   CoordType=Cartesian   XorR={x}   Y=0   Z={z}
TABLE:  "JOINT RESTRAINT ASSIGNMENTS"
   Joint=A   U1=Yes   U2=Yes   U3=Yes   R1=Yes   R2=Yes   R3=Yes
TABLE:  "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"
   Material=M   UnitWeight=0   UnitMass=0   E1=200   G12=80   U12=0.25
TABLE:  "FRAME SECTION PROPERTIES 01 - GENERAL"
   SectionName=S   Material=M   Shape=General   t3=1   t2=1   Area=10   TorsConst=3   I33=50   I22=20   AS2=4   AS3=6
TABLE:  "CONNECTIVITY - FRAME"
   Frame=B1   JointI=A   JointJ=B
TABLE:  "FRAME SECTION ASSIGNMENTS"
   Frame=B1   AnalSect=S   MatProp=Default
{extra}END TABLE DATA
"""


def _cantilever(
    tmp_path: Path, *, units: str = "KN, m, C", x: float = 5, z: float = 0, extra: str = ""
) -> Path:
    return _write(tmp_path, _CANTILEVER.format(units=units, x=x, z=z, extra=extra))


# ──────────────────────────── the file ────────────────────────────
def test_tables_records_quotes_and_continuations() -> None:
    tables = parse_tables(
        'File x.s2k was saved on 1/1/26\n\nTABLE:  "PROGRAM CONTROL"\n'
        '   ProgramName=SAP2000   CurrUnits="KN, m, C"\n'
        'TABLE:  "LOAD PATTERN DEFINITIONS"\n'
        "   LoadPat=DEAD   DesignType=Dead _\n"
        "      SelfWtMult=1\n"
        '   LoadPat="WIND X"   SelfWtMult=0\n'
        "END TABLE DATA\n"
        'TABLE:  "AFTER THE END"\n   Key=1\n'
    )
    assert tables["PROGRAM CONTROL"] == [{"ProgramName": "SAP2000", "CurrUnits": "KN, m, C"}]
    assert tables["LOAD PATTERN DEFINITIONS"] == [
        {"LoadPat": "DEAD", "DesignType": "Dead", "SelfWtMult": "1"},
        {"LoadPat": "WIND X", "SelfWtMult": "0"},
    ]
    assert "AFTER THE END" not in tables


def test_unit_factors() -> None:
    kn_m = unit_scale("KN, m, C", UnitSystem.SI_M_N)
    assert (kn_m.length, kn_m.force) == (1.0, 1000.0)
    assert kn_m.stress == 1000.0
    kip_in = unit_scale("Kip, in, F", UnitSystem.US_IN_KIP)
    assert kip_in.is_identity
    n_mm = unit_scale("N, mm, C", UnitSystem.SI_M_N)
    assert n_mm.length == 1e-3 and n_mm.stress == pytest.approx(1e6)
    with pytest.raises(Sap2000TextError, match="Unknown units"):
        unit_scale("furlong, fortnight", UnitSystem.SI_M_N)


def test_missing_and_empty_files_are_refused(tmp_path: Path) -> None:
    with pytest.raises(Sap2000TextError, match="No such file"):
        read_s2k(tmp_path / "nope.s2k")
    with pytest.raises(Sap2000TextError, match="no SAP2000 table"):
        read_s2k(_write(tmp_path, "just some text\n"))


def test_a_broken_reference_is_named(tmp_path: Path) -> None:
    body = _CANTILEVER.format(units="KN, m, C", x=5, z=0, extra="").replace("JointJ=B", "JointJ=C")
    with pytest.raises(Sap2000TextError, match=r"Frame B1 .*: joint 'C' is not defined"):
        import_s2k(_write(tmp_path, body))


def test_an_error_names_the_table_and_the_line(tmp_path: Path) -> None:
    body = _CANTILEVER.format(units="KN, m, C", x=5, z=0, extra="").replace("JointJ=B", "JointJ=C")
    line = next(
        number for number, text in enumerate(body.splitlines(), start=1) if "JointJ=C" in text
    )
    with pytest.raises(
        Sap2000TextError, match=rf"CONNECTIVITY - FRAME, line {line}\): joint 'C' is not defined"
    ):
        import_s2k(_write(tmp_path, body))


def test_a_line_that_is_not_a_record_is_reported_not_fatal(tmp_path: Path) -> None:
    extra = '   this is not a record at all\n   LoadPat=DEAD   Note="an unbalanced quote\n'
    imported = import_s2k(_cantilever(tmp_path, extra=extra))
    assert len(imported.project.nodes) == 2  # the model around the bad lines still imports
    (note,) = [note for note in imported.notes if "not Key=Value records" in note]
    assert note.startswith("2 line(s)")
    assert "this is not a record at all" in note


def test_a_file_without_joints_is_refused(tmp_path: Path) -> None:
    body = (
        'TABLE:  "PROGRAM CONTROL"\n   ProgramName=SAP2000   CurrUnits="KN, m, C"\n'
        'TABLE:  "GRID LINES"\n   CoordSys=GLOBAL   AxisDir=X   GridID=A   XRYZCoord=0\n'
        "END TABLE DATA\n"
    )
    with pytest.raises(Sap2000TextError, match="has no joints"):
        import_s2k(_write(tmp_path, body))


# ──────────────────────────── local axes ────────────────────────────
def test_sap_local_axes_of_a_beam_a_column_and_a_turned_member() -> None:
    o = np.zeros(3)
    e1, e2, e3 = sap_local_axes(o, np.array([5.0, 0, 0]))
    np.testing.assert_allclose((e1, e2, e3), ([1, 0, 0], [0, 0, 1], [0, -1, 0]), atol=1e-12)
    _, e2, e3 = sap_local_axes(o, np.array([0, 0, 3.0]))
    np.testing.assert_allclose((e2, e3), ([1, 0, 0], [0, 1, 0]), atol=1e-12)
    _, e2, e3 = sap_local_axes(o, np.array([5.0, 0, 0]), angle=90)
    np.testing.assert_allclose((e2, e3), ([0, -1, 0], [0, 0, -1]), atol=1e-12)


def test_writer_angle_puts_local_2_on_opensees_z() -> None:
    o = np.zeros(3)
    assert writer_angle(3, o, np.array([5.0, 0, 0])) == 0.0
    assert writer_angle(3, o, np.array([0, 0, 3.0])) == 0.0
    # A steep brace in the Y-Z plane: OpenSees takes vecxz = X, a quarter turn from SAP2000.
    assert abs(writer_angle(3, o, np.array([0, 1.0, 3.0]))) == pytest.approx(90.0)
    # 2D: local 2 goes on OpenSees' in-plane y, half a turn for a beam drawn right to left.
    assert abs(writer_angle(2, np.array([5.0, 0, 0]), o)) == pytest.approx(180.0)


# ──────────────────────────── the 2D portal ────────────────────────────
def test_portal_is_a_2d_frame_scaled_to_newtons() -> None:
    imported = import_s2k(PORTAL)
    project = imported.project
    assert project.ndm == 2 and project.ndf == 3
    assert project.meta.units is UnitSystem.SI_M_N
    assert imported.scale.force == 1000.0
    assert [n.coords for n in project.nodes] == [(0, 0, 0), (0, 0, 4), (6, 0, 4), (6, 0, 0)]
    assert project.nodes[0].restraint == (True, False, True, False, True, False)
    assert not any(project.nodes[1].restraint)

    (section,) = project.sections
    assert isinstance(section, ElasticSection)
    # In-plane bending is about SAP2000's local 3: I33 becomes Iz.
    assert section.Iz == pytest.approx(0.003125)
    assert pytest.approx(3e10) == section.E
    assert section.unit_weight == pytest.approx(24000.0)
    assert section.shape == RectShape(d=0.5, b=0.3)
    assert section.As2 is None  # AS2 = 0: no shear deformation
    beam = project.elements[1]
    assert isinstance(beam, ElasticBeamColumn)
    assert beam.rho == pytest.approx(2447.3 * 0.15)


def test_portal_loads_cases_and_combinations() -> None:
    imported = import_s2k(PORTAL)
    project = imported.project
    dead, live, wind = project.load_patterns
    assert dead.self_weight == 1.0
    # Gravity on a beam drawn left to right is along -y (its local y is up).
    assert live.element_loads == [UniformElementLoad(element_id=2, wy=-10000.0)]
    assert wind.nodal_loads == [NodalLoad(node_id=2, forces=(20000.0, 0, 0, 0, 0, 0))]
    assert [c.name for c in project.analyses] == ["DEAD", "LIVE", "WIND"]
    uls, env = project.combinations
    assert uls.terms == [
        CombinationTerm(ref_id=1, factor=1.2),
        CombinationTerm(ref_id=2, factor=1.6),
    ]
    assert env.combination_type == "Envelope"
    assert env.terms[0] == CombinationTerm(source="combination", ref_id=1)
    # What did not come across is reported, never silently dropped.
    assert imported.dropped["LinModal load case"] == 1
    assert imported.unsupported_tables == {"JOINT ADDED MASS ASSIGNMENTS": 1}
    assert "Tables not read: JOINT ADDED MASS ASSIGNMENTS (1)" in imported.summary()
    grid = project.coord_systems[0].grid
    assert [(g.id, g.ordinate) for g in grid.x_grid_lines] == [("A", 0.0), ("B", 6.0)]


# ──────────────────────────── the 3D frame ────────────────────────────
def _section(project: Project, element_id: int) -> ElasticSection:
    element = next(e for e in project.elements if e.id == element_id)
    section = next(s for s in project.sections if s.id == element.section_id)
    assert isinstance(section, ElasticSection)
    return section


def test_3d_sections_follow_the_local_axes() -> None:
    project = import_s2k(FRAME).project
    assert project.ndm == 3 and project.meta.units is UnitSystem.US_IN_KIP
    column = _section(project, 1)
    # A column's SAP2000 local 2 is OpenSees' z: I33 is Iy, AS2 is As3.
    assert (column.Iy, column.Iz, column.As3, column.As2) == (999.0, 362.0, 6.16, 17.16)
    assert column.shape == WideFlangeShape(d=14, bf=14.5, tw=0.44, tf=0.71)
    turned = _section(project, 2)  # local-axis angle 90: local 2 lies on OpenSees' y
    assert (turned.Iz, turned.Iy) == (999.0, 362.0)
    assert turned.name == "W14X90 (axes 2-3)" and turned.shape is None
    beam = _section(project, 5)
    assert beam.Iy == pytest.approx(510 * 1.5)  # I3Mod
    tube = _section(project, 9)  # Box/Tube with dimensions only: closed-form properties
    assert pytest.approx(6 * 6 - 5.5 * 5.5) == tube.A
    assert tube.As2 is None  # its releases make it an Euler-Bernoulli member


def test_3d_releases_map_sap2000_m3_onto_bending_about_local_y() -> None:
    project = import_s2k(FRAME).project
    beam = next(e for e in project.elements if e.id == 6)
    assert isinstance(beam, ElasticBeamColumn)
    assert beam.releases.i.released == ("M2",) and beam.releases.j.released == ("M2",)
    brace = next(e for e in project.elements if e.id == 9)
    assert isinstance(brace, ElasticBeamColumn)
    assert brace.releases.i == EndRelease(released=("T", "M2", "M3"), springs={"M2": 5000.0})
    assert _section(project, 6).name == "W18X35 (no shear)"


def test_3d_loads_cases_and_shells() -> None:
    imported = import_s2k(FRAME)
    project = imported.project
    live = next(p for p in project.load_patterns if p.name == "LIVE")
    assert live.element_loads == [UniformElementLoad(element_id=5, wz=-0.1)]
    assert live.point_loads == [PointElementLoad(element_id=6, pz=-12.0, x=0.5)]
    assert live.distributed_loads == [
        TrapezoidalElementLoad(element_id=7, x_start=0.25, x_end=0.75, wz_start=-0.05, wz_end=-0.15)
    ]
    # GRAV = DEAD + 0.5 LIVE: the scaled pattern becomes one of its own.
    grav = next(c for c in project.analyses if c.name == "GRAV")
    assert isinstance(grav, StaticCase)
    half = next(p for p in project.load_patterns if p.id == grav.pattern_ids[1])
    assert half.name == "LIVE x 0.5" and half.point_loads[0].pz == -6.0
    (shell,) = [e for e in project.elements if isinstance(e, ShellMITC4Element)]
    assert shell.id == 10 and shell.nodes == (5, 6, 7, 8)
    slab = next(s for s in project.sections if s.id == shell.section_id)
    assert isinstance(slab, ElasticMembranePlateSection)
    assert (slab.h, slab.nu, slab.E) == (6.0, 0.2, 3605.0)
    c2 = next(c for c in project.combinations if c.name == "C2")
    assert c2.combination_type == "AbsoluteAdd"
    assert imported.dropped["Range Add combination"] == 1
    assert imported.dropped["automatic ASCE 7-16 load"] == 1
    assert imported.dropped["distributed moment load"] == 1


def test_names_that_are_not_integers_are_numbered(tmp_path: Path) -> None:
    imported = import_s2k(_cantilever(tmp_path))
    assert [n.id for n in imported.project.nodes] == [1, 2]
    assert imported.project.elements[0].id == 1
    assert any("numbered 1" in note for note in imported.notes)


def test_projected_and_local_loads(tmp_path: Path) -> None:
    extra = (
        'TABLE:  "LOAD PATTERN DEFINITIONS"\n   LoadPat=L   SelfWtMult=0\n'
        'TABLE:  "FRAME LOADS - DISTRIBUTED"\n'
        '   Frame=B1   LoadPat=L   CoordSys=GLOBAL   Type=Force   Dir="Gravity Projected"   '
        "RelDistA=0   RelDistB=1   FOverLA=2   FOverLB=2\n"
    )
    imported = import_s2k(_cantilever(tmp_path, x=3, z=4, extra=extra))
    (load,) = imported.project.load_patterns[0].element_loads
    # A 3-4-5 slope: 2 per horizontal metre is 2·3/5 per metre of member, pointing down.
    total = np.hypot(np.hypot(load.wx, load.wy), load.wz)
    assert total == pytest.approx(2000 * 3 / 5)


# ──────────────────────────── writing ────────────────────────────
def _totals(project: Project) -> dict[tuple[str, int], np.ndarray]:
    """Per pattern name and element, every frame load summed (distribution kept apart)."""
    out: dict[tuple[str, int], np.ndarray] = {}
    for pattern in project.load_patterns:
        for u in pattern.element_loads:
            key = (pattern.name, u.element_id)
            out[key] = out.get(key, np.zeros(9)) + np.array([u.wx, u.wy, u.wz, 0, 0, 0, 0, 0, 0])
        for d in pattern.distributed_loads:
            key = (pattern.name, d.element_id)
            out[key] = out.get(key, np.zeros(9)) + np.array(
                [0, 0, 0, *d.start(), d.x_start, d.x_end, 0]
            )
        for p in pattern.point_loads:
            key = (pattern.name, p.element_id)
            out[key] = out.get(key, np.zeros(9)) + np.array([0, 0, 0, p.px, p.py, p.pz, 0, 0, p.x])
    return out


def _assert_same_model(a: Project, b: Project) -> None:
    assert (a.ndm, a.meta.units) == (b.ndm, b.meta.units)
    assert [(n.id, n.coords, n.restraint) for n in a.nodes] == [
        (n.id, n.coords, n.restraint) for n in b.nodes
    ]
    assert len(a.elements) == len(b.elements)
    for ea, eb in zip(a.elements, b.elements, strict=True):
        assert (ea.id, ea.nodes, type(ea)) == (eb.id, eb.nodes, type(eb))
        sa = next(s for s in a.sections if s.id == ea.section_id)
        sb = next(s for s in b.sections if s.id == eb.section_id)
        fields = ("E", "A", "Iz", "Iy", "J", "G", "As2", "As3", "unit_weight", "h", "nu", "rho")
        for name in fields:
            va, vb = getattr(sa, name, None), getattr(sb, name, None)
            if isinstance(va, float) and isinstance(vb, float):
                assert va == pytest.approx(vb, rel=1e-12), (ea.id, name)
            else:
                assert va == vb, (ea.id, name)
        if isinstance(ea, ElasticBeamColumn):
            assert isinstance(eb, ElasticBeamColumn)
            assert ea.releases == eb.releases
            assert ea.rho == pytest.approx(eb.rho, rel=1e-12)
    assert [(p.name, p.self_weight, p.nodal_loads) for p in a.load_patterns] == [
        (p.name, p.self_weight, p.nodal_loads) for p in b.load_patterns
    ]
    ta, tb = _totals(a), _totals(b)
    assert ta.keys() == tb.keys()
    for key in ta:
        np.testing.assert_allclose(ta[key], tb[key], rtol=1e-12, atol=1e-15)
    assert [(c.name, c.pattern_ids) for c in a.analyses] == [
        (c.name, c.pattern_ids) for c in b.analyses
    ]
    assert [(c.name, c.combination_type, c.terms) for c in a.combinations] == [
        (c.name, c.combination_type, c.terms) for c in b.combinations
    ]


@pytest.mark.parametrize("fixture", [PORTAL, FRAME], ids=["portal_2d", "frame_3d"])
def test_round_trip_keeps_what_the_import_reads(tmp_path: Path, fixture: Path) -> None:
    first = import_s2k(fixture).project
    report = export_s2k(first, tmp_path / "again.s2k")
    assert not report.skipped
    again = import_s2k(tmp_path / "again.s2k")
    assert not again.dropped and not again.unsupported_tables
    _assert_same_model(first, again.project)


@pytest.mark.parametrize("fixture", [PORTAL, FRAME], ids=["portal_2d", "frame_3d"])
def test_exporting_again_writes_the_same_text(tmp_path: Path, fixture: Path) -> None:
    once = export_s2k(import_s2k(fixture).project, tmp_path / "once.s2k")
    assert once.path is not None
    twice = export_s2k(import_s2k(once.path).project, tmp_path / "twice.s2k")
    assert twice.path is not None
    assert once.path.read_text(encoding="utf-8") == twice.path.read_text(encoding="utf-8")


def _built_project() -> Project:
    """A 3D project made in the application: a sloped brace, loads in local axes."""
    section = ElasticSection(
        id=1,
        name="Box",
        E=2e11,
        A=0.01,
        Iz=2e-5,
        Iy=5e-5,
        G=8e10,
        J=3e-5,
        unit_weight=77000.0,
    )
    return Project(
        meta=ProjectMeta(name="built", units=UnitSystem.SI_M_N),
        nodes=[
            Node(id=1, coords=(0, 0, 0), restraint=(True,) * 6),
            Node(id=2, coords=(0, 1, 3)),
            Node(id=3, coords=(4, 1, 3)),
        ],
        sections=[section],
        elements=[
            ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1, rho=78.5),
            ElasticBeamColumn(
                id=2,
                nodes=(2, 3),
                section_id=1,
                releases=FrameReleases(j=EndRelease(released=("M2", "M3"))),
            ),
        ],
        time_series=[LinearTimeSeries(id=1)],
        load_patterns=[
            PlainLoadPattern(
                id=1,
                name="Q",
                time_series_id=1,
                element_loads=[UniformElementLoad(element_id=1, wy=1.5, wz=-2.0, wx=0.25)],
                point_loads=[PointElementLoad(element_id=2, py=3.0, pz=-4.0, x=0.3)],
            )
        ],
        analyses=[StaticCase(id=1, name="Q", pattern_ids=[1])],
        combinations=[
            LoadCombination(id=1, name="1.5Q", terms=[CombinationTerm(ref_id=1, factor=1.5)])
        ],
    )


def test_a_project_made_here_survives_the_trip() -> None:
    project = _built_project()
    text, report = project_to_s2k(project)
    assert "FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL" in text  # the steep brace is turned
    assert not report.skipped
    again = s2k_to_project(S2kFile(path=Path("built.s2k"), tables=parse_tables(text))).project
    _assert_same_model(project, again)


def test_the_export_reports_what_it_leaves_out() -> None:
    project = _built_project()
    project.nodes[1].mass = (1.0, 1.0, 1.0, 0, 0, 0)
    project.analyses.append(StaticCase(id=2, name="push", pattern_ids=[1], n_steps=10))
    _, report = project_to_s2k(project)
    assert report.skipped["joint mass"] == 1
    assert report.skipped["Static analysis case"] == 1
    assert "Not written" in report.summary()


def test_area_modifier_leaves_mass_and_weight_alone(tmp_path: Path) -> None:
    body = (
        _CANTILEVER.format(units="KN, m, C", x=5, z=0, extra="")
        .replace("UnitWeight=0   UnitMass=0", "UnitWeight=78   UnitMass=7.8")
        .replace("Shape=General", "Shape=Channel   AMod=2")
    )
    imported = import_s2k(_write(tmp_path, body))
    section = imported.project.sections[0]
    member = imported.project.elements[0]
    assert isinstance(section, ElasticSection) and isinstance(member, ElasticBeamColumn)
    assert section.A == 20.0
    assert section.unit_weight * section.A == pytest.approx(78_000 * 10.0)
    assert member.rho == pytest.approx(7_800 * 10.0)
    # A shape this reader cannot draw keeps its properties, and says so once.
    assert imported.dropped["'Channel' section geometry (kept its properties)"] == 1


def test_a_load_in_a_user_coordinate_system_is_reported_not_guessed(tmp_path: Path) -> None:
    extra = (
        'TABLE:  "LOAD PATTERN DEFINITIONS"\n   LoadPat=L   SelfWtMult=0\n'
        'TABLE:  "FRAME LOADS - POINT"\n'
        "   Frame=B1   LoadPat=L   CoordSys=CSYS1   Type=Force   Dir=X   RelDist=0.5   Force=3\n"
    )
    imported = import_s2k(_cantilever(tmp_path, extra=extra))
    assert imported.project.load_patterns[0].point_loads == []
    assert imported.dropped["point load in another coordinate system"] == 1


# ──────────────────────────── damaged files ────────────────────────────
@pytest.mark.parametrize("count", ["1000000000", "1E300", "2.7", "0", "3", "5"])
def test_an_area_needs_exactly_four_joints(tmp_path: Path, count: str) -> None:
    """A bad NumJoints is a dropped area, not a billion-iteration loop or a truncation."""
    body = FRAME.read_text(encoding="utf-8").replace("NumJoints=4", f"NumJoints={count}")
    imported = import_s2k(_write(tmp_path, body))
    assert imported.dropped["area with other than four joints"] == 1
    assert not [e for e in imported.project.elements if isinstance(e, ShellMITC4Element)]


@pytest.mark.parametrize(
    "name", ["9" * 5000, "²"], ids=["thousands-of-digits", "digit-int-refuses"]
)
def test_a_name_that_cannot_be_an_integer_is_numbered(tmp_path: Path, name: str) -> None:
    """``isdigit`` is not an int guarantee: CPython refuses 4 300+ digits and ``²``."""
    body = _CANTILEVER.format(units="KN, m, C", x=5, z=0, extra="")
    for old, new in (("A", f"{name}A"), ("B", f"{name}B")):
        body = (
            body.replace(f"Joint={old} ", f"Joint={new} ")
            .replace(f"JointI={old}", f"JointI={new}")
            .replace(f"JointJ={old}", f"JointJ={new}")
        )
    imported = import_s2k(_write(tmp_path, body))
    assert [n.id for n in imported.project.nodes] == [1, 2]
    assert any("numbered 1" in note for note in imported.notes)


def _imports_or_says_why(tmp_path: Path, text: str) -> None:
    try:
        import_s2k(_write(tmp_path, text))
    except Sap2000TextError:
        return


@pytest.mark.parametrize("fixture", [PORTAL, FRAME], ids=["portal_2d", "frame_3d"])
def test_a_damaged_file_only_ever_raises_a_message(tmp_path: Path, fixture: Path) -> None:
    """Truncated and mutated files reach the caller as Sap2000TextError, never as a crash."""
    text = fixture.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for cut in range(len(lines) + 1):
        _imports_or_says_why(tmp_path, "".join(lines[:cut]))
    rng = random.Random(20261024)
    for _ in range(80):
        body = list(text)
        for _ in range(3):
            body[rng.randrange(len(body))] = rng.choice('=" _\n\t0123456789xyz')
        _imports_or_says_why(tmp_path, "".join(body))
