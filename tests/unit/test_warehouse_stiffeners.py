"""Roof stiffeners and the kinds of wall bracing of a generated warehouse."""

from __future__ import annotations

import itertools

import pytest

from opensees_studio.core.warehouse import (
    SECTION_KEYS,
    Warehouse,
    WarehouseError,
    WarehouseSpec,
    build_warehouse,
    roof_pressure_loads,
)

SECTIONS = {key: n for n, key in enumerate(SECTION_KEYS, start=1)}


def _spec(**fields):  # type: ignore[no-untyped-def]
    values = {
        "span": 20.0, "eave_height": 6.0, "frame_spacing": 6.0, "n_frames": 4,
        "purlin_spacing": 1.0, **fields,
    }  # fmt: skip
    return WarehouseSpec(**values)


def _build(**fields) -> Warehouse:  # type: ignore[no-untyped-def]
    return build_warehouse(_spec(**fields), SECTIONS, first_node_id=1, first_element_id=1)


@pytest.mark.parametrize(
    "fields",
    [
        {"roof_stiffeners": "cable"},
        {"wall_bracing_type": "k"},
        {"roof_stiffeners": "beam", "stiffener_lines": -1},
        {"roof_stiffeners": "truss"},  # no depth
        {"roof_stiffeners": "truss", "stiffener_depth": 7.0},
        {
            "roof_stiffeners": "truss",
            "stiffener_depth": 0.6,
            "roof_structure": "truss",
            "truss_depth": 1.0,
        },
    ],
)
def test_stiffeners_that_cannot_be_built_are_refused(fields: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(WarehouseError):
        _spec(**fields)


def test_stiffener_beams_take_the_place_of_the_purlins_on_their_lines() -> None:
    plain = _build()
    warehouse = _build(roof_stiffeners="beam", stiffener_lines=1)
    by_id = {e.id: e for e in warehouse.elements}
    stiffeners = warehouse.members["roof_stiffeners"]
    lines = sorted({warehouse.stations[warehouse.purlin_station[i]].x for i in stiffeners})
    # Mid-span and one line each side, on the nearest purlin lines (10 / 11 m apart).
    assert lines == pytest.approx([50 / 11, 10.0, 160 / 11])
    assert len(stiffeners) == 3 * 3
    assert len(warehouse.members["purlins"]) == len(plain.members["purlins"]) - 9
    assert {by_id[i].section_id for i in stiffeners} == {SECTIONS["stiffener"]}
    assert not any(by_id[i].releases.any for i in stiffeners)  # framed into the rafters
    # They carry the roof as the purlins did.
    assert sum(
        load.wz for load in roof_pressure_loads(warehouse, 1.0, projected=True)
    ) == pytest.approx(sum(load.wz for load in roof_pressure_loads(plain, 1.0, projected=True)))
    assert warehouse.spec.section_keys().count("stiffener") == 1
    assert "stiffener_chord" not in warehouse.spec.section_keys()


def test_the_roof_x_braces_lie_within_the_spaces_between_stiffeners() -> None:
    warehouse = _build(roof_stiffeners="beam", stiffener_lines=1)
    nodes = {n.id: n for n in warehouse.nodes}
    by_id = {e.id: e for e in warehouse.elements}
    cuts = [0.0, 50 / 11, 10.0, 160 / 11, 20.0]
    for element_id in warehouse.members["roof_bracing"]:
        xs = sorted(nodes[n].coords[0] for n in by_id[element_id].nodes)
        # Both ends in one space: no X crosses a stiffener line.
        assert any(a - 1e-9 <= xs[0] and xs[1] <= b + 1e-9 for a, b in itertools.pairwise(cuts))
    two = _build(roof_stiffeners="beam", roof_bracing_panels=2)
    assert len(two.members["roof_bracing"]) == 2 * 2 * 2 * 2  # bays × spaces × panels × diagonals


def test_a_stiffening_truss_hangs_under_its_line_with_a_web() -> None:
    warehouse = _build(roof_stiffeners="truss", stiffener_depth=0.8)
    nodes = {n.id: n for n in warehouse.nodes}
    by_id = {e.id: e for e in warehouse.elements}
    chords = warehouse.members["roof_stiffeners"]
    webs = warehouse.members["stiffener_webs"]
    assert len(chords) == 3 + 3  # top chord (the purlin's place) and bottom chord
    assert len(webs) == 4 + 3  # a vertical at every frame, a diagonal per bay
    bottom = [n for i in chords for n in by_id[i].nodes if nodes[n].coords[2] < 7.0 - 0.5]
    assert {round(nodes[n].coords[2], 9) for n in bottom} == {round(7.0 - 0.8, 9)}
    assert {by_id[i].section_id for i in chords} == {SECTIONS["stiffener_chord"]}
    assert {by_id[i].section_id for i in webs} == {SECTIONS["stiffener_web"]}
    assert all(by_id[i].releases.any for i in webs)


def test_a_double_x_has_a_strut_at_mid_height() -> None:
    bare = _build(wall_bracing_type="double_x")
    by_id = {e.id: e for e in bare.elements}
    nodes = {n.id: n for n in bare.nodes}
    struts = bare.members["wall_struts"]
    assert len(struts) == 2 * 2  # two braced bays, two side walls
    assert {nodes[n].coords[2] for i in struts for n in by_id[i].nodes} == {3.0}
    assert len(bare.members["wall_bracing"]) == 2 * 2 * 4
    # With girts the girt line nearest mid-height is the strut, and keeps its wind.
    girts = _build(wall_bracing_type="double_x", girt_spacing=1.5)
    struts = girts.members["wall_struts"]
    assert len(struts) == 4 and all(i in girts.wall_girts for i in struts)
    assert {girts.wall_girts[i][2] for i in struts} == {3.0}
    assert len(girts.members["girts"]) == 3 * 3 * 2 - 4


def test_a_moment_frame_wall_has_a_framed_eave_beam_and_no_x() -> None:
    warehouse = _build(wall_bracing_type="moment_frame")
    by_id = {e.id: e for e in warehouse.elements}
    beams = warehouse.members["wall_beams"]
    assert warehouse.members["wall_bracing"] == []
    assert len(beams) == 2 * 2
    assert not any(by_id[i].releases.any for i in beams)
    assert {warehouse.purlin_station[i] for i in beams} == {0, len(warehouse.stations) - 1}
    assert {by_id[i].section_id for i in beams} == {SECTIONS["wall_beam"]}
