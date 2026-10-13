"""Static stability check: is the model's stiffness matrix singular, and where?

The model is built exactly as an analysis would build it (:class:`OpenSeesRunner`
``build``), its tangent stiffness ``K`` is assembled once with the dense
``FullGeneral`` system and read back with ``printA``, and the singular value
decomposition of ``K`` gives its null space: each null vector is a
**mechanism**, a motion of the free DOFs that costs no strain energy. A stable
model has none.

Two kinds of trouble are told apart:

- a free DOF that no element stiffens at all (``uncovered``, the runner's own
  pre-run check), typically a truss node in a frame model or a released joint;
- a mechanism of the assembled structure: a missing support, a frame without
  bracing or with too many hinges, a node that is connected along one line only.

Each mechanism names the nodes and DOFs that move the most in it, in the global
names of ``core.plane`` (a 2D model's DOFs are Ux, Uz and Ry).

This module calls OpenSees: run it in the analysis child process
(``python -m opensees_studio.run --check-stability``), never in the GUI.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from opensees_studio.core import Project
from opensees_studio.core.plane import dof_labels

RELATIVE_TOLERANCE = 1e-11
"""A singular value below this fraction of the largest one counts as zero."""

MAX_MECHANISMS = 6
"""Mechanisms reported in full; a model with more says how many there are."""

MAX_MOVERS = 8
"""Node DOFs listed per mechanism (the largest components)."""

SHOWN_FRACTION = 0.2
"""A DOF is listed when it moves at least this fraction of the largest motion."""


@dataclass
class Mover:
    """One node DOF taking part in a mechanism."""

    node: int
    dof: str
    amplitude: float
    """Signed share of the mechanism's largest component (-1 .. 1)."""


@dataclass
class Mechanism:
    """A zero-energy motion of the structure."""

    movers: list[Mover]
    singular_value: float
    """Relative to the largest singular value of K (0 for an exact mechanism)."""

    def describe(self) -> str:
        parts = [f"N{m.node} {m.dof} ({m.amplitude:+.2f})" for m in self.movers]
        return ", ".join(parts)


@dataclass
class StabilityReport:
    """What the check found; ``stable`` when there is nothing to report."""

    n_equations: int
    rank: int
    mechanisms: list[Mechanism] = field(default_factory=list)
    n_mechanisms: int = 0
    uncovered: list[str] = field(default_factory=list)
    """Free DOFs no element stiffens (the runner's own pre-run check)."""
    condition: float = 0.0
    """Largest over smallest nonzero singular value of K."""

    @property
    def stable(self) -> bool:
        return self.n_mechanisms == 0 and not self.uncovered

    @property
    def nodes(self) -> list[int]:
        """Every node a mechanism moves, for selecting them in the view."""
        out: list[int] = []
        for mech in self.mechanisms:
            for mover in mech.movers:
                if mover.node not in out:
                    out.append(mover.node)
        return out

    def summary(self) -> str:
        """A few lines for the log and the result dialog."""
        if self.stable:
            return (
                f"The model is statically stable: the stiffness matrix of its "
                f"{self.n_equations} free DOF(s) has full rank."
            )
        lines: list[str] = []
        if self.uncovered:
            lines.append("Free DOFs that no element stiffens:")
            lines += [f"  - {text}" for text in self.uncovered]
        if self.n_mechanisms:
            lines.append(
                f"The structure has {self.n_mechanisms} mechanism(s): the stiffness matrix "
                f"of its {self.n_equations} free DOF(s) has rank {self.rank}."
            )
            for k, mech in enumerate(self.mechanisms, start=1):
                lines.append(f"  {k}. moves {mech.describe()}")
            if self.n_mechanisms > len(self.mechanisms):
                lines.append(f"  … and {self.n_mechanisms - len(self.mechanisms)} more.")
            lines.append(
                "Add supports, bracing or members that stop these motions, or restrain "
                "the DOFs that nothing can carry."
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StabilityReport:
        mechanisms = [
            Mechanism(
                movers=[Mover(**m) for m in mech.get("movers", [])],
                singular_value=float(mech.get("singular_value", 0.0)),
            )
            for mech in data.get("mechanisms", [])
        ]
        return cls(
            n_equations=int(data.get("n_equations", 0)),
            rank=int(data.get("rank", 0)),
            mechanisms=mechanisms,
            n_mechanisms=int(data.get("n_mechanisms", 0)),
            uncovered=[str(t) for t in data.get("uncovered", [])],
            condition=float(data.get("condition", 0.0)),
        )


def _uncovered_dofs(runner: Any) -> list[str]:
    """The runner's pre-run check, as a list of 'Node n, DOF x: …' lines."""
    try:
        runner._check_dof_coverage()
    except RuntimeError as exc:
        return [line.strip() for line in str(exc).splitlines() if line.strip().startswith("Node ")]
    return []


def _stiffness(ops: Any) -> np.ndarray:
    """Assemble K once (a zero load step) and read it back."""
    ops.timeSeries("Constant", 999_999)
    ops.pattern("Plain", 999_999, 999_999)
    # Transformation eliminates every MP constraint (equalDOF, rigid links,
    # diaphragms), so K is over the independent DOFs only.
    ops.constraints("Transformation")
    ops.numberer("Plain")
    ops.system("FullGeneral")
    ops.test("NormDispIncr", 1e-8, 1)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 0.0)
    ops.analysis("Static")
    ops.analyze(1)  # a singular K fails the solve, but it was assembled first
    values = np.asarray(ops.printA("-ret"), dtype=float)
    n = math.isqrt(values.size)
    return values.reshape(n, n) if n else np.zeros((0, 0))


