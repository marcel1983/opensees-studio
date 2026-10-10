"""Self weight of the frames and the shells.

A load pattern with a ``self_weight`` multiplier carries, on top of its own
loads, the weight of every frame and shell whose section has a unit weight,
acting downward — global -Z in a 3D model, -Y in a 2D one (the canvas
convention: Z up in 3D, the XY plane in 2D).

Frames: ``gamma * A`` per unit length, as a uniform element load.

OpenSees takes a ``-beamUniform`` load in the element's *local* axes, so the
downward vector is split over local x / y / z here, with the axes the runner
builds the transformation from (:mod:`core.geometry.local_axes`). A column then
takes its weight as an axial load and a sloped rafter as an axial part and a
transverse part.

Shells: ``gamma * h`` per unit area of a ``ShellMITC4`` with an
:class:`ElasticMembranePlateSection`, as **consistent nodal forces** — node i
takes ``q * integral(N_i dA)`` over the real (possibly warped, non-rectangular)
quadrilateral, integrated with 2 x 2 Gauss points, which is exact for the
bilinear shape. A rectangle gives a quarter of its weight to each corner.

Covered: frames that reference a single :class:`ElasticSection`
(``ElasticBeamColumn``, ``ForceBeamColumn``, ``DispBeamColumn``) and
``ShellMITC4`` shells. A fiber or aggregated section, a ``BeamWithHinges``, a
truss and a 2D quad carry no self weight yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from opensees_studio.core.geometry.elements import FRAME_ELEMENT_CLASSES, ShellMITC4Element
from opensees_studio.core.geometry.local_axes import frame_local_axes
from opensees_studio.core.loads import UniformElementLoad
from opensees_studio.core.sections import ElasticMembranePlateSection, ElasticSection

if TYPE_CHECKING:
    from opensees_studio.core.project import Project


def gravity_direction(ndm: int) -> np.ndarray:
    """Unit vector of gravity: -Y in 2D, -Z in 3D."""
    return np.array([0.0, -1.0, 0.0]) if ndm == 2 else np.array([0.0, 0.0, -1.0])


def weight_per_length(project: Project, element: object) -> float:
    """``gamma * A`` of a frame, 0 when it has no section with a unit weight."""
    section_id = getattr(element, "section_id", None)
    if section_id is None or not isinstance(element, FRAME_ELEMENT_CLASSES):
        return 0.0
    section = next((s for s in project.sections if s.id == section_id), None)
    if not isinstance(section, ElasticSection):
        return 0.0
    return section.unit_weight * section.A


def self_weight_loads(project: Project, multiplier: float = 1.0) -> list[UniformElementLoad]:
    """One uniform load per weighted frame, in its local axes, scaled by ``multiplier``."""
    if multiplier == 0.0:
        return []
    coords = {node.id: node.coords for node in project.nodes}
    down = gravity_direction(project.ndm)
    loads: list[UniformElementLoad] = []
    for element in project.elements:
        w = weight_per_length(project, element) * multiplier
        if w == 0.0 or len(element.nodes) != 2:
            continue
        axes = frame_local_axes(project.ndm, coords[element.nodes[0]], coords[element.nodes[1]])
        if axes is None:
            continue
        x, y, z = axes
        loads.append(
            UniformElementLoad(
                element_id=element.id,
                wx=float(w * (down @ x)),
                wy=float(w * (down @ y)),
                wz=float(w * (down @ z)),
            )
        )
    return loads


# ──────────────────────────── shells ────────────────────────────
_GAUSS = (-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0))
_CORNERS = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))


def weight_per_area(project: Project, element: object) -> float:
    """``gamma * h`` of a shell, 0 when it is not a weighted ``ShellMITC4``."""
    if not isinstance(element, ShellMITC4Element):
        return 0.0
    section = next((s for s in project.sections if s.id == element.section_id), None)
    if not isinstance(section, ElasticMembranePlateSection):
        return 0.0
    return section.unit_weight * section.h


def quad_tributary_areas(points: np.ndarray) -> np.ndarray:
    """``integral(N_i dA)`` for the four corners of a bilinear quad (4 x 3 points).

    The four values add up to the quad's area, also when it is warped.
    """
    shares = np.zeros(4)
    for xi in _GAUSS:
        for eta in _GAUSS:
            n = np.array([0.25 * (1 + a * xi) * (1 + b * eta) for a, b in _CORNERS])
            dn_dxi = np.array([0.25 * a * (1 + b * eta) for a, b in _CORNERS])
            dn_deta = np.array([0.25 * b * (1 + a * xi) for a, b in _CORNERS])
            jacobian = float(np.linalg.norm(np.cross(dn_dxi @ points, dn_deta @ points)))
            shares += n * jacobian  # Gauss weights are 1
    return shares


def shell_self_weight_nodal_loads(
    project: Project, multiplier: float = 1.0
) -> dict[int, np.ndarray]:
    """Node id -> global force vector (Fx, Fy, Fz) of the shells' weight, summed per node."""
    if multiplier == 0.0:
        return {}
    coords = {node.id: np.asarray(node.coords, dtype=float) for node in project.nodes}
    down = gravity_direction(project.ndm)
    forces: dict[int, np.ndarray] = {}
    for element in project.elements:
        q = weight_per_area(project, element) * multiplier
        if q == 0.0:
            continue
        points = np.array([coords[node_id] for node_id in element.nodes])
        for node_id, share in zip(element.nodes, quad_tributary_areas(points), strict=True):
            forces[node_id] = forces.get(node_id, np.zeros(3)) + q * share * down
    return forces


def is_weighted(project: Project, element: object) -> bool:
    """Whether a self-weight pattern loads ``element`` (a weighted frame or shell)."""
    return bool(weight_per_length(project, element) or weight_per_area(project, element))


def total_self_weight(project: Project) -> float:
    """Total weight of the weighted frames and shells (a check value)."""
    coords = {node.id: np.asarray(node.coords, dtype=float) for node in project.nodes}
    total = 0.0
    for element in project.elements:
        w = weight_per_length(project, element)
        if w and len(element.nodes) == 2:
            i, j = element.nodes
            total += w * float(np.linalg.norm(coords[j] - coords[i]))
        q = weight_per_area(project, element)
        if q:
            points = np.array([coords[node_id] for node_id in element.nodes])
            total += q * float(quad_tributary_areas(points).sum())
    return total
