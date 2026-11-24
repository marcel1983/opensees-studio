"""Load combinations analysed as cases of their own, for a model that does not superpose.

A combination is normally a sum of separate results. A model with tension-only
members is not linear: which diagonal of an X works depends on the whole load,
so ``1.2D + 1.6W`` is solved under the factored loads together, as SAP2000's
nonlinear static cases (or CYPE's per-combination analysis) do. Each
``LinearAdd`` combination of static cases becomes one
:class:`~opensees_studio.core.analysis.StaticCase` with its patterns and their
factors, solved by Newton iteration, and the combination keeps its name and
becomes that case alone, so envelopes and the design checks read it as before.

A combination with a term that is not a static case (a response spectrum, a
time history), or whose cases carry preloads, stays a sum and is reported.

No Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from opensees_studio.core.analysis import StaticCase
from opensees_studio.core.combinations import CombinationTerm, LoadCombination

#: Name of the case that analyses combination ``name``.
CASE_NAME = "Comb: {name}"


@dataclass
class AnalysedCombinations:
    """The cases to add and the combinations that now read them."""

    cases: list[StaticCase] = field(default_factory=list)
    combinations: list[LoadCombination] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _pattern_factors(
    combination: LoadCombination,
    cases: dict[int, Any],
    combinations: dict[int, LoadCombination],
    scale: float = 1.0,
    seen: frozenset[int] = frozenset(),
) -> dict[int, float] | None:
    """Pattern id → factor of a combination, or None when it is not a sum of static cases."""
    if combination.combination_type != "LinearAdd" or combination.id in seen:
        return None
    factors: dict[int, float] = {}
    for term in combination.terms:
        if term.source == "combination":
            inner = combinations.get(term.ref_id)
            if inner is None:
                return None
            nested = _pattern_factors(
                inner, cases, combinations, scale * term.factor, seen | {combination.id}
            )
            if nested is None:
                return None
            for pid, value in nested.items():
                factors[pid] = factors.get(pid, 0.0) + value
            continue
        case = cases.get(term.ref_id)
        if not isinstance(case, StaticCase) or case.preload_case_ids:
            return None
        for index, pid in enumerate(case.pattern_ids):
            factors[pid] = factors.get(pid, 0.0) + scale * term.factor * case.factor_of(index)
    return factors


def analysed_combinations(
    cases: Iterable[Any],
    combinations: Iterable[LoadCombination],
    *,
    first_case_id: int,
    options: Mapping[str, Any] | None = None,
) -> AnalysedCombinations:
    """One Newton static case per combination of static cases; the combinations rewritten.

    ``cases`` are every case the combinations may name (the project's and any
    planned with them). Each new case takes its solver (system, numberer,
    constraints, test) from the first static case the combination names;
    ``options`` overrides any field of the new cases (a faster ``system``).
    """
    by_id = {c.id: c for c in cases}
    combos = list(combinations)
    combo_by_id = {c.id: c for c in combos}
    out = AnalysedCombinations()
    next_id = first_case_id
    for combination in combos:
        factors = _pattern_factors(combination, by_id, combo_by_id) or {}
        pattern_ids = [pid for pid, f in factors.items() if f != 0.0]
        if not pattern_ids:
            if combination.combination_type == "LinearAdd":
                out.notes.append(
                    f"Combination '{combination.name}' is not analysed on its own (it names "
                    "a case that is not a plain static one): it stays a sum of results."
                )
            out.combinations.append(combination)
            continue
        template = next(
            (
                by_id[t.ref_id]
                for t in combination.terms
                if t.source == "case" and isinstance(by_id.get(t.ref_id), StaticCase)
            ),
            None,
        )
        fields: dict[str, Any] = {"algorithm": "Newton", "max_iter": 50}
        if template is not None:
            fields.update(
                system=template.system,
                numberer=template.numberer,
                constraints=template.constraints,
                test=template.test,
                tolerance=template.tolerance,
            )
        fields.update(options or {})
        case = StaticCase(
            id=next_id,
            name=CASE_NAME.format(name=combination.name),
            pattern_ids=pattern_ids,
            pattern_factors=[round(factors[pid], 12) for pid in pattern_ids],
            **fields,
        )
        next_id += 1
        out.cases.append(case)
        out.combinations.append(
            combination.model_copy(
                update={"terms": [CombinationTerm(source="case", ref_id=case.id, factor=1.0)]}
            )
        )
    return out


__all__ = ["CASE_NAME", "AnalysedCombinations", "analysed_combinations"]
