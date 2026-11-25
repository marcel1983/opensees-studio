"""The load combinations of a generated warehouse, as the wizard shows and edits them.

The plan generates the combinations of the code (``generate_for_code``) on
the cases it creates, and keeps them in :attr:`WarehousePlan.code_combinations`
as :class:`PlannedCombination`: a name and a factor per load case *name*, since
the ids of the cases are only given when the plan is made. The wizard shows
those, the user changes a factor, drops a combination or adds one, and hands
the result back in ``WarehouseLoads.edited_combinations``; the plan then makes
those instead of the code's, with an envelope per set as before. Split out of
:mod:`opensees_studio.core.warehouse`.

No Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from opensees_studio.core.code_combinations import GeneratedCombination


def _refuse(message: str) -> NoReturn:
    from opensees_studio.core.warehouse import WarehouseError

    raise WarehouseError(message)


@dataclass(frozen=True)
class PlannedCombination:
    """A combination of the warehouse's load cases, named by case name."""

    name: str
    factors: tuple[tuple[str, float], ...]
    """``(load case name, factor)`` in the order the terms are written."""
    group: str = ""
    """The set it belongs to, whose envelope takes it ("" = the code's first set)."""

    def factor(self, case: str) -> float:
        """The factor of ``case``, 0 when it is not in the combination."""
        return sum(f for name, f in self.factors if name == case)

    def text(self) -> str:
        """``1.2 DEAD + 1.6 LIVE``: the combination as it reads."""
        parts = []
        for name, factor in self.factors:
            sign = "-" if factor < 0 else "+"
            parts.append(f"{sign} {abs(factor):g} {name}")
        return " ".join(parts).removeprefix("+ ")


def planned_combinations(
    generated: Sequence[GeneratedCombination], case_names: Mapping[int, str]
) -> list[PlannedCombination]:
    """The generated combinations of the code, by case name."""
    return [
        PlannedCombination(
            name=g.name,
            factors=tuple((case_names[t.ref_id], t.factor) for t in g.terms),
            group=g.group,
        )
        for g in generated
    ]


def generated_combinations(
    edited: Sequence[PlannedCombination], case_names: Mapping[int, str], default_group: str
) -> list[GeneratedCombination]:
    """``edited`` as combinations of the cases ``case_names`` lists.

    Raises:
        WarehouseError: for a combination without a name or a factor, two of
            one name, or a load case the warehouse does not have.
    """
    from opensees_studio.core.code_combinations import GeneratedCombination
    from opensees_studio.core.combinations import CombinationTerm

    ids = {name: case_id for case_id, name in case_names.items()}
    out: list[GeneratedCombination] = []
    seen: set[str] = set()
    for combination in edited:
        name = combination.name.strip()
        if not name:
            _refuse("Every combination needs a name.")
        if name in seen:
            _refuse(f"Two combinations are called {name!r}.")
        seen.add(name)
        terms = []
        for case, factor in combination.factors:
            if case not in ids:
                _refuse(f"The combination {name!r} takes {case!r}, which is not a load case here.")
            if factor != 0.0:
                terms.append(CombinationTerm(ref_id=ids[case], factor=factor))
        if not terms:
            _refuse(f"The combination {name!r} has no load case with a factor.")
        out.append(GeneratedCombination(name, terms, combination.group or default_group))
    return out


__all__ = ["PlannedCombination", "generated_combinations", "planned_combinations"]
