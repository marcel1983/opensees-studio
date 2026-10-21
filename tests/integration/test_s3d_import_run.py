"""A PORTICO model imported, scaled and solved by OpenSees.

The cantilevers check the translation end to end against closed form: a tip load
in each direction exercises the swap of PORTICO's local axes (its ``Iz`` is the
strong axis of a beam, OpenSees' ``Iy``), the shear areas and the unit factors.

The parity test solves PORTICO's own verification models and compares them with
the OpenSeesPy runs PORTICO publishes. Its files are not copied into this
repository: point ``PORTICO_CORE_DIR`` at a checkout of ``jpreyes/portico-core``
to run it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("openseespy")

from opensees_studio.core import ModalCase, UnitSystem
from opensees_studio.services.opensees_runner import OpenSeesRunner
from opensees_studio.services.s3d_import import import_s3d

E, G = 2.8e7, 1.2e7  # kN/m²
A, IZ, IY, J = 0.15, 3.125e-3, 1.125e-3, 2.0e-3  # m², m⁴ (PORTICO axes: Iz strong)
AVY, AVZ = 0.125, 0.10
L, P = 4.0, 10.0  # m, kN


def _cantilever(mode: str, load: list[float]) -> dict[str, Any]:
    free = {"ux": 0, "uy": 0, "uz": 0, "rx": 0, "ry": 0, "rz": 0}
    return {
        "units": "kN-m",
        "mode": mode,
        "nodes": [
            {"id": 1, "x": 0, "y": 0, "z": 0, "restraints": dict.fromkeys(free, 1)},
            {"id": 2, "x": L, "y": 0, "z": 0, "restraints": free},
        ],
        "elements": [{"id": 1, "n1": 1, "n2": 2, "matId": 1, "secId": 1}],
        "materials": [{"id": 1, "name": "M", "E": E, "G": G, "nu": 0.2, "rho": 0}],
        "sections": [
            {"id": 1, "name": "S", "A": A, "Iz": IZ, "Iy": IY, "J": J, "Avy": AVY, "Avz": AVZ}
        ],
        "loadCases": [
            {
                "id": 1,
                "name": "TIP",
                "type": "static",
                "loads": [{"type": "nodal", "nodeId": 2, "F": load}],
            }
        ],
    }


def _tip(path: Path, data: dict[str, Any], units: UnitSystem) -> tuple[np.ndarray, Any]:
    path.write_text(json.dumps(data), encoding="utf-8")
    imported = import_s3d(path, units=units)
    project = imported.project
    results = OpenSeesRunner(project).run(project.analyses[0])
    return results.node_disp[2][-1], imported.scale


def _timoshenko(inertia: float, shear_area: float) -> float:
    return P * L**3 / (3 * E * inertia) + P * L / (G * shear_area)


def test_vertical_tip_load_bends_about_portico_strong_axis(tmp_path: Path) -> None:
    disp, scale = _tip(
        tmp_path / "v.s3d", _cantilever("3D", [0, 0, -P, 0, 0, 0]), UnitSystem.SI_M_N
    )
    assert scale.force == 1000.0
    assert -disp[2] == pytest.approx(_timoshenko(IZ, AVY), rel=1e-9)


def test_lateral_tip_load_bends_about_portico_weak_axis(tmp_path: Path) -> None:
    disp, _ = _tip(tmp_path / "h.s3d", _cantilever("3D", [0, P, 0, 0, 0, 0]), UnitSystem.SI_M_N)
    assert disp[1] == pytest.approx(_timoshenko(IY, AVZ), rel=1e-9)


def test_a_2d_cantilever_in_millimetres(tmp_path: Path) -> None:
    disp, scale = _tip(
        tmp_path / "2d.s3d", _cantilever("2D", [0, 0, -P, 0, 0, 0]), UnitSystem.SI_MM_N
    )
    # 2D results are Ux, Uz, Ry; the deflection comes back in millimetres.
    assert -disp[1] / scale.length == pytest.approx(_timoshenko(IZ, AVY), rel=1e-9)


# ──────────────────── parity with PORTICO's own OpenSees runs ────────────────────
PORTICO = os.environ.get("PORTICO_CORE_DIR")

PARITY_CASES = {
    "1-005": "verif_1-005a_settlement",
    "1-014": "verif_1-014_modal_cantilever",
    "1-018": "verif_1-018_static_portal",
    "1-021": "verif_1-021_modal_bathe_wilson",
}


@pytest.mark.skipif(not PORTICO, reason="PORTICO_CORE_DIR points to no portico-core checkout")
@pytest.mark.parametrize("case", sorted(PARITY_CASES))
def test_matches_portico_opensees_runs(case: str) -> None:
    root = Path(str(PORTICO))
    reference = json.loads(
        (root / "tools" / "verif" / "opensees" / "results" / f"{case}.json").read_text()
    )
    imported = import_s3d(root / "examples" / f"{PARITY_CASES[case]}.s3d")
    project, scale = imported.project, imported.scale
    if reference["_meta"]["analysis"] == "modal":
        modal = ModalCase(
            id=project.next_analysis_id(), name="Modal", n_modes=len(reference["omega2"])
        )
        project.analyses.append(modal)
        results = OpenSeesRunner(project).run(modal)
        assert np.asarray(results.eigenvalues) == pytest.approx(reference["omega2"], rel=1e-8)
        return
    static = next(c for c in project.analyses if c.id == reference.get("lcId", 1))
    results = OpenSeesRunner(project).run(static)
    slots = [0, 2, 4] if project.ndm == 2 else list(range(6))
    for node, expected in reference["disp"].items():
        ours = results.node_disp[int(node)][-1]
        back = [ours[k] / (scale.length if slot < 3 else 1.0) for k, slot in enumerate(slots)]
        assert back == pytest.approx([expected[s] for s in slots], abs=1e-9)
    for node, expected in reference["reaction"].items():
        if int(node) not in results.node_reaction:
            continue
        ours = results.node_reaction[int(node)][-1]
        back = [
            ours[k] / (scale.force if slot < 3 else scale.moment) for k, slot in enumerate(slots)
        ]
        assert back == pytest.approx([expected[s] for s in slots], abs=1e-8)
