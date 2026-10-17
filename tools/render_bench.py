"""Render benchmark: geometry build time and draw calls for synthetic models.

The renderer builds every category from the project on each render, so the cost
that scales with the model is CPU work (PolyData construction, glyphing) plus
the number of actors VTK has to draw. Both are measurable without a GPU: this
drives :class:`ModelRenderer` against a plotter that records the calls instead
of opening an OpenGL context, which is what lets the budget test run in CI.

    python tools/render_bench.py            # table
    python tools/render_bench.py --json     # machine-readable, for the budget test

`tests/tools/test_render_budget.py` reads `tools/render-budget.txt` and fails
when a model needs more actors or more time than recorded there. The budget is a
ratchet: lower it in the commit that improves the numbers.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    Node,
    Project,
)
from opensees_studio.views.canvas3d.model_renderer import ModelRenderer


class RecordingPlotter:
    """A plotter that counts the actors and labels instead of drawing them."""

    def __init__(self) -> None:
        self.meshes = 0
        self.labels = 0

    def add_mesh(self, *_args: Any, **_kwargs: Any) -> object:
        self.meshes += 1
        return object()

    def add_point_labels(self, *_args: Any, **_kwargs: Any) -> object:
        self.labels += 1
        return object()

    def remove_actor(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def enable_anti_aliasing(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def render(self) -> None:
        return None

    def __getattr__(self, _name: str) -> Any:
        """Any other plotter call is a no-op: this measures the CPU side only."""
        return lambda *_args, **_kwargs: None


@dataclass(frozen=True)
class BenchResult:
    """One measurement: a model size and what it cost to build."""

    name: str
    nodes: int
    frames: int
    build_ms: float
    actors: int
    labels: int


def build_model(nx: int, ny: int, nz: int, *, restrained: bool = False) -> Project:
    """A full grid of nodes joined along the three axes by elastic frames.

    ``restrained`` fixes the base level, which is what makes the supports path
    matter: one support glyph per node is where the draw calls multiply.
    """
    nodes: list[Node] = []
    index: dict[tuple[int, int, int], int] = {}
    node_id = 1
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                index[(i, j, k)] = node_id
                restraint = (True,) * 6 if restrained and k == 0 else (False,) * 6
                nodes.append(
                    Node(id=node_id, coords=(float(i), float(j), float(k)), restraint=restraint)
                )
                node_id += 1

    elements: list[ElasticBeamColumn] = []
    element_id = 1
    for (i, j, k), start in index.items():
        for step in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            end = index.get((i + step[0], j + step[1], k + step[2]))
            if end is not None:
                elements.append(
                    ElasticBeamColumn(id=element_id, nodes=(start, end), section_id=1)
                )
                element_id += 1

    return Project(
        nodes=nodes,
        sections=[
            ElasticSection(
                id=1,
                name="Bench",
                E=200e9,
                A=0.01,
                Iz=1e-4,
                Iy=1e-4,
                G=80e9,
                J=1e-6,
            )
        ],
        elements=elements,
    )


def measure(project: Project, name: str) -> BenchResult:
    """Build the scene for ``project`` once and report time, actors and labels."""
    plotter = RecordingPlotter()
    renderer = ModelRenderer(plotter)
    started = time.perf_counter()
    renderer.render(project)
    build_ms = (time.perf_counter() - started) * 1000.0
    return BenchResult(
        name=name,
        nodes=len(project.nodes),
        frames=len(project.elements),
        build_ms=round(build_ms, 1),
        actors=plotter.meshes,
        labels=plotter.labels,
    )


#: The models the benchmark and the budget test use: (label, nx, ny, nz, restrained).
MODELS: tuple[tuple[str, int, int, int, bool], ...] = (
    ("grid-6x6x3", 6, 6, 3, False),
    ("grid-6x6x3-supported", 6, 6, 3, True),
    ("grid-10x10x5-supported", 10, 10, 5, True),
)


def run() -> list[BenchResult]:
    """Measure every model in :data:`MODELS`."""
    results: list[BenchResult] = []
    for label, nx, ny, nz, restrained in MODELS:
        results.append(measure(build_model(nx, ny, nz, restrained=restrained), label))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    args = parser.parse_args(argv)

    results = run()
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
        return 0

    print(f"{'model':26} {'nodes':>6} {'frames':>7} {'build ms':>9} {'actors':>7} {'labels':>7}")
    for result in results:
        print(
            f"{result.name:26} {result.nodes:6d} {result.frames:7d} "
            f"{result.build_ms:9.1f} {result.actors:7d} {result.labels:7d}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
