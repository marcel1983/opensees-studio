"""Turns :class:`ActionSpec` tables into the window's ``QAction`` objects."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence

from opensees_studio.views.actions.spec import STANDARD_KEY_PREFIX, ActionSpec, ActionState


def key_sequence(shortcut: str) -> QKeySequence:
    """``"Ctrl+T"`` or ``"std:Save"`` as the key sequence it stands for."""
    if shortcut.startswith(STANDARD_KEY_PREFIX):
        name = shortcut.removeprefix(STANDARD_KEY_PREFIX)
        return QKeySequence(QKeySequence.StandardKey[name])
    return QKeySequence(shortcut)


class ActionRegistry:
    """The actions built from a set of specs, by id.

    The three steps mirror the window's start-up order: :meth:`create` before
    the menus are laid out, :meth:`wire` once the handlers' collaborators
    exist, :meth:`refresh` whenever the project or the selection changes.
    """

    def __init__(self, specs: Iterable[ActionSpec]) -> None:
        self._specs: dict[str, ActionSpec] = {}
        for spec in specs:
            if spec.id in self._specs:
                raise ValueError(f"two actions declared as {spec.id!r}")
            self._specs[spec.id] = spec
        self._actions: dict[str, QAction] = {}

    @property
    def specs(self) -> tuple[ActionSpec, ...]:
        return tuple(self._specs.values())

    def create(self, owner: QObject) -> None:
        """Build every action as a child of ``owner``.

        Each one is also stored on ``owner`` under ``spec.attribute``, which is
        where the ribbon, the icons and the help table look a command up.
        """
        for spec in self._specs.values():
            if hasattr(owner, spec.attribute):
                raise ValueError(f"{spec.id!r}: {spec.attribute} already exists on the window")
            action = QAction(spec.text, owner)
            action.setObjectName(spec.id)
            if spec.shortcut is not None:
                action.setShortcut(key_sequence(spec.shortcut))
            if spec.checkable:
                action.setCheckable(True)
            if spec.tooltip is not None:
                action.setToolTip(spec.tooltip)
            self._actions[spec.id] = action
            setattr(owner, spec.attribute, action)

    def wire(self, target: object) -> None:
        """Connect every action to the method of ``target`` its spec names."""
        for spec in self._specs.values():
            self._actions[spec.id].triggered.connect(getattr(target, spec.handler))

    def refresh(self, state: ActionState) -> None:
        """Enable or disable the actions whose spec states what they need."""
        for spec in self._specs.values():
            if spec.needs:  # None and Needs.NOTHING: not this method's to set
                self._actions[spec.id].setEnabled(state.allows(spec.needs))

    def action(self, action_id: str) -> QAction:
        try:
            return self._actions[action_id]
        except KeyError:
            raise KeyError(f"no action declared as {action_id!r}") from None
