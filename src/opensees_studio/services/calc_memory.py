"""Member calculation memory: the design checks as a printable document.

The design engine keeps one ``LimitStateCheck`` per limit state and station
(:mod:`core.design.calc`); this module turns them into a document with the
project cover, an index and one sheet per member: properties, demands, every
limit state with its steps, and the governing result. It is a service: it reads
project units, shapes and the report, and writes HTML or Markdown. No Qt.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Literal

from opensees_studio import __version__
from opensees_studio.services.steel_design import shape_in_units

Language = Literal["en", "es"]
Format = Literal["html", "markdown"]

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


def _fmt(value: float) -> str:
    if value == 0.0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 1e5 or magnitude < 1e-3:
        return f"{value:.4e}"
    return f"{value:.4g}"


def _e(value: object) -> str:
    return html.escape(str(value))


def _properties(shape: object) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for attribute, label in _PROPERTIES:
        value = getattr(shape, attribute, None)
        if isinstance(value, int | float) and value:
            out.append((label, _fmt(float(value))))
    return out


def _member_shape(project: Any, shape_name: str) -> object | None:
    try:
        return shape_in_units(shape_name, project.meta.units)
    except (KeyError, ValueError):
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
        [str(m.element_id), m.shape, _fmt(m.ratio), m.status]
        for m in sorted(report.members, key=lambda item: item.element_id)
    ]


def _member_html(project: Any, member: Any, labels: dict[str, str]) -> list[str]:
    shape = _member_shape(project, member.shape)
    out = [
        f"<h2>{labels['element']} {member.element_id} - {_e(member.shape)}</h2>",
        f"<p>{labels['governing']}: <b>{_e(member.check)}</b> "
        f"({_e(member.equation)}), {labels['ratio']} {_fmt(member.ratio)}; "
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
        + "".join(members)
        + f"<p class='note'>{_e(labels['disclaimer'])}</p></body></html>"
    )


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
    for member in sorted(report.members, key=lambda item: item.element_id):
        lines += [
            "",
            f"## {labels['element']} {member.element_id} - {member.shape}",
            "",
            f"**{labels['governing']}:** {member.check} ({member.equation}), "
            f"{labels['ratio']} {_fmt(member.ratio)}; {labels['load_set']} "
            f"{member.load_set}; {labels['station']} {member.station:.2f}.",
        ]
        shape = _member_shape(project, member.shape)
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
    """The member calculation memory as HTML or Markdown."""
    labels = _LABELS.get(language)
    if labels is None:
        raise ValueError(f"Unknown language {language!r}: use 'en' or 'es'.")
    if fmt == "html":
        return _html(project, report, labels)
    if fmt == "markdown":
        return _markdown(project, report, labels)
    raise ValueError(f"Unknown format {fmt!r}: use 'html' or 'markdown'.")
