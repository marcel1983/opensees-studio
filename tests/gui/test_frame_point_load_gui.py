"""Assign → Frame → Point Load: the command, the menu, and the edits that move loads.

The solved numbers are pinned in ``tests/integration/test_frame_point_load.py``;
here the wiring: undo, which elements take the load, the relative and absolute
distances, and that meshing, replicating and repairing duplicates keep the load
where it was along the member.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import (
    AddElementsCommand,
    AddNodesCommand,
    AddPointElementLoadsCommand,
    AddSectionsCommand,
    FixDuplicatesCommand,
    MeshCommand,
    ReplicateCommand,
)
from opensees_studio.core import (
    ElasticBeamColumn,
    ElasticSection,
    Node,
    PlainLoadPattern,
    PointElementLoad,
    TrussElement,
)
from opensees_studio.core.mesh import mesh_bars
from opensees_studio.viewmodels import ProjectViewModel
from opensees_studio.views.dialogs import AssignPointElementLoadDialog
from opensees_studio.views.dialogs.point_element_load import ABSOLUTE

LENGTH = 10.0


def _populate(vm: ProjectViewModel) -> None:
    vm.new_project(ndm=3, ndf=6)
    vm.apply_command(
        AddNodesCommand(
            vm,
            [
                Node(id=1, coords=(0.0, 0.0, 0.0), restraint=(True,) * 6),
                Node(id=2, coords=(LENGTH, 0.0, 0.0)),
                Node(id=3, coords=(0.0, 0.0, 4.0)),
            ],
        )
    )
    vm.apply_command(
        AddSectionsCommand(
            vm,
            [ElasticSection(id=1, name="S", E=2e8, A=0.01, Iz=1e-4, Iy=1e-4, G=8e7, J=1e-4)],
        )
    )
    vm.apply_command(
        AddElementsCommand(
            vm,
            [
                ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1),
                TrussElement(id=2, nodes=(1, 3), area=1.0, material_id=1),
            ],
        )
    )


def _vm() -> ProjectViewModel:
    vm = ProjectViewModel()
    _populate(vm)
    return vm


def _point_loads(vm: ProjectViewModel) -> list[PointElementLoad]:
    return [
        load
        for pattern in vm.project.load_patterns
        if isinstance(pattern, PlainLoadPattern)
        for load in pattern.point_loads
    ]


# ──────────────────────────── the command ────────────────────────────
@pytest.mark.gui
def test_the_command_adds_the_load_and_undo_removes_it_with_its_pattern(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = _vm()
    vm.apply_command(AddPointElementLoadsCommand(vm, {1: 0.25}, py=-7.0))

    assert _point_loads(vm) == [PointElementLoad(element_id=1, py=-7.0, x=0.25)]
    assert len(vm.project.load_patterns) == 1  # a default pattern was created

    vm.undo_stack.undo()
    assert vm.project.load_patterns == []
    assert vm.project.time_series == []

    vm.undo_stack.redo()
    assert _point_loads(vm) == [PointElementLoad(element_id=1, py=-7.0, x=0.25)]


@pytest.mark.gui
def test_a_truss_does_not_take_a_point_load(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = _vm()
    command = AddPointElementLoadsCommand(vm, {1: 0.5, 2: 0.5}, py=-1.0)
    with pytest.raises(ValueError, match="not one: 2"):
        command.redo()
    assert vm.project.load_patterns == []


# ──────────────────────────── the menu ────────────────────────────
def _window(qtbot):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    _populate(mw._vm)
    return mw


def _answer(monkeypatch, *, py: float, distance: float, absolute: bool = False) -> None:  # type: ignore[no-untyped-def]
    def _fake_exec(self: AssignPointElementLoadDialog) -> int:
        if absolute:
            self._mode.setCurrentIndex(self._mode.findData(ABSOLUTE))
        self._fields["Py"].setValue(py)
        self._distance.setValue(distance)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(AssignPointElementLoadDialog, "exec", _fake_exec)


@pytest.mark.gui
def test_the_menu_loads_the_selected_frames_and_skips_the_truss(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    _answer(monkeypatch, py=-3.0, distance=0.3)
    mw._canvas.selection.set_selection(set(), {1, 2})
    mw._refresh_action_enablement()
    assert mw._act_assign_frame_point_load.isEnabled()

    mw._act_assign_frame_point_load.trigger()

    assert _point_loads(mw._vm) == [PointElementLoad(element_id=1, py=-3.0, x=0.3)]


@pytest.mark.gui
def test_an_absolute_distance_becomes_a_fraction_of_each_member(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    _answer(monkeypatch, py=-3.0, distance=2.5, absolute=True)
    mw._canvas.selection.set_selection(set(), {1})

    mw._act_assign_frame_point_load.trigger()

    assert _point_loads(mw._vm) == [PointElementLoad(element_id=1, py=-3.0, x=0.25)]


@pytest.mark.gui
def test_a_distance_past_the_end_is_refused(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    _answer(monkeypatch, py=-3.0, distance=12.0, absolute=True)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    mw._canvas.selection.set_selection(set(), {1})

    mw._act_assign_frame_point_load.trigger()

    assert shown == ["The distance is longer than every selected element."]
    assert _point_loads(mw._vm) == []


@pytest.mark.gui
def test_only_a_truss_selected_is_refused(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    mw._canvas.selection.set_selection(set(), {2})

    mw._act_assign_frame_point_load.trigger()

    assert shown == ["None of the selected elements is a frame (beam-column) element."]


# ──────────────────────────── edits that move the load ────────────────────────────
@pytest.mark.gui
def test_meshing_puts_the_load_on_the_piece_it_falls_on(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = _vm()
    vm.apply_command(AddPointElementLoadsCommand(vm, {1: 0.35}, py=-7.0))
    plan = mesh_bars(vm.project, {1}, target_size=2.5)  # four pieces of 2.5

    vm.apply_command(MeshCommand(vm, plan))

    (load,) = _point_loads(vm)
    piece = vm.project.element(load.element_id)
    start = vm.project.node(piece.nodes[0]).coords[0]
    end = vm.project.node(piece.nodes[1]).coords[0]
    assert start + load.x * (end - start) == pytest.approx(3.5)
    assert (start, end) == (2.5, 5.0)
    assert load.py == -7.0

    vm.undo_stack.undo()
    assert _point_loads(vm) == [PointElementLoad(element_id=1, py=-7.0, x=0.35)]


@pytest.mark.gui
def test_replicating_a_frame_copies_its_point_load(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = _vm()
    vm.apply_command(AddPointElementLoadsCommand(vm, {1: 0.2}, py=-1.0))

    vm.apply_command(ReplicateCommand(vm, {1, 2}, {1}, offset=(0.0, 3.0, 0.0)))

    loads = _point_loads(vm)
    assert len(loads) == 2
    assert loads[1].element_id != 1 and loads[1].x == 0.2

    vm.undo_stack.undo()
    assert len(_point_loads(vm)) == 1


@pytest.mark.gui
def test_a_reversed_duplicate_hands_its_load_over_measured_from_the_other_end(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = _vm()
    vm.apply_command(AddElementsCommand(vm, [ElasticBeamColumn(id=5, nodes=(2, 1), section_id=1)]))
    vm.apply_command(AddPointElementLoadsCommand(vm, {5: 0.2}, py=-1.0))

    vm.apply_command(FixDuplicatesCommand(vm))

    assert {el.id for el in vm.project.elements} == {1, 2}
    (load,) = _point_loads(vm)
    assert (load.element_id, load.py) == (1, -1.0)
    assert load.x == pytest.approx(0.8)
