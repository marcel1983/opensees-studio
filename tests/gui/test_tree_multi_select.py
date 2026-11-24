"""Model Tree supports Ctrl+click multi-selection — regression guard."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QTreeWidget

from opensees_studio.core import Node


@pytest.mark.gui
def test_tree_is_in_extended_selection_mode(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Default QTreeWidget is single-select; we need ExtendedSelection."""
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert mw._tree.selectionMode() == QTreeWidget.SelectionMode.ExtendedSelection


@pytest.mark.gui
def test_tree_multi_select_syncs_canvas(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Selecting two node rows in the tree must populate the canvas
    selection with both ids — the precondition for the Zero-Length
    Section dialog (exactly 2 joints)."""
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=2, ndf=3)
    mw._vm.project.nodes.extend(
        [
            Node(id=1, coords=(0, 0, 0)),
            Node(id=2, coords=(0, 0, 0)),
            Node(id=3, coords=(1, 0, 0)),
        ]
    )
    mw._tree.refresh(mw._vm.project)

    nodes_cat = mw._tree.categories["Nodes"]
    nodes_cat.setExpanded(True)
    # Find the three child items and select rows 0 + 1.
    items = [nodes_cat.child(i) for i in range(nodes_cat.childCount())]
    assert len(items) == 3
    items[0].setSelected(True)
    items[1].setSelected(True)

    assert mw._canvas.selection.nodes == frozenset({1, 2})
    assert mw._canvas.selection.elements == frozenset()

    # Adding a third selection (row 2) keeps all three.
    items[2].setSelected(True)
    assert mw._canvas.selection.nodes == frozenset({1, 2, 3})

    # Deselecting row 0 leaves rows 1 + 2.
    items[0].setSelected(False)
    assert mw._canvas.selection.nodes == frozenset({2, 3})


@pytest.mark.gui
def test_the_explorer_alone_lists_the_project_and_reports_what_is_picked(qtbot) -> None:  # type: ignore[no-untyped-def]
    """The tree is a widget of its own: no window, a project in, picked ids out."""
    from opensees_studio.core import ElasticBeamColumn, Project
    from opensees_studio.views.docks import ModelExplorer

    explorer = ModelExplorer()
    qtbot.addWidget(explorer)
    picked: list[tuple[set[int], set[int]]] = []
    explorer.picked.connect(lambda nodes, elements: picked.append((nodes, elements)))

    explorer.refresh(None)
    assert explorer.categories["Nodes"].text(0) == "Nodes (0)"

    project = Project(ndm=3, ndf=6)
    project.nodes.extend([Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0), name="top")])
    project.elements.append(ElasticBeamColumn(id=7, nodes=(1, 2), section_id=1))
    explorer.refresh(project)
    nodes, elements = explorer.categories["Nodes"], explorer.categories["Elements"]
    assert nodes.text(0) == "Nodes (2)" and elements.text(0) == "Elements (1)"
    assert nodes.child(1).text(0) == "#2  top"
    assert elements.child(0).text(0).startswith("#7  [")

    nodes.child(0).setSelected(True)
    elements.child(0).setSelected(True)
    assert picked[-1] == ({1}, {7})

    # A category row carries no object: picking only it reports nothing.
    explorer.clearSelection()
    count = len(picked)
    explorer.categories["Materials"].setSelected(True)
    assert len(picked) == count

    # Refreshing replaces the rows, it does not add to them.
    explorer.refresh(project)
    assert nodes.childCount() == 2
