"""Every section and element a project can hold has an emitter, and only one."""

from __future__ import annotations

import typing
from unittest.mock import Mock

import pytest

from opensees_studio.core import Project
from opensees_studio.core.geometry.elements import Element
from opensees_studio.core.sections import Section
from opensees_studio.services.element_emitters import (
    ELEMENT_EMITTERS,
    ElementContext,
    element_emitter,
    emit_element,
)
from opensees_studio.services.frame_members import FramePlan
from opensees_studio.services.section_emitters import (
    SECTION_EMITTERS,
    SectionContext,
    emit_section,
    section_emitter,
)


def _members(annotated: object) -> tuple[type, ...]:
    """The classes of a discriminated union (``Annotated[A | B, Field(...)]``)."""
    union = typing.get_args(annotated)[0]
    return typing.get_args(union)


@pytest.mark.parametrize("cls", _members(Element), ids=lambda c: c.__name__)
def test_every_element_class_has_an_emitter(cls: type) -> None:
    assert any(issubclass(cls, classes) for classes, _ in ELEMENT_EMITTERS)


@pytest.mark.parametrize("cls", _members(Section), ids=lambda c: c.__name__)
def test_every_section_class_has_an_emitter(cls: type) -> None:
    assert any(issubclass(cls, known) for known, _ in SECTION_EMITTERS)


def test_an_unknown_kind_is_refused_by_name() -> None:
    class Strange:
        id = 1

    with pytest.raises(NotImplementedError, match="Element type not yet handled: Strange"):
        emit_element(Strange(), ElementContext(Mock(), Project(), FramePlan(), {}))
    with pytest.raises(NotImplementedError, match="Section type not yet handled: Strange"):
        emit_section(Strange(), SectionContext(Mock(), 3, {}))


def test_a_class_cannot_be_registered_twice() -> None:
    known_element = ELEMENT_EMITTERS[0][0][0]
    known_section = SECTION_EMITTERS[0][0]
    with pytest.raises(RuntimeError, match="two emitters"):
        element_emitter(known_element)(lambda el, ctx: None)
    with pytest.raises(RuntimeError, match="two emitters"):
        section_emitter(known_section)(lambda sec, ctx: None)
