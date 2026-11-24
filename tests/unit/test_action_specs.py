"""The declared commands (``views/actions``) hang together, checked without Qt.

The spec tables are plain data, so this reads ``main_window.py`` as source
instead of importing it: no ``QApplication`` and no PySide6 needed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from opensees_studio.core.help import ACTION_TOPICS, TOPICS
from opensees_studio.views.actions import ALL_ACTIONS, ActionState, Needs

VIEWS = Path(__file__).resolve().parents[2] / "src" / "opensees_studio" / "views"
MAIN_WINDOW = ast.parse((VIEWS / "main_window.py").read_text(encoding="utf-8"))
#: The modules a unit test may import: they must stay free of Qt.
PLAIN_MODULES = sorted(p for p in (VIEWS / "actions").glob("*.py") if p.name != "registry.py")


def _main_window_class() -> ast.ClassDef:
    return next(
        node
        for node in MAIN_WINDOW.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )


def test_ids_are_area_dot_name_and_unique() -> None:
    ids = [spec.id for spec in ALL_ACTIONS]
    assert [i for i in ids if not re.fullmatch(r"[a-z]+\.[a-z0-9_]+", i)] == []
    assert len(set(ids)) == len(ids)


def test_no_two_commands_share_an_attribute() -> None:
    # The attribute drops the area, so "file.x" and "edit.x" would collide.
    attributes = [spec.attribute for spec in ALL_ACTIONS]
    assert len(set(attributes)) == len(attributes)


def test_every_handler_is_a_method_of_the_window() -> None:
    methods = {node.name for node in _main_window_class().body if isinstance(node, ast.FunctionDef)}
    assert [s.id for s in ALL_ACTIONS if s.handler not in methods] == []


def test_the_window_does_not_build_a_declared_action_itself() -> None:
    # A leftover ``self._act_save = QAction(...)`` would shadow the declared one.
    assigned = {
        target.attr
        for node in ast.walk(_main_window_class())
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Attribute)
    }
    assert sorted(assigned & {spec.attribute for spec in ALL_ACTIONS}) == []


def test_every_command_has_a_help_page() -> None:
    missing = [s.id for s in ALL_ACTIONS if ACTION_TOPICS.get(s.attribute) not in TOPICS]
    assert missing == []


def test_the_spec_tables_import_no_qt() -> None:
    assert PLAIN_MODULES, "views/actions moved?"
    for path in PLAIN_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ] + [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        qt = [m for m in imported if m.startswith("PySide6") or m.endswith(".registry")]
        assert qt == [], f"{path.name} imports {qt}"


def test_needs_are_all_required() -> None:
    state = ActionState(has_project=True, has_selected_nodes=True, has_selection=True)
    assert state.allows(Needs.NOTHING)
    assert state.allows(Needs.PROJECT)
    assert state.allows(Needs.PROJECT | Needs.SELECTED_NODES)
    assert not state.allows(Needs.PROJECT | Needs.SELECTED_ELEMENTS)
    assert not ActionState().allows(Needs.PROJECT)
    assert ActionState().allows(Needs.NOTHING)
