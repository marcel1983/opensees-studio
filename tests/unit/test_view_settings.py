"""Unit tests for the per-viewport display settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from opensees_studio.core.view_settings import ViewSettings


def test_defaults_match_the_historic_renderer_colours() -> None:
    settings = ViewSettings()

    assert settings.show_nodes is True
    assert settings.show_grids is True
    assert settings.show_node_labels is False
    assert settings.node_color == "#d9d9d9"
    assert settings.frame_color == "#338cd9"
    assert settings.surface_color == "#a8b6c4"
    assert settings.selected_color == "#00ffff"


def test_is_immutable() -> None:
    settings = ViewSettings()

    with pytest.raises(ValidationError):
        settings.show_nodes = False  # type: ignore[misc]


def test_with_changes_returns_a_new_instance() -> None:
    original = ViewSettings()

    updated = original.with_changes(show_nodes=False)

    assert updated is not original
    assert updated.show_nodes is False
    assert original.show_nodes is True
    assert updated.show_frames is original.show_frames


def test_with_changes_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unknown view setting"):
        ViewSettings().with_changes(show_everything=False)


@pytest.mark.parametrize("colour", ["#ffffff", "#000000", "#00FFFF"])
def test_accepts_six_digit_hex_colours(colour: str) -> None:
    assert ViewSettings(node_color=colour).node_color == colour


@pytest.mark.parametrize("colour", ["white", "#fff", "#gggggg", "00ffff"])
def test_rejects_invalid_colours(colour: str) -> None:
    with pytest.raises(ValidationError):
        ViewSettings(node_color=colour)


def test_luts_put_the_selection_colour_second() -> None:
    settings = ViewSettings(node_color="#111111", selected_color="#222222")

    assert settings.node_lut == ["#111111", "#222222"]
    assert settings.frame_lut[1] == "#222222"
    assert settings.surface_lut[1] == "#222222"


def test_settings_round_trip_as_a_dict() -> None:
    settings = ViewSettings(show_loads=False, background_top="#123456")

    restored = ViewSettings(**settings.model_dump())

    assert restored == settings


def test_a_project_without_view_settings_saves_it_untouched() -> None:
    """A project that never touched View → Visibility dumps as before."""
    from opensees_studio.core import Project

    payload = Project().model_dump(mode="json")

    assert "view" not in payload


def test_a_customised_view_travels_with_the_project() -> None:
    from opensees_studio.core import Project

    project = Project()
    project.view = ViewSettings(show_loads=False, frame_color="#ff0000")

    payload = project.model_dump(mode="json")
    restored = Project.model_validate(payload)

    assert payload["view"]["show_loads"] is False
    assert restored.view is not None
    assert restored.view.frame_color == "#ff0000"
