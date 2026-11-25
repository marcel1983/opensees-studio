"""Groups by kind of member and section (core.member_groups)."""

from __future__ import annotations

from types import SimpleNamespace

from opensees_studio.core.member_groups import section_groups, unique_name


def test_a_kind_gets_a_group_per_section_named_after_both() -> None:
    elements = [SimpleNamespace(id=i, section_id=s) for i, s in ((1, 7), (2, 8), (3, 7), (4, 9))]
    sections = [SimpleNamespace(id=7, name="W14X48"), SimpleNamespace(id=8, name="W12X26")]
    sections.append(SimpleNamespace(id=9, name=""))
    taken = {"Braces #9"}
    groups = section_groups(
        {"columns": [1, 2, 3], "braces": [4], "none": []},
        elements=elements,
        sections=sections,
        names={"columns": "Columns", "braces": "Braces", "none": "Nothing"},
        colours={"columns": "#112233"},
        taken=taken,
        first_id=5,
    )
    assert [(g.id, g.name, g.element_ids) for g in groups] == [
        (5, "Columns W14X48", [1, 3]),
        (6, "Columns W12X26", [2]),
        (7, "Braces #9 2", [4]),  # a section without a name goes by its id
    ]
    assert groups[0].colour == "#112233"
    assert {"Columns W14X48", "Columns W12X26", "Braces #9 2"} <= taken


def test_a_taken_name_gets_a_number() -> None:
    taken = {"Columns", "Columns 2"}
    assert unique_name("Columns", taken) == "Columns 3"
    assert "Columns 3" in taken
