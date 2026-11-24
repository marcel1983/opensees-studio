"""Member calculation memory: the design checks as a printable document.

The design engine keeps one ``LimitStateCheck`` per limit state and station
(:mod:`core.design.calc`); this module turns them into a document with the
project cover, an index and one sheet per member: properties, demands, every
limit state with its steps, and the governing result. It is a service: it reads
project units, shapes and the report, and writes HTML or Markdown. No Qt.
"""

from __future__ import annotations

import html
import io
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from opensees_studio import __version__
from opensees_studio.core.design.aisi_s100 import cold_formed_member
from opensees_studio.core.design.ratio_bands import ratio_text
from opensees_studio.core.sections.cold_formed import ColdFormedShape
from opensees_studio.services.memory_tables import Column, Raw, Table, memory_tables
from opensees_studio.services.memory_tables import fmt as _fmt
from opensees_studio.services.steel_design import shape_in_units

Language = Literal["en", "es"]
Format = Literal["html", "markdown", "latex"]

_LABELS: dict[Language, dict[str, str]] = {
    "en": {
        "title": "Calculation Memory",
        "subtitle": "AISC 360-16 steel member checks",
        "project": "Project",
        "author": "Author",
        "company": "Company",
        "date": "Date",
        "program": "Program",
        "revisions": "Revisions",
        "rev": "Rev",
        "by": "By",
        "description": "Description",
        "index": "Index",
        "joints": "Joints (AISC 341-22)",
        "connections": "Connections (AISC 358-22)",
        "zones": "SCBF protected zones (AISC 341-22 F2.5c)",
        "zones_x": "Zones (x/L)",
        "gussets": "SCBF gusset plates (AISC 341-22 F2.6c)",
        "gusset": "Gusset",
        "brace": "Brace",
        "expected": "Ry Fy Ag",
        "brace_connections": "SCBF brace connections (AISC 341-22 F2.6c)",
        "tension": "Tension",
        "compression": "Compression",
        "flexure": "Flexure",
        "weld_leg": "Weld leg",
        "required_leg": "Required leg",
        "weld_ratio": "Weld ratio",
        "weld_status": "Weld status",
        "scbf_joints": "SCBF beam-to-column connections (AISC 341-22 F2.6b)",
        "columns": "Columns",
        "beam_moment": "Beam moment",
        "column_moment": "Column moment",
        "required_moment": "Required moment",
        "available_moment": "Available moment",
        "column_splices": "SCBF column splices (AISC 341-22 F2.6d)",
        "splice": "Splice",
        "top_column": "Top column",
        "bottom_column": "Bottom column",
        "clear_height": "Hc",
        "required_shear": "Required shear",
        "capacity_design": "SCBF capacity design (AISC 341-22 F2.3)",
        "state": "State",
        "analysis_force": "Analysis force",
        "expected_strength": "Expected strength",
        "factor": "Factor",
        "connection": "Connection",
        "rbs_checks": "RBS beam checks (AISC 358-22 5.7 steps 1 and 9)",
        "span_ratio": "Clear span / d",
        "limit": "Limit",
        "span": "Span",
        "shear_demand": "Vh",
        "shear_capacity": "phi Vn",
        "shear_ratio": "Vh / phi Vn",
        "shear": "Shear",
        "web_ratio": "Web ratio",
        "web_status": "Web status",
        "web_connection": "Web connection (AISC 358-22 5.5)",
        "chapter_j": "Connection checks (AISC 360 Chapter J)",
        "name": "Name",
        "type": "Type",
        "nominal": "Nominal",
        "beam": "Beam",
        "column": "Column",
        "protected": "Protected zone",
        "mpr": "Mpr",
        "joint": "Joint",
        "scwb": "Sum M*pc / Sum M*be",
        "panel": "Vr / phi Rn",
        "panel_status": "Panel",
        "element": "Element",
        "shape": "Shape",
        "ratio": "Ratio",
        "status": "Status",
        "properties": "Geometric properties",
        "limit_states": "Limit states",
        "check": "Check",
        "equation": "Equation",
        "demand": "Demand",
        "capacity": "Capacity",
        "steps": "Calculation",
        "label": "Step",
        "formula": "Formula",
        "substitution": "Substitution",
        "value": "Value",
        "governing": "Governing check",
        "load_set": "Load set",
        "station": "Station",
        "notes": "Notes",
        "disclaimer": (
            "This document reproduces the checks run by OpenSees Studio. "
            "The engineer of record remains responsible for the design, the code "
            "edition and the assumptions."
        ),
        "none": "-",
    },
    "es": {
        "title": "Memoria de cálculo",
        "subtitle": "Revisión de elementos de acero AISC 360-16",
        "project": "Proyecto",
        "author": "Autor",
        "company": "Empresa",
        "date": "Fecha",
        "program": "Programa",
        "revisions": "Revisiones",
        "rev": "Rev",
        "by": "Por",
        "description": "Descripción",
        "index": "Índice",
        "joints": "Juntas (AISC 341-22)",
        "connections": "Conexiones (AISC 358-22)",
        "zones": "Zonas protegidas SCBF (AISC 341-22 F2.5c)",
        "zones_x": "Zonas (x/L)",
        "gussets": "Planchas de unión SCBF (AISC 341-22 F2.6c)",
        "gusset": "Plancha",
        "brace": "Arriostramiento",
        "expected": "Ry Fy Ag",
        "brace_connections": "Conexiones de arriostramiento SCBF (AISC 341-22 F2.6c)",
        "tension": "Tracción",
        "compression": "Compresión",
        "flexure": "Flexión",
        "weld_leg": "Pierna de soldadura",
        "required_leg": "Pierna requerida",
        "weld_ratio": "Relación soldadura",
        "weld_status": "Estado soldadura",
        "scbf_joints": "Conexiones viga-columna SCBF (AISC 341-22 F2.6b)",
        "columns": "Columnas",
        "beam_moment": "Momento viga",
        "column_moment": "Momento columna",
        "required_moment": "Momento requerido",
        "available_moment": "Momento disponible",
        "column_splices": "Empalmes de columna SCBF (AISC 341-22 F2.6d)",
        "splice": "Empalme",
        "top_column": "Columna superior",
        "bottom_column": "Columna inferior",
        "clear_height": "Hc",
        "required_shear": "Corte requerido",
        "capacity_design": "Diseño por capacidad SCBF (AISC 341-22 F2.3)",
        "state": "Estado",
        "analysis_force": "Fuerza de análisis",
        "expected_strength": "Resistencia esperada",
        "factor": "Factor",
        "connection": "Conexión",
        "rbs_checks": "Chequeos de viga RBS (AISC 358-22 5.7 pasos 1 y 9)",
        "span_ratio": "Luz libre / d",
        "limit": "Límite",
        "span": "Luz",
        "shear_demand": "Vh",
        "shear_capacity": "phi Vn",
        "shear_ratio": "Vh / phi Vn",
        "shear": "Corte",
        "web_ratio": "Relación alma",
        "web_status": "Estado alma",
        "web_connection": "Conexión del alma (AISC 358-22 5.5)",
        "chapter_j": "Chequeos de conexión (AISC 360 Capítulo J)",
        "name": "Nombre",
        "type": "Tipo",
        "nominal": "Nominal",
        "beam": "Viga",
        "column": "Columna",
        "protected": "Zona protegida",
        "mpr": "Mpr",
        "joint": "Junta",
        "scwb": "Sum M*pc / Sum M*be",
        "panel": "Vr / phi Rn",
        "panel_status": "Panel",
        "element": "Elemento",
        "shape": "Perfil",
        "ratio": "Razón",
        "status": "Estado",
        "properties": "Propiedades geométricas",
        "limit_states": "Estados límite",
        "check": "Chequeo",
        "equation": "Ecuación",
        "demand": "Demanda",
        "capacity": "Capacidad",
        "steps": "Cálculo",
        "label": "Paso",
        "formula": "Fórmula",
        "substitution": "Sustitución",
        "value": "Valor",
        "governing": "Chequeo gobernante",
        "load_set": "Combinación",
        "station": "Estación",
        "notes": "Notas",
        "disclaimer": (
            "Este documento reproduce los chequeos ejecutados por OpenSees Studio. "
            "El ingeniero responsable mantiene la responsabilidad del diseño, la "
            "edición del código y los supuestos."
        ),
        "none": "-",
    },
}

