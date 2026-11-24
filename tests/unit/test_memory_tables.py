"""The design check tables of the calculation memory: declared once, rendered four ways."""

from __future__ import annotations

import io
import zipfile

import pytest

from opensees_studio.core import Project
from opensees_studio.services import memory_tables
from opensees_studio.services.calc_memory import _LABELS, build_member_memory, odt_bytes
from opensees_studio.services.memory_tables import (
    MEMORY_SECTIONS,
    Raw,
    Table,
    fmt,
)
from opensees_studio.services.memory_tables import (
    memory_tables as tables_of,
)
from opensees_studio.services.steel_design import DesignReport


def _every_label_key() -> set[str]:
    """Every label a heading or a column of the registry names, read from the source."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(memory_tables))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            first, second = node.elts
            if (
                isinstance(first, ast.Constant)
                and first.value == "label"
                and isinstance(second, ast.Constant)
            ):
                keys.add(second.value)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_section":
            assert isinstance(node.args[0], ast.Constant)
            keys.add(node.args[0].value)
            if isinstance(node.args[2], ast.Tuple):
                keys.update(e.value for e in node.args[2].elts if isinstance(e, ast.Constant))
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in ("columns", "step_columns") for t in node.targets
        ):
            keys.update(
                e.value for e in getattr(node.value, "elts", []) if isinstance(e, ast.Constant)
            )
    return keys


@pytest.mark.parametrize("language", ["en", "es"])
def test_every_label_the_tables_name_is_in_both_languages(language: str) -> None:
    missing = sorted(_every_label_key() - set(_LABELS[language]))  # type: ignore[index]
    assert missing == []


def test_the_sections_print_in_a_fixed_order_and_an_empty_report_prints_none() -> None:
    assert [key for key, _ in MEMORY_SECTIONS][:2] == ["aisc341_joints", "aisc358_rbs"]
    assert len({key for key, _ in MEMORY_SECTIONS}) == len(MEMORY_SECTIONS)
    assert tables_of(DesignReport()) == []


def test_numbers_keep_four_significant_digits() -> None:
    assert [fmt(v) for v in (0.0, 1234.5678, 2e-4, 3.5e6)] == [
        "0",
        "1235",
        "2.0000e-04",
        "3.5000e+06",
    ]


def test_a_new_section_shows_in_every_format(monkeypatch: pytest.MonkeyPatch) -> None:
    table = Table(
        heading=(("label", "chapter_j"), ("plain", " 9 - "), ("text", "a & b")),
        columns=("check", Raw("k_x")),
        rows=[["1", "2 & 3"]],
        odt_name="Extra",
    )
    monkeypatch.setattr(memory_tables, "MEMORY_SECTIONS", [("extra", lambda _report: [table])])
    project, report = Project(), DesignReport()

    html = build_member_memory(project, report, fmt="html")
    assert "<h2>Connection checks (AISC 360 Chapter J) 9 - a &amp; b</h2>" in html
    assert "<th>k_x</th>" in html and "<td>2 &amp; 3</td>" in html
    markdown = build_member_memory(project, report, fmt="markdown")
    assert "| Check | k_x |\n|---|---|\n| 1 | 2 & 3 |" in markdown
    latex = build_member_memory(project, report, fmt="latex")
    assert r"\begin{longtable}{ll}" in latex and r"1 & 2 \& 3 \\" in latex
    with zipfile.ZipFile(io.BytesIO(odt_bytes(project, report))) as package:
        content = package.read("content.xml").decode()
    assert "table:name='Extra'" in content and "2 &amp; 3" in content
