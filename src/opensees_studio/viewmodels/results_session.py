"""The analysis results the window holds in memory, and what can be asked of them.

Three things, which used to be three attributes of the window:

- ``latest``: the results on screen (any kind), or ``None``;
- ``cases``: every static or response spectrum result of the session, for the
  load combinations (:class:`~opensees_studio.viewmodels.case_results.CaseResultsCache`);
- ``extra``: modal, pushover and transient results, kept for the report only.

Nothing here is a widget: the session answers questions about the results (which
ones are current, what the caption says, the diagram of a component) and the
window, its docks and its controllers draw the answers.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from opensees_studio.core import Project
from opensees_studio.core.combinations import model_fingerprint
from opensees_studio.core.reactions import ReactionRow, reaction_rows
from opensees_studio.services.element_forces import (
    DiagramData,
    ForceComponent,
    envelope_diagram_data,
    extract_diagram_data,
)
from opensees_studio.services.results import CombinationResults, StaticResults
from opensees_studio.viewmodels.case_results import CaseResultsCache


def case_names(project: Project | None) -> dict[int, str]:
    """The current name of every analysis case, by id."""
    if project is None:
        return {}
    return {c.id: c.name for c in project.analyses}


class ResultsSession:
    """The results on screen, the case results of the session and the report's extras."""

    def __init__(self) -> None:
        self.latest: object = None  # last analysis output (any kind)
        self.cases = CaseResultsCache()
        self.extra: dict[int, tuple[str, Any]] = {}

    # ── keeping and forgetting ───────────────────────────────────────
    def keep(self, project: Project | None, results: object) -> None:
        """Keep one case's results: for the combinations, or for the report only."""
        if project is None or self.cases.put(project, results):
            return
        # Modal, pushover and transient results: kept for the report only.
        case_id = getattr(results, "case_id", None)
        if case_id is not None:
            self.extra[case_id] = (model_fingerprint(project), results)

    def clear(self) -> None:
        """Forget everything: another project, an unlocked model, Delete All Results."""
        self.cases.clear()
        self.extra.clear()
        self.latest = None

    # ── what is there ────────────────────────────────────────────────
    def current(self, project: Project | None) -> dict[int, Any]:
        """The results computed on the project as it is now, by case id."""
        return dict(self.cases.current(project)) if project is not None else {}

    def has_stored(self, project: Project | None) -> bool:
        """True when a case result is kept, whether or not one is on screen."""
        return project is not None and (bool(self.cases.current(project)) or bool(self.extra))

    def has_any(self, project: Project | None) -> bool:
        """True when unlocking the model would discard something."""
        return self.latest is not None or bool(
            self.extra or (project is not None and self.cases.current(project))
        )

    def for_report(self, project: Project | None) -> list[Any]:
        """The results the report includes: every current case, plus the report's extras."""
        if project is None:
            return []
        current = dict(self.cases.current(project))
        fingerprint = model_fingerprint(project)
        for case_id, (fp, results) in self.extra.items():
            if fp == fingerprint:
                current.setdefault(case_id, results)
        return list(current.values())

    def choices(self, project: Project | None) -> list[tuple[str, str]]:
        """``(label, key)`` for every result Display can show without running anything.

        Case results still current for the model (``case:<id>``), then every load
        combination (``combination:<id>``), whether or not its cases have run.
        """
        if project is None:
            return []
        current = self.cases.current(project)
        names = case_names(project)
        choices = [
            (f"Case: {names.get(cid, cid)}  [{type(r).__name__}]", f"case:{cid}")
            for cid, r in sorted(current.items())
        ]
        choices += [(f"Combination: {c.name}", f"combination:{c.id}") for c in project.combinations]
        return choices

    def member_choices(self, project: Project | None) -> list[tuple[str, str]]:
        """Cases and combinations the member window can draw.

        Modal, pushover and transient cases are left out: the window shows
        static element forces and deformations, so offering them would only
        replace the curves with an empty panel.
        """
        if project is None:
            return []
        current = self.cases.current(project)
        names = case_names(project)
        choices = [
            (f"Case: {names.get(cid, cid)}  [Static]", f"case:{cid}")
            for cid, result in sorted(current.items())
            if isinstance(result, StaticResults)
        ]
        choices += [(f"Combination: {c.name}", f"combination:{c.id}") for c in project.combinations]
        return choices

    # ── the results on screen ────────────────────────────────────────
    def current_key(self) -> str:
        """The key of the result on screen, for the member window picker."""
        results = self.latest
        if isinstance(results, CombinationResults):
            return f"combination:{results.case_id}"
        if isinstance(results, StaticResults):
            return f"case:{results.case_id}"
        return ""

    def caption_for(self, project: Project | None, results: object) -> str:
        """One line naming ``results``, for the viewport's top-left."""
        if isinstance(results, CombinationResults):
            kind = "envelope" if not results.single_valued else "combination"
            return f"{results.combination_name}  ·  {kind}"
        case_id = getattr(results, "case_id", None)
        name = case_names(project).get(int(case_id), "") if case_id is not None else ""
        name = name or getattr(results, "case_name", "")
        if not name:
            name = f"case {case_id}"
        kind = type(results).__name__.removesuffix("Results")
        return f"{name}  ·  {kind}"

    def static(self, bound: str = "max") -> StaticResults | None:
        """The static result Display draws: a static case, or one bound of a combination."""
        results = self.latest
        if isinstance(results, StaticResults):
            return results
        if isinstance(results, CombinationResults):
            return results.bound(bound)
        return None

    def is_envelope(self) -> bool:
        """True when the shown result has a maximum and a minimum (two diagrams, two shapes)."""
        results = self.latest
        return isinstance(results, CombinationResults) and not results.single_valued

    def steps(self) -> int:
        """How many steps the shown result has (1 for a result without steps)."""
        return int(getattr(self.latest, "n_steps", 1) or 1)

    def diagram_data(self, project: Project | None, component: ForceComponent) -> DiagramData:
        """Diagram data of the shown result; an envelope draws its max and min together."""
        results = self.latest
        if project is not None and isinstance(results, CombinationResults) and self.is_envelope():
            return envelope_diagram_data(project, results.max, results.min, component)
        static = self.static()
        if project is None or static is None:
            return DiagramData(component, np.zeros(0, dtype=int), np.zeros(0), np.zeros(0), 0.0)
        # Stations read the case's loads back: only for a case's own results, not a combination's.
        return extract_diagram_data(
            project, static, component, stations=isinstance(results, StaticResults)
        )

    def reaction_rows(self, project: Project | None) -> list[ReactionRow]:
        """The reactions of the case on screen, or none when there are no results."""
        results = self.latest
        if project is None or results is None:
            return []
        return reaction_rows(project, getattr(results, "node_reaction", None))