#: Attributes printed, in order, when the shape family has them.
_PROPERTIES = (
    ("A", "A"),
    ("d", "d"),
    ("H", "H"),
    ("B", "B"),
    ("D", "D"),
    ("bf", "bf"),
    ("tf", "tf"),
    ("tw", "tw"),
    ("t", "t"),
    ("Ix", "Ix"),
    ("Iy", "Iy"),
    ("Zx", "Zx"),
    ("Zy", "Zy"),
    ("Sx", "Sx"),
    ("Sy", "Sy"),
    ("rx", "rx"),
    ("ry", "ry"),
    ("J", "J"),
    ("Cw", "Cw"),
)


@dataclass(frozen=True)
class MemoryOptions:
    language: Language = "en"
    fmt: Format = "html"


def _e(value: object) -> str:
    return html.escape(str(value))


def _properties(shape: object) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for attribute, label in _PROPERTIES:
        value = getattr(shape, attribute, None)
        if isinstance(value, int | float) and value:
            out.append((label, _fmt(float(value))))
    return out


def _member_shape(project: Any, shape_name: str, element_id: int = 0) -> object | None:
    """The AISC shape of that name, or the cold-formed profile of the element's section."""
    try:
        return shape_in_units(shape_name, project.meta.units)
    except (KeyError, ValueError):
        pass
    element = next((e for e in project.elements if e.id == element_id), None)
    section_id = getattr(element, "section_id", None)
    section = next((s for s in project.sections if s.id == section_id), None)
    profile = getattr(section, "shape", None)
    if not isinstance(profile, ColdFormedShape):
        return None
    try:
        return cold_formed_member(profile, float(getattr(section, "E", 0.0) or 1.0))
    except ValueError:
        return None


