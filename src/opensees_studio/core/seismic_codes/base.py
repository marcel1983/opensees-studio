"""What a seismic code is to the equivalent lateral force generator.

A code is one object: how it turns the engineer's numbers into a base shear
and shares it between the storeys, the empirical period it gives, the height
it allows the static method for, and which of the numbers it reads (so a
dialog asks for those and no others). ``core.equivalent_lateral`` gathers the
storeys and their weights, which no code changes, and hands them over.

This module is part of ``core``: no Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar, Literal

import numpy as np

from opensees_studio.core.target_spectrum import TBDY_TL

Hazard = Literal["spectral", "a0"]


class ElfError(ValueError):
    """The model or the parameters cannot give an ELF distribution."""


@dataclass(frozen=True)
class ElfParameters:
    """What the engineer gives the generator."""

    code: str
    """Key of the code in ``seismic_codes.SEISMIC_CODES``."""
    period: float
    """Fundamental period T in the direction, seconds."""
    sds: float
    sd1: float
    r: float
    """Response modification (ASCE R) or load reduction (TBDY R) coefficient."""
    importance: float = 1.0
    """ASCE Ie or TBDY I."""
    tl: float = TBDY_TL
    s1: float = 0.0
    """ASCE mapped S1 (g), for the §12.8-6 minimum; 0 leaves it out."""
    overstrength_d: float = 2.0
    """TBDY D (overstrength), for Ra(T) below TB."""
    eccentricity_ratio: float = 0.05
    """Accidental eccentricity as a fraction of the floor extent (3D)."""
    a0: float = 0.0
    """RNC-07 / NSCM peak ground acceleration a0 (g)."""
    soil: str = ""
    """RNC-07 soil type I-III or NSCM site class A-D."""
    importance_class: str = ""
    """RNC-07 group A-C or NSCM risk category I-IV ("" = B / II)."""
    zone: str = ""
    """RNC-07 Fig. 2 zone for Tabla 2 ("" = from a0)."""
    regularity: str = "regular"
    """RNC-07 Art. 23 regularity, for Q'."""
    use_period: bool = False
    """RNC-07: reduce the forces with the period (Art. 32 b, Ec. 13)."""
    approximate_period: float = 0.0
    """NSCM Ta (s): when positive, T is capped at Cu Ta (Sec. 8.2.1.5)."""


@dataclass(frozen=True)
class BaseShear:
    """What a code makes of the storey weights."""

    shear: float
    forces: np.ndarray
    """One force per storey, lowest first; they add up to ``shear``."""
    coefficient: float
    """``shear`` over the total weight (ASCE Cs, RNC-07 c, TBDY Vt / W)."""
    note: str
    """The governing clause, for the dialog."""


class SeismicCode:
    """One code of the equivalent lateral force method.

    A new code is a subclass in a module of its own, an entry in
    ``seismic_codes.SEISMIC_CODES`` and a test against a worked example of the
    code: nothing else branches on the key.
    """

    key: ClassVar[str]
    label: ClassVar[str]
    hazard: ClassVar[Hazard]
    """``"spectral"``: SDS and SD1 describe the site; ``"a0"``: a0 and a soil class."""
    inputs: ClassVar[frozenset[str]]
    """The fields of :class:`ElfParameters` the code reads, besides the period,
    ``r`` and the eccentricity every code takes."""
    r_label: ClassVar[str] = "R"
    importance_label: ClassVar[str] = "I"
    eccentricity_ratio: ClassVar[float] = 0.05
    """The accidental eccentricity the code asks for, as a fraction of the floor."""
    period_systems: ClassVar[Mapping[str, str]] = {}
    """Structural systems of the empirical period, key to label; empty when the
    code gives no empirical period."""
    soils: ClassVar[tuple[str, ...]] = ()
    default_soil: ClassVar[str] = ""
    importance_classes: ClassVar[tuple[str, ...]] = ()
    default_importance_class: ClassVar[str] = ""
    tl: ClassVar[float | None] = None
    """The long-period corner TL (s) when the code fixes it."""

    def check_hazard(self, p: ElfParameters) -> None:
        """Refuse parameters that do not describe a site."""
        if self.hazard == "a0":
            if p.a0 <= 0.0 or not p.soil:
                raise ElfError("a0 and the soil type must be given.")
        elif p.sds <= 0.0 or p.sd1 <= 0.0:
            raise ElfError("SDS and SD1 must be positive.")

    def approximate_period(self, system: str, height_m: float) -> float:
        """The empirical period (s) of a building ``height_m`` metres tall."""
        raise NotImplementedError

    def base_shear(
        self, p: ElfParameters, weights: Sequence[float], heights: Sequence[float]
    ) -> BaseShear:
        """The base shear and one force per storey (lowest first)."""
        raise NotImplementedError

    def height_limit(self, p: ElfParameters) -> tuple[float, str] | None:
        """Largest height (m) the code allows the static method for, and the clause."""
        return None


__all__ = ["BaseShear", "ElfError", "ElfParameters", "Hazard", "SeismicCode"]
