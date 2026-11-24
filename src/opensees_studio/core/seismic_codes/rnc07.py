"""RNC-07 Art. 32 (Nicaragua), the static method.

``Fi = c W0 Wi hi / Σ Wi hi`` with the seismic coefficient of
:func:`core.rnc07.static_coefficient` (Ec. 3, or Ec. 13 with the period), Group
A times 1.5. Accidental eccentricity is 0.1 b (Ec. 15).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from opensees_studio.core import rnc07
from opensees_studio.core.seismic_codes.base import (
    BaseShear,
    ElfError,
    ElfParameters,
    SeismicCode,
)


def rnc07_coefficient(p: ElfParameters) -> rnc07.Rnc07Coefficient:
    """RNC-07 seismic coefficient of Art. 24 / 32 (Group factor included)."""
    try:
        zone = p.zone or rnc07.zone_for_a0(p.a0)
        s = rnc07.soil_factor(zone, p.soil)
        return rnc07.static_coefficient(
            p.a0,
            s,
            p.r,
            group=p.importance_class or "B",
            regularity=p.regularity,
            period=p.period if p.use_period else None,
        )
    except rnc07.Rnc07Error as exc:
        raise ElfError(str(exc)) from exc


class Rnc07(SeismicCode):
    key = "rnc07"
    label = "RNC-07 Nicaragua Art. 32"
    hazard = "a0"
    inputs = frozenset({"a0", "soil", "importance_class", "regularity", "zone", "use_period"})
    r_label = "Q (Art. 21)"
    eccentricity_ratio = 0.10
    soils = ("I", "II", "III")
    default_soil = "II"
    importance_classes = ("A", "B", "C")
    default_importance_class = "B"

    def approximate_period(self, system: str, height_m: float) -> float:
        raise ElfError(
            "RNC-07 gives no empirical period: use the modal period or Rayleigh's "
            "formula (Art. 32 b, Ec. 12)."
        )

    def base_shear(
        self, p: ElfParameters, weights: Sequence[float], heights: Sequence[float]
    ) -> BaseShear:
        found = rnc07_coefficient(p)
        shear = found.c * float(sum(weights))
        share = np.array([w * h for w, h in zip(weights, heights, strict=True)])
        forces = shear * share / share.sum()
        return BaseShear(shear, forces, found.c, f"c = {found.c:.4g} by {found.why}.")

    def height_limit(self, p: ElfParameters) -> tuple[float, str] | None:
        if p.regularity == "regular":
            return (40.0, "RNC-07 Art. 30 b, regular")
        return (30.0, "Art. 30 b, irregular")


__all__ = ["Rnc07", "rnc07_coefficient"]
