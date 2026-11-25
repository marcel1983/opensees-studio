"""The direct analysis method of AISC 360-16 Chapter C on a generated warehouse.

A second-order analysis does not superpose, so every combination of the code
(or of the wizard's Combinations page) is solved under its factored loads
together, as :mod:`opensees_studio.core.design.direct_analysis` does for the
ASCE 7 combinations of Design → Direct Analysis Method, with what C2 asks:

* **P-Delta** in every frame (C2.1), P-delta left to B1 in the member check;
* **stiffness × 0.8** (C2.3), τb = 1 with the additional notional load
  ``0.001 α Yi`` in every combination (C2.3(c));
* **notional loads** ``0.002 α Yi`` (C2.2b) in the gravity-only combinations,
  in each direction and sign: such a combination becomes four cases and the
  envelope of the four. A combination with wind or earthquake is one case, its
  τb notional load along its lateral load.

The combination keeps its name and reads its case(s), so the envelopes, the
results and the steel check (which takes the direct analysis cases as its
demands) work as before. Valid while Δ2/Δ1 <= 1.7 (C2.2b(d)), which the notes
ask to check. LRFD only (α = 1).

No Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from opensees_studio.core.analysis import DirectAnalysisTag, StaticCase
from opensees_studio.core.combination_cases import AnalysedCombinations
from opensees_studio.core.combinations import CombinationTerm, LoadCombination
from opensees_studio.core.design.direct_analysis import (
    DAM_STEPS,
    STIFFNESS_REDUCTION,
    TAU_B_NOTIONAL,
)
from opensees_studio.core.design.stability import ALPHA_LRFD, NOTIONAL_FRACTION

#: The directions a gravity-only combination takes its notional loads in.
NOTIONAL_DIRECTIONS: tuple[str, ...] = ("+X", "-X", "+Y", "-Y")


def _factors(
    combination: LoadCombination, cases: Mapping[int, Any]
) -> tuple[dict[int, float], list[tuple[int, float]]] | None:
    """Pattern id → factor, and the ``(case id, factor)`` terms; None if not a sum of static cases."""
    if combination.combination_type != "LinearAdd":
        return None
    factors: dict[int, float] = {}
    terms: list[tuple[int, float]] = []
    for term in combination.terms:
        case = cases.get(term.ref_id)
        if term.source != "case" or not isinstance(case, StaticCase) or case.preload_case_ids:
            return None
        terms.append((case.id, term.factor))
        for index, pid in enumerate(case.pattern_ids):
            factors[pid] = factors.get(pid, 0.0) + term.factor * case.factor_of(index)
    return factors, terms


def direct_analysis_combinations(
    cases: Iterable[Any],
    combinations: Iterable[LoadCombination],
    lateral: Mapping[int, tuple[str, float]],
    *,
    first_case_id: int,
    options: Mapping[str, Any] | None = None,
) -> AnalysedCombinations:
    """The second-order cases of every combination of static cases; the combinations rewritten.

    ``lateral`` maps a wind or earthquake case to the axis (``"X"``, ``"Y"``) and
    sign of the load it puts on the building; the term with the largest factor
    sets the direction of a combination's notional load. ``options`` overrides
    any field of the new cases (a faster ``system``).
    """
    by_id = {c.id: c for c in cases}
    out = AnalysedCombinations()
    next_id = first_case_id
    gravity_ratio = round((NOTIONAL_FRACTION + TAU_B_NOTIONAL) * ALPHA_LRFD, 12)
    lateral_ratio = round(TAU_B_NOTIONAL * ALPHA_LRFD, 12)
    for combination in combinations:
        found = _factors(combination, by_id)
        pattern_ids = [pid for pid, f in (found[0] if found else {}).items() if f != 0.0]
        if found is None or not pattern_ids:
            if combination.combination_type == "LinearAdd":
                out.notes.append(
                    f"Combination '{combination.name}' is not analysed to second order (it "
                    "names a case that is not a plain static one): it stays a sum of results."
                )
            out.combinations.append(combination)
            continue
        factors, terms = found
        template = by_id[terms[0][0]]
        fields: dict[str, Any] = {
            "system": template.system,
            "numberer": template.numberer,
            "constraints": template.constraints,
            "test": template.test,
            "tolerance": template.tolerance,
            "pattern_ids": pattern_ids,
            "pattern_factors": [round(factors[pid], 12) for pid in pattern_ids],
            "n_steps": DAM_STEPS,
            "load_factor_increment": 1.0 / DAM_STEPS,
            "algorithm": "Newton",
            "max_iter": 50,
            "p_delta": True,
            "stiffness_factor": STIFFNESS_REDUCTION,
            **(options or {}),
        }
        sideways = [(abs(f), cid, f) for cid, f in terms if cid in lateral and f != 0.0]
        if sideways:
            _size, case_id, factor = max(sideways)
            axis, sign = lateral[case_id]
            direction = f"{'+' if factor * sign > 0 else '-'}{axis}"
            case = StaticCase(
                id=next_id,
                name=f"DAM {combination.name}",
                notional_ratio=lateral_ratio,
                notional_direction=direction,  # type: ignore[arg-type]
                direct_analysis=DirectAnalysisTag(combination=combination.name, lateral=True),
                **fields,
            )
            next_id += 1
            out.cases.append(case)
            out.combinations.append(
                combination.model_copy(update={"terms": [CombinationTerm(ref_id=case.id)]})
            )
            continue
        own = []
        for direction in NOTIONAL_DIRECTIONS:
            case = StaticCase(
                id=next_id,
                name=f"DAM {combination.name} N{direction}",
                notional_ratio=gravity_ratio,
                notional_direction=direction,  # type: ignore[arg-type]
                direct_analysis=DirectAnalysisTag(combination=combination.name),
                **fields,
            )
            next_id += 1
            out.cases.append(case)
            own.append(CombinationTerm(ref_id=case.id))
        out.combinations.append(
            combination.model_copy(update={"combination_type": "Envelope", "terms": own})
        )
    out.notes.append(
        "AISC 360-16 Chapter C, direct analysis: each combination solved to second order "
        "(P-Delta, Newton), stiffness x0.8 (C2.3), the notional load 0.001 alpha Yi of "
        "C2.3(c) in every combination and 0.002 alpha Yi (C2.2b) in each direction of the "
        "gravity-only ones. Valid while the second- to first-order drift ratio stays at or "
        "below 1.7 (C2.2b(d)): check it, or use Design → Direct Analysis Method."
    )
    return out


__all__ = ["NOTIONAL_DIRECTIONS", "direct_analysis_combinations"]
