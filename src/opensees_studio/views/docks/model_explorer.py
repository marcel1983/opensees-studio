"""The Model Explorer: what the project holds, by category, and a way to select it.

A tree with one branch per kind of object (nodes, elements, materials,
sections, time series, patterns, analyses), each with its count and one row
per object. Picking node and element rows selects them in the viewport:
Ctrl+click and Shift+click build a multi-row selection, so a command that
needs several joints (Zero-Length Section needs exactly two) can be driven
from the tree alone.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget

from opensees_studio.core import Project
from opensees_studio.views.i18n import tr

#: The branches, in order. The English name is the key the selection
#: dispatches on; only the text on screen is translated.
CATEGORIES = (
    "Nodes",
    "Elements",
    "Materials",
    "Sections",
    "Time Series",
    "Patterns",
    "Analyses",
)


def _typed_label(item: Any) -> str:
    return f"#{item.id}  [{item.type}]  {item.name or ''}".strip()


def _node_label(node: Any) -> str:
    return f"#{node.id}  {node.name or ''}".strip()


class ModelExplorer(QTreeWidget):
    """The project as a tree; :attr:`picked` carries the node and element ids selected in it."""

    #: ``(node_ids, element_ids)``, two sets, when the picked rows hold at least one of them.
    picked = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderLabel("Model")
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        #: The top-level item of each category, filled by :meth:`refresh`.
        self.categories: dict[str, QTreeWidgetItem] = {}
        for label in CATEGORIES:
            category = QTreeWidgetItem([label])
            self.categories[label] = category
            self.addTopLevelItem(category)

    def refresh(self, project: Project | None) -> None:
        """Repopulate every category with its count and its objects."""
        self.setHeaderLabel(tr("Model"))
        if project is None:
            for kind, category in self.categories.items():
                category.takeChildren()
                category.setText(0, f"{tr(kind)} (0)")
            return
        self._fill("Nodes", project.nodes, _node_label)
        self._fill("Elements", project.elements, _typed_label)
        self._fill("Materials", project.materials, _typed_label)
        self._fill("Sections", project.sections, _typed_label)
        self._fill("Time Series", project.time_series, _typed_label)
        self._fill("Patterns", project.load_patterns, _typed_label)
        self._fill("Analyses", project.analyses, _typed_label)

    def _fill(self, kind: str, items: Sequence[Any], label: Callable[[Any], str]) -> None:
        """Refill one category in place."""
        category = self.categories[kind]
        category.takeChildren()
        category.setText(0, f"{tr(kind)} ({len(items)})")
        for item in items:
            child = QTreeWidgetItem([label(item)])
            # Tagged with kind and id, which is what a picked row is read by.
            child.setData(0, Qt.ItemDataRole.UserRole, (kind, item.id))
            category.addChild(child)

    def _on_selection_changed(self) -> None:
        """Tell the viewport about every picked node and element row, in one go."""
        node_ids: set[int] = set()
        element_ids: set[int] = set()
        for item in self.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data is None:
                continue
            kind, entity_id = data
            if kind == "Nodes":
                node_ids.add(entity_id)
            elif kind == "Elements":
                element_ids.add(entity_id)
        if node_ids or element_ids:
            self.picked.emit(node_ids, element_ids)
