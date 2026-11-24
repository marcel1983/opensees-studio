"""Edit → Copy/Paste/Move/Replicate/Mirror/Extrude live in ``TransformsController``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import AddElementsCommand, AddNodesCommand, AddSectionsCommand
from opensees_studio.core import ElasticBeamColumn, ElasticSection, Node
from opensees_studio.views.controllers.transforms import TransformsController
from opensees_studio.views.dialogs.mirror import MirrorDialog
from opensees_studio.views.dialogs.move import MoveDialog

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    vm = mw._vm
    vm.new_project(ndm=3, ndf=6)
    section = ElasticSection(id=1, name="S", E=200e9, A=0.01, Iz=1e-5, Iy=1e-5, G=80e9, J=1e-6)
    vm.apply_command(AddSectionsCommand(vm, [section]))
    vm.apply_command(
        AddNodesCommand(vm, [Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0))])
    )
    vm.apply_command(AddElementsCommand(vm, [ElasticBeamColumn(id=1, nodes=(1, 2), section_id=1)]))
    yield mw
    mw._help_controller.uninstall()


def test_the_window_owns_one_controller_and_the_commands_point_at_it(window) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(window.transforms, TransformsController)
    assert window.transforms.parent() is window
    # The old attribute names still find the same actions (ribbon, icons, help).
    assert window._act_move is window.action("edit.move")
    assert window._act_paste is window.action("edit.paste")


def test_a_selected_member_stands_for_its_joints(window) -> None:  # type: ignore[no-untyped-def]
    window._canvas.selection.set_selection(set(), {1})
    assert window.transforms.selection_nodes() == {1, 2}


def test_the_commands_follow_the_selection_and_the_clipboard(window) -> None:  # type: ignore[no-untyped-def]
    window._canvas.selection.clear()
    window._refresh_action_enablement()
    for name in ("copy", "move", "replicate", "mirror", "extrude", "paste"):
        assert not window.action(f"edit.{name}").isEnabled(), name

    window._canvas.selection.set_selection(set(), {1})
    window._refresh_action_enablement()
    for name in ("copy", "move", "replicate", "mirror", "extrude"):
        assert window.action(f"edit.{name}").isEnabled(), name
    assert not window.action("edit.paste").isEnabled()

    window.action("edit.copy").trigger()
    assert window.transforms.clipboard_contents() == ({1, 2}, {1})
    assert window.action("edit.paste").isEnabled()  # copy refreshed the commands


def test_move_opens_one_modeless_window_and_applies_it_as_one_undo_step(window) -> None:  # type: ignore[no-untyped-def]
    window._canvas.selection.set_selection(set(), {1})
    window.action("edit.move").trigger()
    dialog = window.transforms.offset_dialog
    assert isinstance(dialog, MoveDialog) and not dialog.isModal()
    assert window._offset_dialog is dialog  # the name the Measure tool tests use

    # A second request raises the open window instead of stacking another.
    window.action("edit.move").trigger()
    assert window.transforms.offset_dialog is dialog

    dialog.set_offset(0.0, 0.0, 3.0)
    count = window._vm.undo_stack.count()
    dialog.accept()
    project = window._vm.project
    assert [n.coords for n in project.nodes] == [(0.0, 0.0, 3.0), (4.0, 0.0, 3.0)]
    assert window._vm.undo_stack.count() == count + 1
    assert window.transforms.offset_dialog is None


def test_mirror_without_a_selection_only_explains(window, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text, *a, **k: seen.append(text))
    monkeypatch.setattr(MirrorDialog, "exec", lambda self: int(QDialog.DialogCode.Rejected))
    window._canvas.selection.clear()
    window.transforms.mirror()
    assert seen == ["Select nodes or frame elements first."]
