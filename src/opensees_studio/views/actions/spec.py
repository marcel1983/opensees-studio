"""What a menu command is, as data.

A command used to be spread over ``MainWindow``: a ``QAction(...)`` line in
``_build_actions``, a ``triggered.connect`` in ``_wire`` and a ``setEnabled`` in
``_refresh_action_enablement``, tied together only by the attribute name. An
:class:`ActionSpec` says the three things in one place, and
:class:`~opensees_studio.views.actions.registry.ActionRegistry` turns the specs
into actions.

No Qt here: the tables are plain data, so ``tests/unit`` checks them without a
``QApplication``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

#: Prefix of a ``shortcut`` that names a ``QKeySequence.StandardKey`` member
#: (``"std:Save"``) instead of spelling the keys (``"Ctrl+T"``).
STANDARD_KEY_PREFIX = "std:"


class Needs(enum.Flag):
    """What must be there for a command to be enabled; flags combine with ``|``."""

    NOTHING = 0
    PROJECT = enum.auto()
    SELECTION = enum.auto()
    SELECTED_NODES = enum.auto()
    SELECTED_ELEMENTS = enum.auto()
    #: Exactly two joints selected: what a link, a bearing or a constraint joins.
    TWO_NODES = enum.auto()
    #: The project has a time series: what a load pattern refers to.
    TIME_SERIES = enum.auto()


@dataclass(frozen=True)
class ActionState:
    """What the window has right now, as far as :class:`Needs` asks."""

    has_project: bool = False
    has_selection: bool = False
    has_selected_nodes: bool = False
    has_selected_elements: bool = False
    has_two_selected_nodes: bool = False
    has_time_series: bool = False

    def allows(self, needs: Needs) -> bool:
        """True when everything in ``needs`` is there."""
        met = Needs.NOTHING
        if self.has_project:
            met |= Needs.PROJECT
        if self.has_selection:
            met |= Needs.SELECTION
        if self.has_selected_nodes:
            met |= Needs.SELECTED_NODES
        if self.has_selected_elements:
            met |= Needs.SELECTED_ELEMENTS
        if self.has_two_selected_nodes:
            met |= Needs.TWO_NODES
        if self.has_time_series:
            met |= Needs.TIME_SERIES
        return needs & met == needs


@dataclass(frozen=True)
class ActionSpec:
    """One command.

    ``id`` is ``"<area>.<name>"`` and is how code and tests ask for the action
    (``window.action("file.save")``). ``handler`` names the method that runs it:
    a method of the window (``"_on_save"``) or, dotted, of one of its
    controllers (``"transforms.move"`` is ``window.transforms.move``).

    ``needs`` is what enables it. ``Needs.NOTHING`` leaves the action alone (it
    stays enabled); ``None`` means the condition is not one :class:`Needs` can
    express and the window sets it itself.
    """

    id: str
    text: str
    handler: str
    shortcut: str | None = None
    needs: Needs | None = Needs.NOTHING
    checkable: bool = False
    tooltip: str | None = None
    #: Only for a command whose ``_act_`` name predates its id and is not
    #: ``_act_<name>`` (``"assign.diaphragm"`` is ``_act_assign_diaphragm``).
    legacy_attribute: str | None = None

    @property
    def area(self) -> str:
        return self.id.partition(".")[0]

    @property
    def name(self) -> str:
        return self.id.partition(".")[2]

    @property
    def attribute(self) -> str:
        """The ``_act_<name>`` attribute the action is also stored under.

        The ribbon layout, ``core.help.ACTION_TOPICS``, the icon files and the
        GUI tests still find a command by that name.
        """
        return self.legacy_attribute or f"_act_{self.name}"
