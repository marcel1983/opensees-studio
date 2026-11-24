"""The declared commands (``views/actions``) hang together, checked without Qt.

The spec tables are plain data, so this reads ``main_window.py`` as source
instead of importing it: no ``QApplication`` and no PySide6 needed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from opensees_studio.core.help import ACTION_TOPICS, TOPICS
from opensees_studio.views.actions import ALL_ACTIONS, ActionSpec, ActionState, Needs

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


def test_the_attribute_is_the_name_unless_the_command_kept_an_older_one() -> None:
    assert ActionSpec("assign.masses", "M", "_on_m").attribute == "_act_masses"
    kept = ActionSpec("assign.masses", "M", "_on_m", legacy_attribute="_act_assign_masses")
    assert kept.attribute == "_act_assign_masses"
    # An override is only for a name that differs: otherwise it is noise.
    assert [s.id for s in ALL_ACTIONS if s.legacy_attribute == f"_act_{s.name}"] == []


def test_no_two_commands_share_an_attribute() -> None:
    # The attribute drops the area, so "file.x" and "edit.x" would collide.
    attributes = [spec.attribute for spec in ALL_ACTIONS]
    assert len(set(attributes)) == len(attributes)


def _methods(tree: ast.AST, class_suffix: str) -> set[str]:
    return {
        item.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name.endswith(class_suffix)
        for item in node.body
        if isinstance(item, ast.FunctionDef)
    }


def test_every_handler_is_a_method_of_the_window_or_of_its_controller() -> None:
    window_methods = _methods(MAIN_WINDOW, "MainWindow")
    window_attributes = {
        target.attr
        for node in ast.walk(_main_window_class())
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Attribute)
    }
    missing = []
    for spec in ALL_ACTIONS:
        controller, _, method = spec.handler.rpartition(".")
        if not controller:
            found = method in window_methods
        else:
            # "transforms.move": views/controllers/transforms.py, a method of its
            # controller class, which the window keeps as ``self.transforms``.
            module = VIEWS / "controllers" / f"{controller}.py"
            found = (
                module.is_file()
                and controller in window_attributes
                and method in _methods(ast.parse(module.read_text(encoding="utf-8")), "Controller")
            )
        if not found:
            missing.append(spec.id)
    assert missing == []


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


def test_two_joints_is_its_own_need() -> None:
    # A link joins exactly two joints: one, or three, is not enough.
    two = Needs.PROJECT | Needs.TWO_NODES
    some = ActionState(has_project=True, has_selected_nodes=True, has_selection=True)
    assert not some.allows(two)
    exactly = ActionState(
        has_project=True, has_selected_nodes=True, has_selection=True, has_two_selected_nodes=True
    )
    assert exactly.allows(two)
    assert not ActionState(has_two_selected_nodes=True).allows(two)
