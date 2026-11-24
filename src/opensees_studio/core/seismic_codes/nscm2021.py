"""NSCM Managua 8.2.1, the equivalent lateral force method.

``Vb = Cs W`` with Cs of Ec. 8.2-2 and its minimum (Ec. 8.2-3), T capped at
Cu Ta, and the ASCE-style ``Cvx`` distribution with ``k`` from 1 to 2 (the
empirical period is ASCE's too). Accidental eccentricity 5 % (Sec. 9.8).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

import numpy as np

from opensees_studio.core import nscm
from opensees_studio.core.seismic_codes.asce7_16 import (
    ASCE_PERIOD_SYSTEMS,
    asce7_k,
    asce7_period,
)
from opensees_studio.core.seismic_codes.base import (
    BaseShear,
    ElfError,
    ElfParameters,
    SeismicCode,
)


def nscm_cs(p: ElfParameters) -> tuple[float, str, float]:
    """NSCM Cs (Ec. 8.2-2 / 8.2-3), which clause governs, and the period used."""
    try:
        site = nscm.NscmSite(
            a0=p.a0, site_class=p.soil, risk_category=p.importance_class or "II", r0=p.r
        )
        period = p.period
        if p.approximate_period > 0.0:
            period = min(period, site.cu * p.approximate_period)
        cs, why = site.seismic_coefficient(period)
    except nscm.NscmError as exc:
        raise ElfError(str(exc)) from exc
    return cs, why, period


class Nscm2021(SeismicCode):
    key = "nscm2021"
    label = "NSCM Managua 8.2.1"
    hazard = "a0"
    inputs = frozenset({"a0", "soil", "importance_class", "regularity", "approximate_period"})
    r_label = "Ro = R ΦP ΦE"
    period_systems: ClassVar[Mapping[str, str]] = {
        key: entry[0] for key, entry in ASCE_PERIOD_SYSTEMS.items()
    }
    soils = ("A", "B", "C", "D")
    default_soil = "D"
    importance_classes = tuple(nscm.NSCM_IMPORTANCE)
    default_importance_class = "II"

    def approximate_period(self, system: str, height_m: float) -> float:
        return asce7_period(system, height_m)

    def base_shear(
        self, p: ElfParameters, weights: Sequence[float], heights: Sequence[float]
    ) -> BaseShear:
        cs, why, period = nscm_cs(p)
        shear = cs * float(sum(weights))
        k = asce7_k(period)
        share = np.array([w * h**k for w, h in zip(weights, heights, strict=True)])
        forces = shear * share / share.sum()
        capped = f" (T capped at Cu·Ta = {period:.4g} s)" if period < p.period else ""
        return BaseShear(shear, forces, cs, f"Cs = {cs:.4g} by {why}{capped}; k = {k:.3g}.")

    def height_limit(self, p: ElfParameters) -> tuple[float, str] | None:
        if p.a0 <= 0.0:
            return None
        z1 = nscm.zone_for_a0(p.a0) == "Z1"
        if p.regularity == "regular":
            return (24.0 if z1 else 12.0, "NSCM 8.2.1.1, regular")
        return (12.0 if z1 else 6.0, "NSCM 8.2.1.1, irregular")


__all__ = ["Nscm2021", "nscm_cs"]
