"""The Sections page shared by the Warehouse and Building wizards.

Each member kind has a combo box: its first entry creates the wizard's default
section with the model, the others are the project's sections. A wizard opened
on an empty project would offer nothing else, so the page also has a
*Section Library…* button: it opens Define → Section Library (the AISC
shapes, the cold-formed profiles, a section typed in) through a hook the controller hands
over, and the combo boxes are filled again with what the project has then.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtWidgets import QComboBox, QPushButton, QWidget

from opensees_studio.views.i18n import tr

#: Item data of the entry that creates the wizard's default section.
CREATE_DEFAULT = -1

#: Opens Define → Section Library over ``parent``; returns the sections a wizard offers then.
DefineSections = Callable[[QWidget], list[Any]]


def section_label(section: Any) -> str:
    return f"#{section.id}  {section.name or tr('(unnamed)')}"


def new_section_combo(default_text: str, sections: Iterable[Any]) -> QComboBox:
    """A combo box of a member kind, narrow whatever the names of the sections."""
    combo = QComboBox()
    fill_section_combo(combo, default_text, sections)
    # A long section name must not push the page wider than the wizard.
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(24)
    return combo


def fill_section_combo(combo: QComboBox, default_text: str, sections: Iterable[Any]) -> None:
    """Fill ``combo`` again, keeping the section it shows when it is still there."""
    current = combo.currentData()
    blocked = combo.blockSignals(True)
    combo.clear()
    combo.addItem(default_text, userData=CREATE_DEFAULT)
    for section in sections:
        combo.addItem(section_label(section), userData=section.id)
    index = combo.findData(current) if current is not None else -1
    combo.setCurrentIndex(max(index, 0))
    combo.blockSignals(blocked)
    if not blocked:  # what depends on the choice is worked out again, once
        combo.currentIndexChanged.emit(combo.currentIndex())


def chosen_section(combo: QComboBox) -> int | None:
    """The section id ``combo`` shows; None for "create the default one"."""
    data = combo.currentData()
    return None if data in (None, CREATE_DEFAULT) else int(data)


def define_sections_button(
    parent: QWidget, define: DefineSections | None, on_sections: Callable[[list[Any]], None]
) -> QPushButton | None:
    """The *Section Library…* button, or None when the wizard has no hook for it."""
    if define is None:
        return None
    button = QPushButton(tr("Section Library…"))
    button.setToolTip(
        tr(
            "Opens Define → Section Library to add shapes of the AISC library, "
            "cold-formed profiles or sections of your own; they are then offered here"
        )
    )
    button.clicked.connect(lambda: on_sections(define(parent)))
    return button


__all__ = [
    "CREATE_DEFAULT",
    "DefineSections",
    "chosen_section",
    "define_sections_button",
    "fill_section_combo",
    "new_section_combo",
    "section_label",
]