def _cover(project: Any, labels: dict[str, str]) -> list[tuple[str, str]]:
    meta = project.meta
    return [
        (labels["project"], meta.name),
        (labels["author"], meta.author or labels["none"]),
        (labels["company"], meta.company or labels["none"]),
        (labels["date"], meta.date or labels["none"]),
        (labels["program"], f"OpenSees Studio {__version__}"),
    ]


def _index_rows(report: Any) -> list[list[str]]:
    return [
        [str(m.element_id), m.shape, ratio_text(m.ratio), m.status]
        for m in sorted(report.members, key=lambda item: item.element_id)
    ]


def _member_html(project: Any, member: Any, labels: dict[str, str]) -> list[str]:
    shape = _member_shape(project, member.shape, member.element_id)
    out = [
        f"<h2>{labels['element']} {member.element_id} - {_e(member.shape)}</h2>",
        f"<p>{labels['governing']}: <b>{_e(member.check)}</b> "
        f"({_e(member.equation)}), {labels['ratio']} {ratio_text(member.ratio)}; "
        f"{labels['load_set']} {_e(member.load_set)}; "
        f"{labels['station']} {member.station:.2f}.</p>",
    ]
    if shape is not None:
        rows = _properties(shape)
        if rows:
            out.append(f"<h3>{labels['properties']}</h3>")
            out.append(
                "<table><tr><th>Property</th><th>Value</th></tr>"
                + "".join(f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>" for k, v in rows)
                + "</table>"
            )
    if member.checks:
        out.append(f"<h3>{labels['limit_states']}</h3>")
        out.append(
            "<table><tr>"
            f"<th>{labels['check']}</th><th>{labels['equation']}</th>"
            f"<th>{labels['demand']}</th><th>{labels['capacity']}</th>"
            f"<th>{labels['ratio']}</th></tr>"
            + "".join(
                f"<tr><td>{_e(c.name)}</td><td>{_e(c.equation)}</td>"
                f"<td>{_fmt(c.demand)}</td><td>{_fmt(c.capacity)}</td>"
                f"<td>{_fmt(c.ratio)}</td></tr>"
                for c in member.checks
            )
            + "</table>"
        )
        for check in member.checks:
            if not check.steps:
                continue
            out.append(f"<h3>{_e(check.name)} - {_e(check.equation)}</h3>")
            out.append(
                "<table><tr>"
                f"<th>{labels['label']}</th><th>{labels['formula']}</th>"
                f"<th>{labels['substitution']}</th><th>{labels['value']}</th></tr>"
                + "".join(
                    f"<tr><td>{_e(s.label)}</td><td>{_e(s.formula)}</td>"
                    f"<td>{_e(s.substitution)}</td>"
                    f"<td>{_fmt(s.value) if s.value is not None else ''}</td></tr>"
                    for s in check.steps
                )
                + "</table>"
            )
    if member.notes:
        out.append(f"<h3>{labels['notes']}</h3><ul>")
        out.extend(f"<li>{_e(note)}</li>" for note in member.notes)
        out.append("</ul>")
    return out


def _heading(
    table: Table,
    labels: dict[str, str],
    escape: Callable[[object], str],
    *,
    escape_labels: bool = True,
) -> str:
    """A table's heading in one format: model text escaped, labels as the format writes them."""
    out = []
    for kind, value in table.heading:
        if kind == "label":
            out.append(escape(labels[value]) if escape_labels else labels[value])
        elif kind == "text":
            out.append(escape(value))
        else:
            out.append(value)
    return "".join(out)


def _header(column: Column, labels: dict[str, str]) -> str:
    return column.text if isinstance(column, Raw) else labels[column]


def _html_table(table: Table, labels: dict[str, str]) -> str:
    level = table.level
    return (
        f"<h{level}>{_heading(table, labels, _e, escape_labels=False)}</h{level}><table><tr>"
        + "".join(f"<th>{_header(column, labels)}</th>" for column in table.columns)
        + "</tr>"
        + "".join(
            "<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>" for row in table.rows
        )
        + "</table>"
    )


def _html(project: Any, report: Any, labels: dict[str, str]) -> str:
    cover = "".join(
        f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>" for k, v in _cover(project, labels)
    )
    revisions = ""
    if project.meta.revisions:
        revisions = (
            f"<h3>{labels['revisions']}</h3><table><tr>"
            f"<th>{labels['rev']}</th><th>{labels['date']}</th>"
            f"<th>{labels['by']}</th><th>{labels['description']}</th></tr>"
            + "".join(
                f"<tr><td>{_e(r.code)}</td><td>{_e(r.date)}</td>"
                f"<td>{_e(r.by)}</td><td>{_e(r.description)}</td></tr>"
                for r in project.meta.revisions
            )
            + "</table>"
        )
    index = "".join(
        f"<tr><td>{_e(row[0])}</td><td>{_e(row[1])}</td>"
        f"<td>{_e(row[2])}</td><td>{_e(row[3])}</td></tr>"
        for row in _index_rows(report)
    )
    members = []
    for member in sorted(report.members, key=lambda item: item.element_id):
        members.extend(_member_html(project, member, labels))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_e(project.meta.name)} - {_e(labels['title'])}</title>"
        "<style>body{font-family:Arial,sans-serif;font-size:10pt;margin:24px}"
        "h1{font-size:18pt}h2{font-size:14pt;border-bottom:1px solid #888}"
        "h3{font-size:11pt}table{border-collapse:collapse;margin:6px 0 12px}"
        "th,td{border:1px solid #999;padding:1px 4px;text-align:right}"
        "th{background:#eee}td:first-child{text-align:left}"
        "p.note{color:#555;font-style:italic}</style></head><body>"
        f"<h1>{_e(project.meta.name)}</h1>"
        f"<h2>{_e(labels['title'])}</h2><p>{_e(labels['subtitle'])}</p>"
        f"<table>{cover}</table>{revisions}"
        f"<h2>{labels['index']}</h2><table><tr>"
        f"<th>{labels['element']}</th><th>{labels['shape']}</th>"
        f"<th>{labels['ratio']}</th><th>{labels['status']}</th></tr>{index}</table>"
        + "".join(_html_table(table, labels) for table in memory_tables(report))
        + "".join(members)
        + f"<p class='note'>{_e(labels['disclaimer'])}</p></body></html>"
    )