def check_stability(project: Project, ops_module: Any | None = None) -> StabilityReport:
    """Build ``project`` in OpenSees and look for mechanisms in its stiffness."""
    from opensees_studio.services.opensees_runner import OpenSeesRunner

    if ops_module is None:
        import openseespy.opensees as default_ops

        ops_module = default_ops
    runner = OpenSeesRunner(project, ops_module=ops_module)
    runner.build()
    uncovered = _uncovered_dofs(runner)
    ops = ops_module

    stiffness = _stiffness(ops)
    n = stiffness.shape[0]
    if n == 0:
        ops.wipe()
        return StabilityReport(n_equations=0, rank=0, uncovered=uncovered)

    # Which node DOF each equation is; hidden nodes (end releases) report as their joint.
    joint_of = {extra.tag: extra.joint for extra in runner._frame_plan.nodes}
    labels = dof_labels(project.ndm, project.ndf)
    equation: dict[int, tuple[int, str]] = {}
    for tag in [*(node.id for node in project.nodes), *joint_of]:
        for k, eq in enumerate(ops.nodeDOFs(tag)):
            if eq >= 0 and k < len(labels) and eq not in equation:
                equation[eq] = (joint_of.get(tag, tag), labels[k])
    ops.wipe()

    _, singular, vt = np.linalg.svd(stiffness)
    largest = float(singular[0]) if singular.size else 0.0
    if largest <= 0.0:
        null = list(range(n))
    else:
        null = [i for i, s in enumerate(singular) if s < RELATIVE_TOLERANCE * largest]
    rank = n - len(null)
    nonzero = [float(s) for s in singular if largest > 0 and s >= RELATIVE_TOLERANCE * largest]
    condition = (nonzero[0] / nonzero[-1]) if nonzero else 0.0

    mechanisms: list[Mechanism] = []
    for i in null[:MAX_MECHANISMS]:
        vector = vt[i]
        peak = float(np.max(np.abs(vector))) or 1.0
        order = np.argsort(-np.abs(vector))
        movers: list[Mover] = []
        for eq in order:
            share = float(vector[eq]) / peak
            if abs(share) < SHOWN_FRACTION or len(movers) >= MAX_MOVERS:
                break
            node, dof = equation.get(int(eq), (0, f"eq {int(eq)}"))
            movers.append(Mover(node=node, dof=dof, amplitude=round(share, 4)))
        relative = float(singular[i]) / largest if largest > 0 else 0.0
        mechanisms.append(Mechanism(movers=movers, singular_value=relative))
    return StabilityReport(
        n_equations=n,
        rank=rank,
        mechanisms=mechanisms,
        n_mechanisms=len(null),
        uncovered=uncovered,
        condition=condition,
    )
