"""What counts as a click, and what counts as a camera drag.

The report — "no se puede dibujar nodos y elementos frame" — had a second cause
beyond the view jumping: a press/release pair was only accepted as a click when
the pointer moved **3 px or less**, so a hand that drifted a few pixels turned
every click into a (bogus) drag and nothing was drawn.

The camera decides now: if it did not move, the gesture was a click and it may
drift up to `CLICK_MAX_DRIFT_PX`; if it did move, the user was orbiting and no
pick is committed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest


@pytest.fixture
def canvas(qtbot):  # type: ignore[no-untyped-def]
    from opensees_studio.core import Project
    from opensees_studio.views.canvas3d.model_canvas import ModelCanvas

    widget = ModelCanvas()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.show()
    qtbot.waitExposed(widget)
    widget.show_project(Project())
    widget.view_xy()
    yield widget
    widget.close()


def _clicks(canvas) -> list[tuple]:  # type: ignore[no-untyped-def]
    seen: list[tuple] = []
    canvas.emptyClicked.connect(lambda *args: seen.append(args))
    return seen


def _press_release(canvas, start: QPoint, end: QPoint | None = None) -> None:  # type: ignore[no-untyped-def]
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    if end is not None:
        QTest.mouseMove(canvas, end)
    QTest.mouseRelease(
        canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        end or start,
    )


def test_a_clean_click_commits(canvas) -> None:  # type: ignore[no-untyped-def]
    seen = _clicks(canvas)
    _press_release(canvas, QPoint(400, 300))
    assert len(seen) == 1


def test_a_click_that_drifts_a_few_pixels_still_commits(canvas) -> None:  # type: ignore[no-untyped-def]
    """The bug: 5 px of hand jitter used to swallow the click entirely."""
    seen = _clicks(canvas)
    _press_release(canvas, QPoint(400, 300), QPoint(405, 302))
    assert len(seen) == 1


def test_a_drag_past_the_threshold_does_not_commit(canvas) -> None:  # type: ignore[no-untyped-def]
    """An orbit travels far more than the click budget, and keeps the new view."""
    seen = _clicks(canvas)
    _press_release(canvas, QPoint(400, 300), QPoint(460, 340))
    assert seen == []


def test_a_click_that_drifts_leaves_the_camera_untouched(canvas) -> None:  # type: ignore[no-untyped-def]
    """VTK rotates a little during the drift; a click must undo that."""
    before = tuple(canvas.camera.position)
    _press_release(canvas, QPoint(400, 300), QPoint(405, 302))
    after = tuple(canvas.camera.position)
    assert after == pytest.approx(before, abs=1e-9)


def test_a_large_jitter_without_camera_movement_is_a_drag(canvas) -> None:  # type: ignore[no-untyped-def]
    """The pixel bound stays as a guard: 20 px is a drag even if the camera held still."""
    from opensees_studio.views.canvas3d.model_canvas import CLICK_MAX_DRIFT_PX

    assert CLICK_MAX_DRIFT_PX < 20.0
    seen = _clicks(canvas)
    _press_release(canvas, QPoint(400, 300), QPoint(420, 310))
    assert seen == []


def test_a_drifting_click_draws_a_node_end_to_end(qtbot) -> None:  # type: ignore[no-untyped-def]
    """The whole path: arm Draw Node, click with a little drift, get a node."""
    from opensees_studio.views.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.show()
    qtbot.waitExposed(window)
    window._vm.new_project(ndm=2, ndf=3)

    canvas = window._canvas
    window._on_draw_node_tool()
    canvas.view_xy()

    centre = QPoint(canvas.width() // 2, canvas.height() // 2)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    QTest.mouseRelease(
        canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(centre.x() + 5, centre.y() + 2),
    )

    assert len(window._vm.project.nodes) >= 1
