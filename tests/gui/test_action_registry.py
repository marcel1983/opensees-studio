"""``ActionRegistry`` builds, wires and enables the declared commands."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence

from opensees_studio.views.actions import ALL_ACTIONS, ActionSpec, ActionState, Needs
from opensees_studio.views.actions.registry import ActionRegistry, key_sequence

pytestmark = pytest.mark.gui


class _Target:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def _on_one(self) -> None:
        self.calls.append("one")

    def _on_two(self) -> None:
        self.calls.append("two")


SPECS = (
    ActionSpec("demo.one", "&One…", "_on_one", shortcut="Ctrl+T", needs=Needs.PROJECT),
    ActionSpec("demo.two", "T&wo", "_on_two", shortcut="std:Save", checkable=True, tooltip="tip"),
    ActionSpec("demo.three", "Three", "_on_one", needs=None),
    ActionSpec("demo.four", "Four", "_on_one", needs=Needs.PROJECT | Needs.SELECTED_NODES),
)


def test_create_builds_each_action_under_its_id_and_attribute(qapp) -> None:  # type: ignore[no-untyped-def]
    owner = QObject()
    registry = ActionRegistry(SPECS)
    registry.create(owner)

    one = registry.action("demo.one")
    assert one is owner._act_one  # type: ignore[attr-defined]
    assert one.parent() is owner
    assert (one.text(), one.objectName()) == ("&One…", "demo.one")
    assert one.shortcut() == QKeySequence("Ctrl+T")
    assert not one.isCheckable()

    two = registry.action("demo.two")
    assert two.shortcut() == QKeySequence(QKeySequence.StandardKey.Save)
    assert two.isCheckable()
    assert two.toolTip() == "tip"
    with pytest.raises(KeyError, match=r"demo\.none"):
        registry.action("demo.none")


def test_a_repeated_id_or_a_taken_attribute_is_refused(qapp) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=r"demo\.one"):
        ActionRegistry((*SPECS, SPECS[0]))
    owner = QObject()
    owner._act_one = QAction(owner)  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="_act_one already exists"):
        ActionRegistry(SPECS).create(owner)


def test_wire_connects_each_action_to_its_handler(qapp) -> None:  # type: ignore[no-untyped-def]
    owner, target = QObject(), _Target()
    registry = ActionRegistry(SPECS)
    registry.create(owner)
    registry.wire(target)
    registry.action("demo.two").trigger()
    registry.action("demo.one").trigger()
    assert target.calls == ["two", "one"]


def test_refresh_sets_only_the_actions_that_state_a_need(qapp) -> None:  # type: ignore[no-untyped-def]
    owner = QObject()
    registry = ActionRegistry(SPECS)
    registry.create(owner)
    # Disabled by somebody else: refresh must not take them back.
    registry.action("demo.two").setEnabled(False)
    registry.action("demo.three").setEnabled(False)

    registry.refresh(ActionState(has_project=True))
    assert registry.action("demo.one").isEnabled()
    assert not registry.action("demo.four").isEnabled()
    assert not registry.action("demo.two").isEnabled()
    assert not registry.action("demo.three").isEnabled()

    registry.refresh(ActionState(has_project=True, has_selected_nodes=True))
    assert registry.action("demo.four").isEnabled()
    registry.refresh(ActionState())
    assert not registry.action("demo.one").isEnabled()


def test_key_sequence_reads_both_spellings(qapp) -> None:  # type: ignore[no-untyped-def]
    assert key_sequence("std:Open") == QKeySequence(QKeySequence.StandardKey.Open)
    assert key_sequence("Ctrl+Shift+R") == QKeySequence("Ctrl+Shift+R")


def test_the_window_serves_every_declared_command(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    try:
        for spec in ALL_ACTIONS:
            action = window.action(spec.id)
            assert action is getattr(window, spec.attribute), spec.id
            assert action.text().replace("&", "") != "", spec.id
            if spec.shortcut is not None:
                assert action.shortcut() == key_sequence(spec.shortcut), spec.id

        # File commands before and after a project exists.
        window._refresh_action_enablement()
        assert window.action("file.open").isEnabled()
        assert not window.action("file.save").isEnabled()
        assert not window.action("file.export_report").isEnabled()
        window._vm.new_project(ndm=3, ndf=6)
        window._refresh_action_enablement()
        assert window.action("file.save").isEnabled()
        assert window.action("file.export_report").isEnabled()
    finally:
        window._help_controller.uninstall()
