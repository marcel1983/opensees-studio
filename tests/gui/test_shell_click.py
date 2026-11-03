"""Clicking the face of a shell/quad selects the element.

Frames are picked by their screen-space lines; faces need their own
point-in-polygon test, otherwise a click in the middle of a shell falls through
to "empty space" and selects nothing.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from opensees_studio.core import (
    ElasticMembranePlateSection,
    Node,
    Project,
    ShellMITC4Element,
)
from opensees_studio.views.main_window import MainWindow


def _project() -> Project:
    return Project(
        ndm=3,
        ndf=6,
        nodes=[
            Node(id=1, coords=(0.0, 0.0, 0.0)),
            Node(id=2, coords=(4.0, 0.0, 0.0)),
            Node(id=3, coords=(4.0, 3.0, 0.0)),
            Node(id=4, coords=(0.0, 3.0, 0.0)),
        ],
        sections=[ElasticMembranePlateSection(id=1, E=30e9, nu=0.2, h=0.2)],
        elements=[ShellMITC4Element(id=7, nodes=(1, 2, 3, 4), section_id=1)],
    )


@pytest.mark.gui
def test_click_inside_a_shell_selects_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.show()
    qtbot.waitExposed(window)
    project = _project()
    window._vm.adopt(project)
    canvas = window._canvas
    canvas.view_isometric()
    canvas.render()
    qtbot.wait(50)

    centre = np.mean([node.coords for node in project.nodes], axis=0)
    display = canvas._project_to_display(np.asarray([centre], dtype=float))[0]
    dpr = canvas.devicePixelRatioF()
    point = QPoint(int(display[0] / dpr), int(canvas.height() - display[1] / dpr))

    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    assert canvas.selection.elements == frozenset({7})

    # A click away from the face must not select it. Keep this in the same
    # window: a second MainWindow with its own VTK context crashed the Windows
    # CI runner inside the Qt event loop.
    canvas.selection.clear()
    QTest.mouseClick(
        canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(5, 5),
    )
    assert canvas.selection.elements == frozenset()