def _markdown_table(table: Table, labels: dict[str, str]) -> list[str]:
    columns = [_header(column, labels) for column in table.columns]
    return [
        "",
        f"{'#' * table.level} {_heading(table, labels, _plain)}",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "---|" * len(columns),
        *("| " + " | ".join(row) + " |" for row in table.rows),
    ]


def _plain(value: object) -> str:
    return str(value)


def _markdown(project: Any, report: Any, labels: dict[str, str]) -> str:
    lines = [f"# {project.meta.name}", "", f"## {labels['title']}", "", labels["subtitle"], ""]
    for key, value in _cover(project, labels):
        lines.append(f"- **{key}:** {value}")
    if project.meta.revisions:
        lines += [
            "",
            f"### {labels['revisions']}",
            "",
            f"| {labels['rev']} | {labels['date']} | {labels['by']} | {labels['description']} |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| {r.code} | {r.date} | {r.by} | {r.description} |" for r in project.meta.revisions
        ]
    lines += [
        "",
        f"## {labels['index']}",
        "",
        f"| {labels['element']} | {labels['shape']} | {labels['ratio']} | {labels['status']} |",
        "|---|---|---|---|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in _index_rows(report)]
    for table in memory_tables(report):
        lines += _markdown_table(table, labels)
    for member in sorted(report.members, key=lambda item: item.element_id):
        lines += [
            "",
            f"## {labels['element']} {member.element_id} - {member.shape}",
            "",
            f"**{labels['governing']}:** {member.check} ({member.equation}), "
            f"{labels['ratio']} {ratio_text(member.ratio)}; {labels['load_set']} "
            f"{member.load_set}; {labels['station']} {member.station:.2f}.",
        ]
        shape = _member_shape(project, member.shape, member.element_id)
        if shape is not None and (props := _properties(shape)):
            lines += ["", f"### {labels['properties']}", "", "| Property | Value |", "|---|---|"]
            lines += [f"| {k} | {v} |" for k, v in props]
        if member.checks:
            lines += [
                "",
                f"### {labels['limit_states']}",
                "",
                f"| {labels['check']} | {labels['equation']} | {labels['demand']} | {labels['capacity']} | {labels['ratio']} |",
                "|---|---|---|---|---|",
            ]
            lines += [
                f"| {c.name} | {c.equation} | {_fmt(c.demand)} | {_fmt(c.capacity)} | {_fmt(c.ratio)} |"
                for c in member.checks
            ]
            for check in member.checks:
                if not check.steps:
                    continue
                lines += [
                    "",
                    f"#### {check.name} - {check.equation}",
                    "",
                    f"| {labels['label']} | {labels['formula']} | {labels['substitution']} | {labels['value']} |",
                    "|---|---|---|---|",
                ]
                lines += [
                    f"| {s.label} | {s.formula} | {s.substitution} | "
                    f"{_fmt(s.value) if s.value is not None else ''} |"
                    for s in check.steps
                ]
        if member.notes:
            lines += ["", f"### {labels['notes']}"]
            lines += [f"- {note}" for note in member.notes]
    lines += ["", "---", labels["disclaimer"], ""]
    return "\n".join(lines)


def build_member_memory(
    project: Any,
    report: Any,
    *,
    language: Language = "en",
    fmt: Format = "html",
) -> str:
    """The member calculation memory as HTML, Markdown or LaTeX."""
    labels = _LABELS.get(language)
    if labels is None:
        raise ValueError(f"Unknown language {language!r}: use 'en' or 'es'.")
    if fmt == "html":
        return _html(project, report, labels)
    if fmt == "markdown":
        return _markdown(project, report, labels)
    if fmt == "latex":
        return _latex(project, report, labels)
    raise ValueError(f"Unknown format {fmt!r}: use 'html', 'markdown' or 'latex'.")


def _tex_escape(value: object) -> str:
    text = str(value)
    for old, new in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        text = text.replace(old, new)
    return text


def _latex_table(table: Table, labels: dict[str, str]) -> list[str]:
    columns = [
        column.text if isinstance(column, Raw) else _tex_escape(labels[column])
        for column in table.columns
    ]
    return [
        rf"\subsection*{{{_heading(table, labels, _tex_escape)}}}",
        r"\begin{longtable}{" + "l" * len(columns) + "}",
        " & ".join(columns) + r" \\ \toprule",
        *(" & ".join(_tex_escape(cell) for cell in row) + r" \\" for row in table.rows),
        r"\end{longtable}",
    ]


def _latex(project: Any, report: Any, labels: dict[str, str]) -> str:
    lines = [
        r"\documentclass[10pt]{article}",
        r"\usepackage[margin=20mm]{geometry}",
        r"\usepackage{longtable,booktabs}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[utf8]{inputenc}",
        r"\begin{document}",
        rf"\section*{{{_tex_escape(project.meta.name)}}}",
        rf"\subsection*{{{_tex_escape(labels['title'])}}}",
        _tex_escape(labels["subtitle"]),
        "",
    ]
    for key, value in _cover(project, labels):
        lines.append(rf"\textbf{{{_tex_escape(key)}:}} {_tex_escape(value)}\\")
    if project.meta.revisions:
        lines += [
            "",
            rf"\subsection*{{{_tex_escape(labels['revisions'])}}}",
            r"\begin{longtable}{llll}",
        ]
        lines.append(
            rf"{_tex_escape(labels['rev'])} & {_tex_escape(labels['date'])} & "
            rf"{_tex_escape(labels['by'])} & {_tex_escape(labels['description'])} \\ \toprule"
        )
        lines += [
            rf"{_tex_escape(r.code)} & {_tex_escape(r.date)} & "
            rf"{_tex_escape(r.by)} & {_tex_escape(r.description)} \\"
            for r in project.meta.revisions
        ]
        lines.append(r"\end{longtable}")
    lines += ["", rf"\subsection*{{{_tex_escape(labels['index'])}}}", r"\begin{longtable}{llll}"]
    lines.append(
        rf"{_tex_escape(labels['element'])} & {_tex_escape(labels['shape'])} & "
        rf"{_tex_escape(labels['ratio'])} & {_tex_escape(labels['status'])} \\ \toprule"
    )
    lines += [" & ".join(_tex_escape(cell) for cell in row) + r" \\" for row in _index_rows(report)]
    lines.append(r"\end{longtable}")
    for table in memory_tables(report):
        lines += _latex_table(table, labels)
    for member in sorted(report.members, key=lambda item: item.element_id):
        lines += [
            "",
            rf"\subsection*{{{_tex_escape(labels['element'])} {member.element_id} - {_tex_escape(member.shape)}}}",
            rf"\textbf{{{_tex_escape(labels['governing'])}:}} {_tex_escape(member.check)} "
            rf"({_tex_escape(member.equation)}), {_tex_escape(labels['ratio'])} {ratio_text(member.ratio)}; "
            rf"{_tex_escape(labels['load_set'])} {_tex_escape(member.load_set)}; "
            rf"{_tex_escape(labels['station'])} {member.station:.2f}.",
            "",
        ]
        shape = _member_shape(project, member.shape, member.element_id)
        if shape is not None and (props := _properties(shape)):
            lines += [rf"\textbf{{{_tex_escape(labels['properties'])}}}", r"\begin{longtable}{ll}"]
            lines += [rf"{_tex_escape(k)} & {_tex_escape(v)} \\" for k, v in props]
            lines.append(r"\end{longtable}")
        for check in member.checks:
            lines += [
                rf"\textbf{{{_tex_escape(check.name)}}} ({_tex_escape(check.equation)}): "
                rf"{_tex_escape(labels['demand'])} {_fmt(check.demand)}, "
                rf"{_tex_escape(labels['capacity'])} {_fmt(check.capacity)}, "
                rf"{_tex_escape(labels['ratio'])} {_fmt(check.ratio)}.",
            ]
            if check.steps:
                lines += [r"\begin{longtable}{llll}"]
                lines.append(
                    rf"{_tex_escape(labels['label'])} & {_tex_escape(labels['formula'])} & "
                    rf"{_tex_escape(labels['substitution'])} & {_tex_escape(labels['value'])} \\ \toprule"
                )
                lines += [
                    rf"{_tex_escape(s.label)} & {_tex_escape(s.formula)} & "
                    rf"{_tex_escape(s.substitution)} & "
                    rf"{_fmt(s.value) if s.value is not None else ''} \\"
                    for s in check.steps
                ]
                lines.append(r"\end{longtable}")
    lines += ["", r"\emph{" + _tex_escape(labels["disclaimer"]) + "}", r"\end{document}", ""]
    return "\n".join(lines)


def _odt_text(value: object) -> str:
    import xml.sax.saxutils as saxutils

    return saxutils.escape(str(value))


def _odt_table(table: Table, labels: dict[str, str]) -> list[str]:
    header = [_header(column, labels) for column in table.columns]
    return [
        f"<text:h text:outline-level='2'>{_heading(table, labels, _odt_text)}</text:h>",
        f"<table:table table:name='{table.odt_name}'>",
        *(
            "<table:table-row>"
            + "".join(
                f"<table:table-cell><text:p>{_odt_text(c)}</text:p></table:table-cell>" for c in row
            )
            + "</table:table-row>"
            for row in [header, *table.rows]
        ),
        "</table:table>",
    ]


def odt_bytes(project: Any, report: Any, *, language: Language = "en") -> bytes:
    """The member memory as an OpenDocument text package (a zip)."""
    labels = _LABELS.get(language)
    if labels is None:
        raise ValueError(f"Unknown language {language!r}: use 'en' or 'es'.")
    body: list[str] = [
        f"<text:h text:outline-level='1'>{_odt_text(project.meta.name)}</text:h>",
        f"<text:h text:outline-level='2'>{_odt_text(labels['title'])}</text:h>",
        f"<text:p>{_odt_text(labels['subtitle'])}</text:p>",
    ]
    for key, value in _cover(project, labels):
        body.append(
            f"<text:p><text:span text:style-name='Bold'>{_odt_text(key)}:</text:span> {_odt_text(value)}</text:p>"
        )
    if project.meta.revisions:
        body.append(f"<text:h text:outline-level='3'>{_odt_text(labels['revisions'])}</text:h>")
        body.append("<table:table table:name='Revisions'>")
        for row in [[labels["rev"], labels["date"], labels["by"], labels["description"]]] + [
            [r.code, r.date, r.by, r.description] for r in project.meta.revisions
        ]:
            body.append(
                "<table:table-row>"
                + "".join(
                    f"<table:table-cell><text:p>{_odt_text(c)}</text:p></table:table-cell>"
                    for c in row
                )
                + "</table:table-row>"
            )
        body.append("</table:table>")
    body.append(f"<text:h text:outline-level='2'>{_odt_text(labels['index'])}</text:h>")
    body.append("<table:table table:name='Index'>")
    index_rows = [[labels["element"], labels["shape"], labels["ratio"], labels["status"]]]
    index_rows.extend(_index_rows(report))
    for row in index_rows:
        body.append(
            "<table:table-row>"
            + "".join(
                f"<table:table-cell><text:p>{_odt_text(c)}</text:p></table:table-cell>" for c in row
            )
            + "</table:table-row>"
        )
    body.append("</table:table>")
    for table in memory_tables(report):
        body += _odt_table(table, labels)
    for member in sorted(report.members, key=lambda item: item.element_id):
        body.append(
            f"<text:h text:outline-level='2'>{_odt_text(labels['element'])} {member.element_id} - {_odt_text(member.shape)}</text:h>"
        )
        body.append(
            f"<text:p>{_odt_text(labels['governing'])}: {_odt_text(member.check)} ({_odt_text(member.equation)}); {_odt_text(labels['ratio'])} {ratio_text(member.ratio)}</text:p>"
        )
        shape = _member_shape(project, member.shape, member.element_id)
        if shape is not None and (props := _properties(shape)):
            body.append(
                f"<text:h text:outline-level='3'>{_odt_text(labels['properties'])}</text:h>"
            )
            body.append("<table:table table:name='Properties'>")
            for key, value in props:
                body.append(
                    f"<table:table-row><table:table-cell><text:p>{_odt_text(key)}</text:p></table:table-cell><table:table-cell><text:p>{_odt_text(value)}</text:p></table:table-cell></table:table-row>"
                )
            body.append("</table:table>")
        if member.checks:
            body.append(
                f"<text:h text:outline-level='3'>{_odt_text(labels['limit_states'])}</text:h>"
            )
            body.append("<table:table table:name='Checks'>")
            header = [
                labels["check"],
                labels["equation"],
                labels["demand"],
                labels["capacity"],
                labels["ratio"],
            ]
            rows = [header] + [
                [c.name, c.equation, _fmt(c.demand), _fmt(c.capacity), _fmt(c.ratio)]
                for c in member.checks
            ]
            for row in rows:
                body.append(
                    "<table:table-row>"
                    + "".join(
                        f"<table:table-cell><text:p>{_odt_text(c)}</text:p></table:table-cell>"
                        for c in row
                    )
                    + "</table:table-row>"
                )
            body.append("</table:table>")
            for check in member.checks:
                if not check.steps:
                    continue
                body.append(
                    f"<text:h text:outline-level='4'>{_odt_text(check.name)} - {_odt_text(check.equation)}</text:h>"
                )
                body.append("<table:table table:name='Steps'>")
                header = [
                    labels["label"],
                    labels["formula"],
                    labels["substitution"],
                    labels["value"],
                ]
                rows = [header] + [
                    [
                        s.label,
                        s.formula,
                        s.substitution,
                        _fmt(s.value) if s.value is not None else "",
                    ]
                    for s in check.steps
                ]
                for row in rows:
                    body.append(
                        "<table:table-row>"
                        + "".join(
                            f"<table:table-cell><text:p>{_odt_text(c)}</text:p></table:table-cell>"
                            for c in row
                        )
                        + "</table:table-row>"
                    )
                body.append("</table:table>")
    body.append(
        f"<text:p><text:span text:style-name='Italic'>{_odt_text(labels['disclaimer'])}</text:span></text:p>"
    )
    content = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<office:document-content "
        "xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0' "
        "xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0' "
        "xmlns:table='urn:oasis:names:tc:opendocument:xmlns:table:1.0' "
        "office:version='1.2'><office:body><office:text>"
        + "".join(body)
        + "</office:text></office:body></office:document-content>"
    )
    styles = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<office:document-styles "
        "xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0' "
        "xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0' "
        "xmlns:style='urn:oasis:names:tc:opendocument:xmlns:style:1.0' "
        "office:version='1.2'><office:styles>"
        "<style:style style:name='Bold' style:family='text'><style:text-properties fo:font-weight='bold' xmlns:fo='urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0'/></style:style>"
        "<style:style style:name='Italic' style:family='text'><style:text-properties fo:font-style='italic' xmlns:fo='urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0'/></style:style>"
        "</office:styles></office:document-styles>"
    )
    manifest = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<manifest:manifest xmlns:manifest='urn:oasis:names:tc:opendocument:xmlns:manifest:1.0' manifest:version='1.2'>"
        "<manifest:file-entry manifest:full-path='/' manifest:media-type='application/vnd.oasis.opendocument.text'/>"
        "<manifest:file-entry manifest:full-path='content.xml' manifest:media-type='text/xml'/>"
        "<manifest:file-entry manifest:full-path='styles.xml' manifest:media-type='text/xml'/>"
        "</manifest:manifest>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )
        package.writestr("content.xml", content)
        package.writestr("styles.xml", styles)
        package.writestr("META-INF/manifest.xml", manifest)
    return buffer.getvalue()
