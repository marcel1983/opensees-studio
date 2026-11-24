"""Controllers: what one area of the menus does, outside ``MainWindow``.

A controller is a ``QObject`` that receives a :class:`~.shell.Shell` (the few
things of the window it may use) and owns the state of its area. The window
creates it, and the area's commands name its methods as their handlers
(``ActionSpec(..., handler="transforms.move")``).
"""

from __future__ import annotations

from opensees_studio.views.controllers.shell import Shell

__all__ = ["Shell"]
