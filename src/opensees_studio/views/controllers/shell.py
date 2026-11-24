"""What a controller may use of the main window."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

    from opensees_studio.viewmodels import ProjectViewModel
    from opensees_studio.views.canvas3d import ModelCanvas


@dataclass(frozen=True)
class Shell:
    """The window as a controller sees it: five things, on purpose.

    A controller that needs something else of the window takes it as its own
    constructor argument (see ``TransformsController``'s measure hooks), so the
    coupling is written down where it is created instead of being any
    attribute of a 9000-line class.
    """

    window: QMainWindow
    """Parent of the dialogs and message boxes; owner of the status bar."""
    vm: ProjectViewModel
    canvas: Callable[[], ModelCanvas]
    """The focused viewport *now*: it follows focus to a secondary view window."""
    log: Callable[[str], None]
    refresh_actions: Callable[[], None]
    """Re-evaluate which commands are enabled."""
