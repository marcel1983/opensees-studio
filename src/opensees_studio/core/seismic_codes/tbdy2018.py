"""TBDY 2018 §4.7, the equivalent seismic load method.

``Vt = m_t SaR(T) g >= 0.04 m_t I SDS g``, with ``SaR = Sae(T) / Ra(T)``,
``Ra = R/I`` for ``T > TB`` and ``D + (R/I - D) T / TB`` below. An extra
``ΔFN = 0.0075 N Vt`` acts at the top storey; the rest is shared as
``Fi = (Vt - ΔFN) mi Hi / Σ mj Hj``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

import numpy as np

from opensees_studio.core.response_spectrum import four_branch_spectrum
from opensees_studio.core.seismic_codes.base import (
    BaseShear,
    ElfError,
    ElfParameters,
    SeismicCode,
)
from opensees_studio.core.target_spectrum import TBDY_TL, tbdy2018_corner_periods

#: TBDY 2018 §4.7.3.4: (label, Ct for H in metres); T = Ct H^(3/4).
TBDY_PERIOD_SYSTEMS: dict[str, tuple[str, float]] = {
    "concrete_frame": ("Reinforced concrete frame", 0.1),
    "steel_frame": ("Steel frame", 0.08),
    "braced_ebf": ("Eccentrically braced steel frame", 0.07),
    "other": ("All other systems", 0.05),
}


def tbdy_sar(p: ElfParameters) -> tuple[float, float]:
    """TBDY 2018 reduced spectral acceleration SaR(T) (g) and Ra(T)."""
    if p.r <= 0.0 or p.importance <= 0.0 or p.overstrength_d <= 0.0:
        raise ElfError("R, I and D must be positive.")
    _ta, tb = tbdy2018_corner_periods(p.sds, p.sd1)
    sae = float(np.ravel(four_branch_spectrum(p.period, p.sds, p.sd1, p.tl))[0])
    ri = p.r / p.importance
    ra = ri if p.period > tb else p.overstrength_d + (ri - p.overstrength_d) * p.period / tb
    return sae / ra, ra


class Tbdy2018(SeismicCode):
    key = "tbdy2018"
    label = "TBDY 2018 §4.7"
    hazard = "spectral"
    inputs = frozenset({"sds", "sd1", "tl", "importance", "overstrength_d"})
    period_systems: ClassVar[Mapping[str, str]] = {
        key: entry[0] for key, entry in TBDY_PERIOD_SYSTEMS.items()
    }
    tl = TBDY_TL

    def approximate_period(self, system: str, height_m: float) -> float:
        _label, ct = TBDY_PERIOD_SYSTEMS[system]
        return float(ct * height_m**0.75)

    def base_shear(
        self, p: ElfParameters, weights: Sequence[float], heights: Sequence[float]
    ) -> BaseShear:
        total = float(sum(weights))
        sar, ra = tbdy_sar(p)
        shear = sar * total
        minimum = 0.04 * p.importance * p.sds * total
        why = f"SaR(T) = {sar:.4g} g with Ra(T) = {ra:.4g}"
        if shear < minimum:
            shear, why = minimum, "the minimum 0.04 I SDS (Eq. 4.19)"
        top = 0.0075 * len(weights) * shear
        share = np.array([w * h for w, h in zip(weights, heights, strict=True)])
        forces = (shear - top) * share / share.sum()
        forces[-1] += top
        note = f"Vt by {why}; ΔFN = {top:.4g} at the top storey (Eq. 4.20)."
        return BaseShear(shear, forces, shear / total, note)


__all__ = ["TBDY_PERIOD_SYSTEMS", "Tbdy2018", "tbdy_sar"]
