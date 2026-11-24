"""The design check tables of the calculation memory, declared once for every format.

Each design check that adds tables to the memory (the AISC 341 joints, the
AISC 358 RBS connections, the SCBF gussets, joints and splices, the Chapter J
connection checks, the SCBF capacity design) is a function here that returns its
:class:`Table` objects for a report, registered in :data:`MEMORY_SECTIONS` in
the order the memory prints them. ``services/calc_memory.py`` renders the same
tables as HTML, Markdown, LaTeX and OpenDocument, so a new check is one function
and its labels, not four copies of the same table.

A table's heading and columns name labels of the memory's language
(``calc_memory._LABELS``); :class:`Raw` marks a column written as it is. The
cells are text already: no format escapes them differently from another.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

#: How a heading part is written: a label of the language, text from the model
#: (escaped by every format), or plain characters (separators, ids).
PartKind = Literal["label", "text", "plain"]


@dataclass(frozen=True)
class Raw:
    """A column header written as it is, not a label key (``Sh``, ``Lw``)."""

    text: str


Column = str | Raw


@dataclass(frozen=True)
class Table:
    """One table of the memory: a heading, its columns and its rows."""

    heading: tuple[tuple[PartKind, str], ...]
    columns: tuple[Column, ...]
    rows: list[list[str]]
    odt_name: str
    level: int = 2
    """2 for a section of the memory, 3 for the detail of one item of it."""


def fmt(value: float) -> str:
    """A number the way the memory prints it: four significant digits."""
    if value == 0.0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 1e5 or magnitude < 1e-3:
        return f"{value:.4e}"
    return f"{value:.4g}"


def _section(key: str, odt_name: str, columns: tuple[Column, ...], rows: list[list[str]]) -> Table:
    return Table((("label", key),), columns, rows, odt_name)


# ─────────────────────────── rows ───────────────────────────
def _joint_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(j.node_id),
            fmt(j.ratio),
            j.status,
            fmt(j.panel_ratio),
            j.panel_status,
            j.load_set,
        ]
        for j in sorted(report.joints, key=lambda item: item.node_id)
    ]


def _connection_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(c.connection_id),
            str(c.beam_element_id),
            str(c.column_element_id),
            c.shape,
            fmt(c.sh),
            fmt(c.mpr),
            f"{c.protected_from:g}-{c.protected_to:g} "
            f"({'clear' if c.zone_clear else 'node inside'})",
            f"{c.flexure_ratio:.3f}" if c.flexure_status else "-",
            c.flexure_status or "-",
            c.status,
        ]
        for c in report.connections
    ]


def _rbs_check_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(c.connection_id),
            fmt(c.span_ratio) if c.span_limit else "-",
            fmt(c.span_limit) if c.span_limit else "-",
            c.span_status or "not checked",
            fmt(c.shear_demand) if c.shear_capacity else "-",
            fmt(c.shear_capacity) if c.shear_capacity else "-",
            fmt(c.shear_ratio) if c.shear_capacity else "-",
            c.shear_status or "not checked",
            fmt(c.web_ratio) if c.web_status else "-",
            c.web_status or "not checked",
        ]
        for c in report.connections
    ]


def _web_check_rows(connection: Any) -> list[list[str]]:
    return [
        [c.name, c.equation, fmt(c.demand), fmt(c.capacity), fmt(c.ratio)]
        for c in connection.web_checks
    ]


def _chapter_j_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(item.check_id),
            item.name or item.check_type,
            item.check_type,
            fmt(item.demand),
            fmt(item.nominal),
            fmt(item.available),
            fmt(item.ratio),
            item.status,
        ]
        for item in report.chapter_j
    ]


def _protected_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(zone.element_id),
            ", ".join(f"{low:.2f}-{high:.2f}" for low, high in zone.ranges),
            "clear" if zone.zone_clear else "node inside",
        ]
        for zone in report.protected_zones
    ]


def _gusset_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(g.gusset_id),
            str(g.brace_element_id),
            g.shape,
            fmt(g.t),
            fmt(g.b),
            fmt(g.lw),
            fmt(g.free_length),
            fmt(g.demand),
            fmt(g.ratio),
            g.status,
        ]
        for g in report.gussets
    ]


def _brace_connection_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(g.gusset_id),
            str(g.brace_element_id),
            fmt(g.tension_demand),
            fmt(g.compression_demand),
            fmt(g.flexure_demand) if g.flexure_demand else "-",
            fmt(g.weld_leg) if g.weld_leg else "-",
            fmt(g.weld_required_leg) if g.weld_leg else "-",
            fmt(g.weld_ratio) if g.weld_leg else "-",
            g.weld_status or "not checked",
        ]
        for g in report.gussets
    ]


def _scbf_joint_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(j.node_id),
            str(j.beam_element_id),
            ", ".join(str(c) for c in j.column_element_ids),
            str(j.brace_element_id),
            fmt(j.beam_moment),
            fmt(j.column_moment),
            fmt(j.required_moment),
            fmt(j.available_moment) if j.available_moment else "-",
            fmt(j.ratio) if j.available_moment else "-",
            j.status,
        ]
        for j in report.scbf_joints
    ]


def _column_splice_rows(report: Any) -> list[list[str]]:
    return [
        [
            str(s.splice_id),
            str(s.node_id),
            f"{s.top_element_id} ({s.shape_top})",
            f"{s.bottom_element_id} ({s.shape_bottom})",
            fmt(s.clear_height),
            fmt(s.moment),
            fmt(s.shear),
            s.status,
        ]
        for s in report.column_splices
    ]


def _capacity_rows(report: Any) -> list[list[str]]:
    return [
        [
            item.load_set,
            str(item.brace_element_id),
            item.shape,
            item.state,
            fmt(item.analysis_force),
            fmt(item.expected_force),
            fmt(item.factor),
        ]
        for item in report.capacity_design
    ]


# ─────────────────────────── the sections ───────────────────────────
def _joints(report: Any) -> list[Table]:
    if not report.joints:
        return []
    columns = ("joint", "scwb", "status", "panel", "panel_status", "load_set")
    return [_section("joints", "Joints", columns, _joint_rows(report))]


def _rbs_connections(report: Any) -> list[Table]:
    if not report.connections:
        return []
    tables = [
        _section(
            "connections",
            "Connections",
            (
                "connection",
                "beam",
                "column",
                "shape",
                Raw("Sh"),
                "mpr",
                "protected",
                Raw("Mf / phi Mpe"),
                Raw("RBS"),
                "status",
            ),
            _connection_rows(report),
        ),
        _section(
            "rbs_checks",
            "RbsChecks",
            (
                "connection",
                "span_ratio",
                "limit",
                "span",
                "shear_demand",
                "shear_capacity",
                "shear_ratio",
                "shear",
                "web_ratio",
                "web_status",
            ),
            _rbs_check_rows(report),
        ),
    ]
    for connection in report.connections:
        if connection.web_checks:
            heading: tuple[tuple[PartKind, str], ...] = (
                ("label", "connection"),
                ("plain", f" {connection.connection_id} - "),
                ("label", "web_connection"),
            )
            columns = ("check", "equation", "demand", "capacity", "ratio")
            tables.append(
                Table(heading, columns, _web_check_rows(connection), "WebChecks", level=3)
            )
    return tables


def _protected_zones(report: Any) -> list[Table]:
    if not report.protected_zones:
        return []
    columns = ("element", "zones_x", "status")
    return [_section("zones", "Zones", columns, _protected_rows(report))]


def _scbf_gussets(report: Any) -> list[Table]:
    if not report.gussets:
        return []
    return [
        _section(
            "gussets",
            "Gussets",
            (
                "gusset",
                "brace",
                "shape",
                Raw("t"),
                Raw("b"),
                Raw("Lw"),
                Raw("Lc"),
                "expected",
                "ratio",
                "status",
            ),
            _gusset_rows(report),
        ),
        _section(
            "brace_connections",
            "BraceConnections",
            (
                "gusset",
                "brace",
                "tension",
                "compression",
                "flexure",
                "weld_leg",
                "required_leg",
                "weld_ratio",
                "weld_status",
            ),
            _brace_connection_rows(report),
        ),
    ]


def _scbf_joints(report: Any) -> list[Table]:
    if not report.scbf_joints:
        return []
    columns = (
        "joint",
        "beam",
        "columns",
        "brace",
        "beam_moment",
        "column_moment",
        "required_moment",
        "available_moment",
        "ratio",
        "status",
    )
    return [_section("scbf_joints", "ScbfJoints", columns, _scbf_joint_rows(report))]


def _column_splices(report: Any) -> list[Table]:
    if not report.column_splices:
        return []
    columns = (
        "splice",
        "joint",
        "top_column",
        "bottom_column",
        "clear_height",
        "required_moment",
        "required_shear",
        "status",
    )
    return [_section("column_splices", "ColumnSplices", columns, _column_splice_rows(report))]


def _chapter_j(report: Any) -> list[Table]:
    if not report.chapter_j:
        return []
    columns = ("check", "name", "type", "demand", "nominal", "capacity", "ratio", "status")
    tables = [_section("chapter_j", "ChapterJ", columns, _chapter_j_rows(report))]
    for item in report.chapter_j:
        if not item.steps:
            continue
        heading: tuple[tuple[PartKind, str], ...] = (
            ("label", "check"),
            ("plain", f" {item.check_id} - "),
            ("text", item.name or item.check_type),
        )
        steps = [
            [
                step.label,
                step.formula,
                step.substitution,
                fmt(step.value) if step.value is not None else "",
            ]
            for step in item.steps
        ]
        step_columns = ("label", "formula", "substitution", "value")
        tables.append(Table(heading, step_columns, steps, "ChapterJSteps", level=3))
    return tables


def _capacity_design(report: Any) -> list[Table]:
    if not report.capacity_design:
        return []
    columns = (
        "load_set",
        "brace",
        "shape",
        "state",
        "analysis_force",
        "expected_strength",
        "factor",
    )
    return [_section("capacity_design", "Capacity", columns, _capacity_rows(report))]


#: Every design check's tables, in the order the memory prints them.
MEMORY_SECTIONS: list[tuple[str, Callable[[Any], list[Table]]]] = [
    ("aisc341_joints", _joints),
    ("aisc358_rbs", _rbs_connections),
    ("scbf_protected_zones", _protected_zones),
    ("scbf_gussets", _scbf_gussets),
    ("scbf_joints", _scbf_joints),
    ("scbf_column_splices", _column_splices),
    ("aisc360_chapter_j", _chapter_j),
    ("scbf_capacity_design", _capacity_design),
]


def memory_tables(report: Any) -> list[Table]:
    """Every design check table of ``report``, in order (the member sheets excluded)."""
    return [table for _key, section in MEMORY_SECTIONS for table in section(report)]


__all__ = ["MEMORY_SECTIONS", "Column", "PartKind", "Raw", "Table", "fmt", "memory_tables"]
