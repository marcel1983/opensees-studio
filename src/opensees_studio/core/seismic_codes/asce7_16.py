"""ASCE/SEI 7-16 §12.8, the equivalent lateral force procedure.

``Cs = SDS / (R / Ie)``, capped by ``SD1 / (T (R/Ie))`` (``T <= TL``) or
``SD1 TL / (T² (R/Ie))`` (``T > TL``), and at least ``max(0.044 SDS Ie, 0.01)``
and, when ``S1 >= 0.6 g``, ``0.5 S1 / (R/Ie)``. ``V = Cs W``. Storey forces
``Fx = Cvx V`` with ``Cvx = wx hx^k / Σ wi hi^k``, ``k = 1`` for ``T <= 0.5 s``,
``2`` for ``T >= 2.5 s``, linear between (§12.8.3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

import numpy as np

from opensees_studio.core.seismic_codes.base import (
    BaseShear,
    ElfError,
    ElfParameters,
    SeismicCode,
)

#: ASCE 7-16 Table 12.8-2: (label, Ct for h in metres, x).
ASCE_PERIOD_SYSTEMS: dict[str, tuple[str, float, float]] = {
    "steel_mrf": ("Steel moment-resisting frame", 0.0724, 0.8),
    "concrete_mrf": ("Concrete moment-resisting frame", 0.0466, 0.9),
    "braced_ebf": ("Eccentrically braced / BRB frame", 0.0731, 0.75),
    "other": ("All other structural systems", 0.0488, 0.75),
}


def asce7_period(system: str, height_m: float) -> float:
    """Eq. 12.8-7: ``Ta = Ct hn^x``."""
    _label, ct, x = ASCE_PERIOD_SYSTEMS[system]
    return float(ct * height_m**x)


def asce7_cs(p: ElfParameters) -> tuple[float, str]:
    """ASCE 7-16 seismic response coefficient Cs and the clause that governs it."""
    ri = p.r / p.importance
    if p.r <= 0.0 or p.importance <= 0.0:
        raise ElfError("R and Ie must be positive.")
    cs = p.sds / ri
    why = "Eq. 12.8-2 (SDS / (R/Ie))"
    if p.period > 0.0:
        cap = p.sd1 / (p.period * ri) if p.period <= p.tl else p.sd1 * p.tl / (p.period**2 * ri)
        if cap < cs:
            cs, why = cap, ("Eq. 12.8-3 (T <= TL)" if p.period <= p.tl else "Eq. 12.8-4 (T > TL)")
    floor = max(0.044 * p.sds * p.importance, 0.01)
    if cs < floor:
        cs, why = floor, "Eq. 12.8-5 minimum (0.044 SDS Ie, at least 0.01)"
    if p.s1 >= 0.6:
        floor6 = 0.5 * p.s1 / ri
        if cs < floor6:
            cs, why = floor6, "Eq. 12.8-6 minimum (0.5 S1 / (R/Ie), S1 >= 0.6 g)"
    return cs, why


def asce7_k(period: float) -> float:
    """ASCE 7-16 §12.8.3 distribution exponent."""
    if period <= 0.5:
        return 1.0
    if period >= 2.5:
        return 2.0
    return 1.0 + (period - 0.5) / 2.0


class Asce716(SeismicCode):
    key = "asce7_16"
    label = "ASCE/SEI 7-16 §12.8"
    hazard = "spectral"
    inputs = frozenset({"sds", "sd1", "tl", "importance", "s1"})
    importance_label = "Ie"
    period_systems: ClassVar[Mapping[str, str]] = {
        key: entry[0] for key, entry in ASCE_PERIOD_SYSTEMS.items()
    }

    def approximate_period(self, system: str, height_m: float) -> float:
        return asce7_period(system, height_m)

    def base_shear(
        self, p: ElfParameters, weights: Sequence[float], heights: Sequence[float]
    ) -> BaseShear:
        cs, why = asce7_cs(p)
        shear = cs * float(sum(weights))
        k = asce7_k(p.period)
        share = np.array([w * h**k for w, h in zip(weights, heights, strict=True)])
        forces = shear * share / share.sum()
        return BaseShear(shear, forces, cs, f"Cs = {cs:.4g} by {why}; k = {k:.3g}.")


__all__ = ["ASCE_PERIOD_SYSTEMS", "Asce716", "asce7_cs", "asce7_k", "asce7_period"]
