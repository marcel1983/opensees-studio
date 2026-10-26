"""The truss scratch matrix is cleared before a 2D ndf-3 model is built.

OpenSeesPy's ``truss`` keeps one class-wide force vector and stiffness matrix
per DOF count. A 3D truss with ndf 3 and a 2D truss with ndf 3 share those
buffers, and the 2D element leaves their rotation rows behind. The runner must
run a small 3D bar first to overwrite every entry before building such a model.
This test drives the command sequence with a fake solver module, so it needs no
OpenSees installation.
"""

from __future__ import annotations

from types import ModuleType
from unittest.mock import Mock

from opensees_studio.core import ElasticUniaxial, Node, Project, TrussElement
from opensees_studio.services.opensees_runner import OpenSeesRunner


class _FakeOps(ModuleType):
    """A real module type so the runner's real-solver guard accepts it."""

    def __getattr__(self, name: str) -> Mock:
        value = Mock()
        setattr(self, name, value)
        return value


def _project(ndm: int, ndf: int) -> Project:
    return Project(
        ndm=ndm,
        ndf=ndf,
        nodes=[Node(id=1, coords=(0.0, 0.0, 0.0)), Node(id=2, coords=(4.0, 0.0, 0.0))],
        materials=[ElasticUniaxial(id=1, E=200e9)],
        elements=[TrussElement(id=1, nodes=(1, 2), area=0.01, material_id=1)],
    )


def test_a_2d_ndf3_truss_model_clears_the_shared_truss_scratch() -> None:
    ops = _FakeOps("fake_ops")
    runner = OpenSeesRunner(_project(2, 3), ops_module=ops)

    runner.build()

    # The scratch step writes a 3D bar, then the real model is wiped and built.
    assert ops.model.call_count == 2
    assert ops.element.call_count == 2
    assert ops.analysis.call_count == 1


def test_a_3d_model_does_not_clear_the_scratch() -> None:
    ops = _FakeOps("fake_ops")
    runner = OpenSeesRunner(_project(3, 3), ops_module=ops)

    runner.build()

    assert ops.model.call_count == 1
    assert ops.element.call_count == 1
