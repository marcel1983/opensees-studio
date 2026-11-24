"""Combinations analysed as cases of their own (``core.combination_cases``)."""

from __future__ import annotations

from opensees_studio.core.analysis import ModalCase, StaticCase
from opensees_studio.core.combination_cases import analysed_combinations
from opensees_studio.core.combinations import CombinationTerm, LoadCombination


def _cases() -> list:  # type: ignore[type-arg]
    return [
        StaticCase(id=1, name="DEAD", pattern_ids=[1], system="UmfPack"),
        StaticCase(id=2, name="WIND", pattern_ids=[2, 3], pattern_factors=[1.0, 0.5]),
        ModalCase(id=3, name="MODAL", n_modes=3),
    ]


def test_each_sum_of_static_cases_becomes_one_newton_case() -> None:
    combos = [
        LoadCombination(
            id=1,
            name="1.2D+1.6W",
            terms=[CombinationTerm(ref_id=1, factor=1.2), CombinationTerm(ref_id=2, factor=1.6)],
        ),
        LoadCombination(
            id=2,
            name="0.9D-1.0W",
            terms=[
                CombinationTerm(ref_id=1, factor=0.9),
                CombinationTerm(source="combination", ref_id=3, factor=-1.0),
            ],
        ),
        LoadCombination(id=3, name="W", terms=[CombinationTerm(ref_id=2)]),
        LoadCombination(
            id=4,
            name="ENV",
            combination_type="Envelope",
            terms=[CombinationTerm(source="combination", ref_id=i) for i in (1, 2)],
        ),
    ]
    out = analysed_combinations(_cases(), combos, first_case_id=10)

    assert [c.name for c in out.cases] == ["Comb: 1.2D+1.6W", "Comb: 0.9D-1.0W", "Comb: W"]
    first, second, _third = out.cases
    assert (first.id, first.pattern_ids, first.pattern_factors) == (10, [1, 2, 3], [1.2, 1.6, 0.8])
    assert first.algorithm == "Newton" and first.system == "UmfPack"  # the first term's solver
    # A nested combination and a negative factor: its patterns, reversed.
    assert second.pattern_ids == [1, 2, 3] and second.pattern_factors == [0.9, -1.0, -0.5]
    assert [c.terms for c in out.combinations[:3]] == [
        [CombinationTerm(ref_id=i, factor=1.0)] for i in (10, 11, 12)
    ]
    assert [c.name for c in out.combinations] == [c.name for c in combos]
    assert out.combinations[3] == combos[3]  # an envelope stays one
    assert out.notes == []


def test_a_combination_with_a_case_that_is_not_static_stays_a_sum() -> None:
    combos = [
        LoadCombination(
            id=1, name="D+MODAL", terms=[CombinationTerm(ref_id=1), CombinationTerm(ref_id=3)]
        )
    ]
    out = analysed_combinations(_cases(), combos, first_case_id=10, options={"system": "UmfPack"})
    assert out.cases == [] and out.combinations == combos
    assert "D+MODAL" in out.notes[0]


def test_options_override_the_solver_of_the_new_cases() -> None:
    combos = [LoadCombination(id=1, name="D", terms=[CombinationTerm(ref_id=1)])]
    out = analysed_combinations(
        _cases(), combos, first_case_id=5, options={"system": "BandGeneral", "max_iter": 80}
    )
    (case,) = out.cases
    assert (case.system, case.max_iter, case.algorithm) == ("BandGeneral", 80, "Newton")
