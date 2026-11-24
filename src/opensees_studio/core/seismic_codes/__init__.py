"""The seismic codes of the equivalent lateral force method, one module each.

``SEISMIC_CODES`` is the registry: ``core.equivalent_lateral`` and the Seismic
Loads dialog ask it, and neither branches on a code's key. Adding a code is a
module here with a :class:`SeismicCode`, its entry below, and a test against a
worked example of the code.
"""

from __future__ import annotations

from opensees_studio.core.seismic_codes.asce7_16 import Asce716
from opensees_studio.core.seismic_codes.base import (
    BaseShear,
    ElfError,
    ElfParameters,
    SeismicCode,
)
from opensees_studio.core.seismic_codes.nscm2021 import Nscm2021
from opensees_studio.core.seismic_codes.rnc07 import Rnc07
from opensees_studio.core.seismic_codes.tbdy2018 import Tbdy2018

#: Every code, in the order a list offers them.
SEISMIC_CODES: dict[str, SeismicCode] = {
    code.key: code for code in (Asce716(), Tbdy2018(), Rnc07(), Nscm2021())
}


def seismic_code(key: str) -> SeismicCode:
    """The code registered under ``key``.

    Raises:
        ElfError: when no code has that key.
    """
    try:
        return SEISMIC_CODES[key]
    except KeyError:
        raise ElfError(f"Unknown seismic code {key!r}.") from None


__all__ = [
    "SEISMIC_CODES",
    "BaseShear",
    "ElfError",
    "ElfParameters",
    "SeismicCode",
    "seismic_code",
]
