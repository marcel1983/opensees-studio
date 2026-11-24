"""The Select menu: everything, inverted, the previous one, and queries that add to it."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from opensees_studio.core import Project
from opensees_studio.core import selection as selection_queries
from opensees_studio.core.connectivity import (
    joints_on_bars,
    joints_on_shell_edges,
    loose_joints,
)
from opensees_studio.core.duplicates import default_tolerance
from opensees_studio.core.groups import group_members
from opensees_studio.views.controllers.shell import Shell

#: What a query returns: the joints and the elements to add.
Found = tuple[set[int], set[int]]


def _pairs_selection(pairs: list[tuple[int, int]]) -> Found:
    """``(element, node)`` fault pairs as a selection: the joints and the members."""
    return {node for _, node in pairs}, {element for element, _ in pairs}


class SelectController(QObject):
    """What the Select menu does to the selection of the focused viewport.

    Every query *adds* to the current selection (SAP2000 style), so "frames of
    section A" then "frames of section B" selects both. The "By …" submenus
    list what the model holds when they open. ``action`` is the window's
    ``action(id)``: the menu enables three of its commands when it opens.
    """

    def __init__(self, shell: Shell, *, action: Callable[[str], QAction]) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._action = action
        self._by_menus: tuple[QMenu, ...] = ()

    # ── the menu ────────────────────────────────────────────────────
    def add_by_menus(self, menu: QMenu) -> None:
        """Add the "By …" submenus to ``menu`` and keep it up to date when it opens."""
        self.by_type_menu = menu.addMenu("By Element &Type")
        self.by_section_menu = menu.addMenu("By Se&ction")
        self.by_material_menu = menu.addMenu("By Mate&rial")
        self.by_pattern_menu = menu.addMenu("By &Load Pattern")
        self.by_group_menu = menu.addMenu("By &Group")
        filled = (
            (self.by_type_menu, self.fill_by_type),
            (self.by_section_menu, self.fill_by_section),
            (self.by_material_menu, self.fill_by_material),
            (self.by_pattern_menu, self.fill_by_pattern),
            (self.by_group_menu, self.fill_by_group),
        )
        for submenu, fill in filled:
            submenu.aboutToShow.connect(lambda submenu=submenu, fill=fill: fill(submenu))
        self._by_menus = tuple(submenu for submenu, _fill in filled)
        menu.aboutToShow.connect(self.refresh_menu)

    def refresh_menu(self) -> None:
        """Enable what makes sense for the project and the selection right now."""
        has = self._vm.project is not None
        sel = self._shell.canvas().selection
        self._action("select.invert").setEnabled(has)
        self._action("select.previous").setEnabled(has and any(sel.previous))
        self._action("select.joints_of_elements").setEnabled(has and bool(sel.elements))
        self._action("select.elements_within_joints").setEnabled(has and bool(sel.nodes))
        for submenu in self._by_menus:
            submenu.setEnabled(has)

    def _fill(self, submenu: Any, entries: list[tuple[str, Callable[[], None]]]) -> None:
        submenu.clear()
        if not entries:
            submenu.addAction("(none in the model)").setEnabled(False)
            return
        for label, callback in entries:
            # ``triggered`` passes ``checked``; keep it away from the callback.
            submenu.addAction(label).triggered.connect(lambda _checked=False, cb=callback: cb())

    def fill_by_type(self, submenu: Any) -> None:
        project = self._vm.project
        if project is None:
            return
        entries: list[tuple[str, Callable[[], None]]] = []
        for element_type in selection_queries.element_types(project):
            ids = selection_queries.elements_of_type(project, element_type)
            entries.append(
                (
                    f"{element_type} ({len(ids)})",
                    lambda ids=ids: self._add(elements=ids),
                )
            )
        self._fill(submenu, entries)

    def fill_by_section(self, submenu: Any) -> None:
        project = self._vm.project
        if project is None:
            return
        entries: list[tuple[str, Callable[[], None]]] = []
        for section in selection_queries.sections_in_use(project):
            ids = selection_queries.elements_with_section(project, section.id)
            entries.append(
                (
                    f"#{section.id} {section.name or section.type} ({len(ids)})",
                    lambda ids=ids: self._add(elements=ids),
                )
            )
        self._fill(submenu, entries)

    def fill_by_material(self, submenu: Any) -> None:
        project = self._vm.project
        if project is None:
            return
        entries: list[tuple[str, Callable[[], None]]] = []
        for material in selection_queries.materials_in_use(project):
            ids = selection_queries.elements_with_material(project, material.id)
            entries.append(
                (
                    f"#{material.id} {material.name or material.type} ({len(ids)})",
                    lambda ids=ids: self._add(elements=ids),
                )
            )
        self._fill(submenu, entries)

    def fill_by_pattern(self, submenu: Any) -> None:
        project = self._vm.project
        if project is None:
            return
        entries: list[tuple[str, Callable[[], None]]] = []
        for pattern in project.load_patterns:
            nodes, elements = selection_queries.loaded_by_pattern(project, pattern.id)
            if not nodes and not elements:
                continue
            entries.append(
                (
                    f"#{pattern.id} {pattern.name or pattern.type} "
                    f"({len(nodes)} joint(s), {len(elements)} element(s))",
                    lambda nodes=nodes, elements=elements: self._add(
                        nodes=nodes, elements=elements
                    ),
                )
            )
        self._fill(submenu, entries)

    def fill_by_group(self, submenu: Any) -> None:
        project = self._vm.project
        if project is None:
            return
        entries: list[tuple[str, Callable[[], None]]] = []
        for group in project.groups:
            nodes, elements = group_members(project, group.id)
            entries.append(
                (
                    f"{group.name} ({len(nodes)} joint(s), {len(elements)} element(s))",
                    partial(self._add, nodes=nodes, elements=elements),
                )
            )
        self._fill(submenu, entries)

    # ── replacing the selection ─────────────────────────────────────
    def all_objects(self) -> None:
        """Select all nodes AND all elements in the project."""
        if self._vm.project is None:
            return
        node_ids = {n.id for n in self._vm.project.nodes}
        elem_ids = {e.id for e in self._vm.project.elements}
        self._shell.canvas().selection.set_selection(node_ids, elem_ids)

    def invert(self) -> None:
        if self._vm.project is None:
            return
        sel = self._shell.canvas().selection
        nodes, elements = selection_queries.invert(self._vm.project, sel.nodes, sel.elements)
        sel.set_selection(nodes, elements)

    def previous(self) -> None:
        nodes, elements = self._shell.canvas().selection.previous
        if self._vm.project is None:
            return
        # Drop ids deleted since (the previous selection can outlive them).
        node_ids = {n.id for n in self._vm.project.nodes}
        element_ids = {e.id for e in self._vm.project.elements}
        self._shell.canvas().selection.set_selection(
            set(nodes) & node_ids, set(elements) & element_ids
        )

    # ── queries: each adds what it finds ────────────────────────────
    def all_joints(self) -> None:
        self._select_from(lambda p, sel: ({n.id for n in p.nodes}, set()))

    def all_elements(self) -> None:
        self._select_from(lambda p, sel: (set(), {e.id for e in p.elements}))

    def supports(self) -> None:
        self._select_from(lambda p, sel: (selection_queries.restrained_nodes(p), set()))

    def joints_with_mass(self) -> None:
        self._select_from(lambda p, sel: (selection_queries.nodes_with_mass(p), set()))

    def weighted(self) -> None:
        self._select_from(lambda p, sel: (set(), selection_queries.weighted_elements(p)))

    def joints_of_elements(self) -> None:
        self._select_from(
            lambda p, sel: (selection_queries.nodes_of_elements(p, sel.elements), set())
        )

    def elements_within_joints(self) -> None:
        self._select_from(
            lambda p, sel: (set(), selection_queries.elements_within_nodes(p, sel.nodes))
        )

    def loose_joints(self) -> None:
        self._select_from(lambda p, sel: (set(loose_joints(p)), set()))

    def joints_in_bars(self) -> None:
        self._select_from(lambda p, sel: _pairs_selection(joints_on_bars(p, default_tolerance(p))))

    def shell_edge_joints(self) -> None:
        self._select_from(
            lambda p, sel: _pairs_selection(joints_on_shell_edges(p, default_tolerance(p)))
        )

    def _select_from(self, query: Callable[[Project, Any], Found]) -> None:
        """Add what ``query(project, selection)`` returns to the selection."""
        if self._vm.project is None:
            return
        nodes, elements = query(self._vm.project, self._shell.canvas().selection)
        self._add(nodes=nodes, elements=elements)

    def _add(self, *, nodes: set[int] | None = None, elements: set[int] | None = None) -> None:
        """Add ``nodes`` / ``elements`` to what is selected and report the count."""
        if self._vm.project is None:
            return
        sel = self._shell.canvas().selection
        new_nodes = set(sel.nodes) | set(nodes or ())
        new_elements = set(sel.elements) | set(elements or ())
        sel.set_selection(new_nodes, new_elements)
        self._window.statusBar().showMessage(
            f"Selected {len(new_nodes)} joint(s), {len(new_elements)} element(s).", 4000
        )
