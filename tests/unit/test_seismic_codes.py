"""The registry of seismic codes: each code is one object, and nothing else branches on it."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

import numpy as np
import pytest

from opensees_studio.core.equivalent_lateral import (
    CODE_LABELS,
    NICARAGUA_CODES,
    approximate_period,
    equivalent_lateral_forces,
    static_height_limit,
)
from opensees_studio.core.seismic_codes import (
    SEISMIC_CODES,
    BaseShear,
    ElfError,
    ElfParameters,
    SeismicCode,
    seismic_code,
)
from tests.unit.test_equivalent_lateral import _shear_building

_FIELDS = {f.name for f in dataclasses.fields(ElfParameters)}


def test_the_four_codes_in_the_order_the_dialog_lists_them() -> None:
    assert list(SEISMIC_CODES) == ["asce7_16", "tbdy2018", "rnc07", "nscm2021"]
    assert all(key == code.key for key, code in SEISMIC_CODES.items())
    assert {key: code.label for key, code in SEISMIC_CODES.items()} == CODE_LABELS
    assert frozenset({"rnc07", "nscm2021"}) == NICARAGUA_CODES


@pytest.mark.parametrize("code", list(SEISMIC_CODES.values()), ids=list(SEISMIC_CODES))
def test_a_code_reads_only_fields_that_exist_and_offers_its_defaults(code: SeismicCode) -> None:
    assert code.inputs <= _FIELDS
    assert code.hazard in ("spectral", "a0")
    if code.hazard == "a0":
        assert {"a0", "soil", "importance_class"} <= code.inputs
        assert code.default_soil in code.soils
        assert code.default_importance_class in code.importance_classes
    else:
        assert {"sds", "sd1"} <= code.inputs and not code.soils


def test_an_unknown_code_is_refused_by_name() -> None:
    with pytest.raises(ElfError, match="Unknown seismic code 'ubc97'"):
        seismic_code("ubc97")
    with pytest.raises(ElfError, match="Unknown seismic code"):
        approximate_period("ubc97", "other", 10.0, 1.0)


def test_the_empirical_period_and_the_height_limit_come_from_the_code() -> None:
    assert approximate_period("asce7_16", "steel_mrf", 10.0, 1.0) == pytest.approx(
        0.0724 * 10.0**0.8
    )
    assert approximate_period("nscm2021", "steel_mrf", 10.0, 1.0) == pytest.approx(
        0.0724 * 10.0**0.8
    )
    assert approximate_period("tbdy2018", "steel_frame", 16.0, 1.0) == pytest.approx(0.08 * 8.0)
    with pytest.raises(ElfError, match="RNC-07 gives no empirical period"):
        approximate_period("rnc07", "steel_mrf", 10.0, 1.0)
    with pytest.raises(ElfError, match="no height"):
        approximate_period("asce7_16", "steel_mrf", 0.0, 1.0)
    p = ElfParameters(code="rnc07", period=0.3, sds=0.0, sd1=0.0, r=2.0, regularity="irregular_one")
    assert static_height_limit(p) == (30.0, "Art. 30 b, irregular")
    assert static_height_limit(dataclasses.replace(p, code="asce7_16")) is None


class _Uniform(SeismicCode):
    """A code the generator has never heard of: the same force on every storey."""

    key = "uniform"
    label = "Uniform"
    hazard = "spectral"
    inputs = frozenset({"sds", "sd1"})

    def base_shear(
        self, p: ElfParameters, weights: Sequence[float], heights: Sequence[float]
    ) -> BaseShear:
        shear = 0.1 * float(sum(weights))
        forces = np.full(len(weights), shear / len(weights))
        return BaseShear(shear, forces, 0.1, "V = 0.1 W.")


def test_a_new_code_is_one_entry_in_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(SEISMIC_CODES, "uniform", _Uniform())
    p = ElfParameters(code="uniform", period=0.4, sds=1.0, sd1=0.6, r=1.0)

    result = equivalent_lateral_forces(_shear_building(), 0, p)

    assert result.code == "uniform" and result.coefficient == 0.1
    assert [lv.force for lv in result.levels] == pytest.approx([result.base_shear / 3] * 3)
    assert result.notes[0] == "V = 0.1 W."
    assert static_height_limit(p) is None
