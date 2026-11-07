"""The member calculation memory: HTML/Markdown, English/Spanish."""

from __future__ import annotations

import pytest

from opensees_studio.core import Project
from opensees_studio.core.design.calc import CalcStep, LimitStateCheck
from opensees_studio.core.project import ProjectMeta, Revision
from opensees_studio.services.calc_memory import build_member_memory, odt_bytes
from opensees_studio.services.steel_design import DesignReport, MemberResult


def _report() -> DesignReport:
    member = MemberResult(
        element_id=7,
        shape="W18X50",
        status="OK",
        ratio=0.62,
        check="Major flexure",
        equation="F2-2 inelastic LTB",
        load_set="Combination 1.2D+1.6L",
        station=0.5,
        checks=[
            LimitStateCheck(
                "Major flexure",
                "F2-2 inelastic LTB",
                demand=2000.0,
                capacity=3200.0,
                ratio=0.625,
                steps=(
                    CalcStep("Lp", "Lp = 1.76 ry sqrt(E/Fy)", "77.4", 77.4),
                    CalcStep("Mn", "Mn = Cb [...]", "Cb=1.14", 3200.0),
                ),
            )
        ],
        notes=["Bent about the shape's major axis."],
    )
    return DesignReport(members=[member], load_sets=["Combination 1.2D+1.6L"])


def _project() -> Project:
    project = Project()
    project.meta = ProjectMeta(
        name="Steel tower",
        author="A. Engineer",
        company="ACME",
        date="2026-11-05",
        revisions=[Revision(code="A", date="2026-11-01", by="AE", description="Issued")],
    )
    return project


def test_the_english_html_has_the_cover_index_member_and_steps() -> None:
    page = build_member_memory(_project(), _report(), language="en", fmt="html")
    assert "Calculation Memory" in page
    assert "Steel tower" in page and "ACME" in page
    assert "Index" in page and "W18X50" in page
    assert "Geometric properties" in page and "3200" in page
    assert "Lp = 1.76 ry sqrt(E/Fy)" in page
    assert "F2-2 inelastic LTB" in page


def test_the_spanish_markdown_translates_the_labels() -> None:
    page = build_member_memory(_project(), _report(), language="es", fmt="markdown")
    assert "Memoria de cálculo" in page
    assert "Índice" in page
    assert "Estados límite" in page
    assert "Sustitución" in page
    assert "| 7 | W18X50 | 0.62 | OK |" in page


def test_unknown_language_or_format_is_refused() -> None:
    with pytest.raises(ValueError, match="language"):
        build_member_memory(_project(), _report(), language="fr")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="format"):
        build_member_memory(_project(), _report(), fmt="pdf")  # type: ignore[arg-type]


def test_latex_and_odt_are_generated() -> None:
    latex = build_member_memory(_project(), _report(), language="en", fmt="latex")
    assert r"\documentclass" in latex
    assert r"\section*{Steel tower}" in latex
    assert "F2-2 inelastic LTB" in latex
    odt = odt_bytes(_project(), _report(), language="es")
    assert odt.startswith(b"PK")
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(odt)) as package:
        names = set(package.namelist())
        assert {"mimetype", "content.xml", "styles.xml", "META-INF/manifest.xml"} <= names
        assert package.read("mimetype").decode() == "application/vnd.oasis.opendocument.text"
        assert "Memoria de cálculo" in package.read("content.xml").decode()


def test_the_memory_carries_the_joint_checks() -> None:
    from opensees_studio.services.steel_design import JointResult

    report = _report()
    report.joints = [
        JointResult(
            node_id=3,
            ratio=1.25,
            status="OK",
            panel_ratio=0.8,
            panel_status="OK",
            load_set="Combination 1.2D+1.0E",
        )
    ]
    english = build_member_memory(_project(), report, language="en", fmt="html")
    assert "Joints (AISC 341-22)" in english
    assert "1.25" in english and "0.8" in english
    spanish = build_member_memory(_project(), report, language="es", fmt="markdown")
    assert "Juntas (AISC 341-22)" in spanish


def test_the_memory_carries_the_rbs_connections() -> None:
    from opensees_studio.services.steel_design import ConnectionResult

    report = _report()
    report.connections = [
        ConnectionResult(
            connection_id=1,
            beam_element_id=2,
            column_element_id=1,
            shape="W18X50",
            a=4.5,
            b=13.0,
            c=1.0,
            sh=11.0,
            z_rbs=80.0,
            mpr=5000.0,
            protected_from=0.0,
            protected_to=17.5,
            status="checked",
        )
    ]
    english = build_member_memory(_project(), report, language="en", fmt="html")
    assert "Connections (AISC 358-22)" in english
    assert "17.5" in english
    spanish = build_member_memory(_project(), report, language="es", fmt="markdown")
    assert "Conexiones (AISC 358-22)" in spanish


def test_the_memory_carries_the_scbf_protected_zones() -> None:
    from opensees_studio.services.steel_design import ProtectedZone

    report = _report()
    report.protected_zones = [
        ProtectedZone(
            element_id=5,
            ranges=((0.0, 0.1), (0.375, 0.625), (0.9, 1.0)),
            zone_clear=False,
            notes=["Node 98 lies inside the protected zone."],
        )
    ]
    english = build_member_memory(_project(), report, language="en", fmt="html")
    assert "SCBF protected zones" in english and "node inside" in english
    spanish = build_member_memory(_project(), report, language="es", fmt="markdown")
    assert "Zonas protegidas SCBF" in spanish


def test_the_memory_carries_the_scbf_gussets() -> None:
    from opensees_studio.services.steel_design import GussetResult

    report = _report()
    report.gussets = [
        GussetResult(
            gusset_id=1,
            brace_element_id=5,
            shape="W18X50",
            t=0.5,
            b=12.0,
            lw=10.0,
            free_length=10.0,
            demand=800.0,
            tension_demand=800.0,
            compression_demand=200.0,
            flexure_demand=3000.0,
            weld_leg=0.5,
            weld_required_leg=0.37,
            weld_ratio=0.74,
            weld_status="OK",
            ratio=0.75,
            status="OK",
        )
    ]
    english = build_member_memory(_project(), report, language="en", fmt="html")
    assert "SCBF gusset plates" in english and "W18X50" in english
    assert "SCBF brace connections" in english and "Weld status" in english
    spanish = build_member_memory(_project(), report, language="es", fmt="markdown")
    assert "Planchas de unión SCBF" in spanish
    assert "Conexiones de arriostramiento SCBF" in spanish


def test_the_memory_carries_the_scbf_capacity_design() -> None:
    from opensees_studio.services.steel_design import CapacityDesign

    report = _report()
    report.capacity_design = [
        CapacityDesign(
            load_set="Case EQ",
            brace_element_id=5,
            shape="W18X50",
            state="tension",
            analysis_force=100.0,
            expected_force=800.0,
            factor=8.0,
        )
    ]
    english = build_member_memory(_project(), report, language="en", fmt="html")
    assert "SCBF capacity design" in english and "Case EQ" in english
    spanish = build_member_memory(_project(), report, language="es", fmt="markdown")
    assert "Diseño por capacidad SCBF" in spanish
