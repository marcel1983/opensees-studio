"""A brand-new project has an empty grid, so there is nothing to snap to.

The canvas rejects off-grid clicks on purpose, which left Draw Node / Frame
/ Truss apparently dead on a fresh model with no hint about why. Arming one
of those tools must now offer to define a grid instead.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QMessageBox

from opensees_studio.commands import SetCoordSystemsCommand
from opensees_studio.core import CoordinateGridSystem, GridSystem, make_grid_lines

#: (slot name on MainWindow, tool name shown in the prompt)
DRAW_TOOLS = [
    ("_on_draw_node_tool", "Draw Node"),
    ("_on_draw_frame_tool", "Draw Frame"),
    ("_on_draw_truss_tool", "Draw Truss"),
]


@pytest.fixture
def window(qtbot):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    win._vm.new_project(ndm=2, ndf=3)
    win.show()
    qtbot.waitExposed(win)
    yield win


def _give_it_a_grid(window) -> None:  # type: ignore[no-untyped-def]
    window._vm.apply_command(
        SetCoordSystemsCommand(
            window._vm,
            [
                CoordinateGridSystem(
                    name="Global",
                    grid=GridSystem(
                        x_grid_lines=make_grid_lines("X", [0.0, 5.0]),
                        y_grid_lines=make_grid_lines("Y", [0.0, 3.0]),
                        z_grid_lines=make_grid_lines("Z", [0.0]),
                    ),
                )
            ],
        )
    )


def _answer(monkeypatch: pytest.MonkeyPatch, button) -> list[str]:  # type: ignore[no-untyped-def]
    seen: list[str] = []

    def _question(parent, title, text, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(title)
        return button

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_question))
    return seen


@pytest.mark.parametrize(("slot", "tool_name"), DRAW_TOOLS)
@pytest.mark.gui
def test_draw_tool_explains_the_missing_grid(  # type: ignore[no-untyped-def]
    qtbot, window, monkeypatch, slot, tool_name
) -> None:
    assert not window._has_grid_lines()
    seen = _answer(monkeypatch, QMessageBox.StandardButton.No)

    getattr(window, slot)()

    assert seen == [f"{tool_name}: no grid defined"]
    # The tool did not arm, and the toolbar fell back to Select rather than
    # staying on a tool that cannot do anything.
    assert window._tool_controller.active is None
    assert window._act_tool_select.isChecked()
    assert not window._act_tool_draw_node.isChecked()


@pytest.mark.gui
def test_accepting_the_prompt_defines_a_grid_and_arms_the_tool(  # type: ignore[no-untyped-def]
    qtbot, window, monkeypatch
) -> None:
    _answer(monkeypatch, QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(window, "_on_grid_system", lambda: _give_it_a_grid(window))

    window._on_draw_node_tool()

    assert window._has_grid_lines()
    assert window._tool_controller.active is not None


@pytest.mark.gui
def test_a_project_with_a_grid_never_asks(qtbot, window, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _give_it_a_grid(window)
    seen = _answer(monkeypatch, QMessageBox.StandardButton.No)

    window._on_draw_node_tool()

    assert seen == []
    assert window._tool_controller.active is not None


@pytest.mark.gui
def test_a_hidden_grid_does_not_count_as_snappable(qtbot, window, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Grid lines that are switched off leave the canvas with no target either."""
    _give_it_a_grid(window)
    project = window._vm.project
    system = project.coord_systems[0]
    window._vm.apply_command(
        SetCoordSystemsCommand(
            window._vm,
            [system.model_copy(update={"grid": system.grid.model_copy(update={"visible": False})})],
        )
    )
    seen = _answer(monkeypatch, QMessageBox.StandardButton.No)

    window._on_draw_node_tool()

    assert seen == ["Draw Node: no grid defined"]
    assert window._tool_controller.active is None
