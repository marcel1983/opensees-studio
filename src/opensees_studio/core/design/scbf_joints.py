"""AISC 341-22 F2.6b: SCBF beam-to-column connection moment demand.

Where a brace or gusset plate connects to both members of a beam-to-column
joint, the connection must either be a simple connection with 0.025 rad of
rotation or resist a moment equal to the lesser of

* ``1.1 Ry Mp`` of the beam, divided by ``alpha_s``; and
* ``1.1`` times the sum of the expected column plastic moments
  ``sum(Ry Fy Z)``, divided by ``alpha_s``.

The function returns the two candidate moments and the required one, with the
calculation steps. It is a demand, not a pass/fail check: the connection
detail (simple, RBS or another prequalified moment connection) supplies the
available strength. No Qt, no OpenSees.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from opensees_studio.core.design.aisc341 import alpha_s
from opensees_studio.core.design.aisc360 import Method
from opensees_studio.core.design.calc import CalcStep

#: F2.6b(b): the expected moment is multiplied by 1.1.
MOMENT_FACTOR = 1.1


@dataclass(frozen=True)
class ScbfJointMoment:
    """The two candidate moments of F2.6b and the required one."""

    beam_moment: float
    """``1.1 Ry Fy_b Z_b / alpha_s``."""
    column_moment: float
    """``1.1 sum(Ry Fy_c Z_c) / alpha_s``."""
    required: float
    """The lesser of the two."""
    steps: tuple[CalcStep, ...] = field(default_factory=tuple)


def scbf_beam_column_moment(
    *,
    ry: float,
    beam_fy: float,
    beam_z: float,
    columns: Sequence[tuple[float, float]],
    method: Method = "LRFD",
) -> ScbfJointMoment:
    """F2.6b(b): the required moment of one SCBF beam-to-column connection.

    ``columns`` holds ``(Fy, Z)`` pairs for every column framing into the
    joint; the sum uses the expected plastic moment ``Ry Fy Z`` of each.
    """
    if ry <= 0.0 or beam_fy <= 0.0 or beam_z <= 0.0:
        raise ValueError("Ry, the beam Fy and Z must be positive.")
    if not columns or any(fy <= 0.0 or z <= 0.0 for fy, z in columns):
        raise ValueError("Every column needs a positive Fy and Z.")
    factor = alpha_s(method)
    beam = MOMENT_FACTOR * ry * beam_fy * beam_z / factor
    column_sum = sum(fy * z for fy, z in columns)
    column = MOMENT_FACTOR * ry * column_sum / factor
    required = min(beam, column)
    return ScbfJointMoment(
        beam,
        column,
        required,
        (
            CalcStep(
                "Beam expected moment",
                "1.1 Ry Fy_b Z_b / alpha_s",
                f"1.1 x {ry:g} x {beam_fy:g} x {beam_z:g} / {factor:g}",
                beam,
            ),
            CalcStep(
                "Column expected moment",
                "1.1 Ry sum(Fy_c Z_c) / alpha_s",
                f"1.1 x {ry:g} x {column_sum:g} / {factor:g}",
                column,
            ),
            CalcStep(
                "Required moment",
                "min(beam, columns)",
                f"min({beam:.6g}, {column:.6g})",
                required,
            ),
        ),
    )
