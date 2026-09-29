"""Numberer, system and system-argument controls of the stepped case forms."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from opensees_studio.core import PlainLoadPattern, PushoverCase, StaticCase, TransientCase
from opensees_studio.views.dialogs.case_forms import (
    PushoverCaseForm,
    StaticCaseForm,
    TransientCaseForm,
)

PATTERNS = [PlainLoadPattern(id=1, time_series_id=1)]


@pytest.mark.gui
def test_static_form_defaults_and_plain_sparse_general_piv(qtbot) -> None:  # type: ignore[no-untyped-def]
    form = StaticCaseForm(PATTERNS, [])
    qtbot.addWidget(form)
    rows = form._solver
    default = form.read(1)
    assert (default.numberer, default.system, default.system_args) == ("RCM", "BandGeneral", ())
    assert not rows.args.isEnabled()

    rows.numberer.setCurrentText("Plain")
    rows.system.setCurrentText("SparseGeneral")
    assert rows.args.isEnabled()
    assert [rows.args.itemText(i) for i in range(rows.args.count())] == ["(none)", "-piv"]
    rows.args.setCurrentText("-piv")
    case = form.read(1)
    assert (case.numberer, case.system, case.system_args) == ("Plain", "SparseGeneral", ("-piv",))

    # switching to a system without arguments drops them
    rows.system.setCurrentText("UmfPack")
    assert form.read(1).system_args == ()


@pytest.mark.gui
@pytest.mark.parametrize(
    ("form_cls", "case"),
    [
        (
            StaticCaseForm,
            StaticCase(
                id=4,
                pattern_ids=[1],
                numberer="AMD",
                system="SparseGeneral",
                system_args=("-piv",),
            ),
        ),
        (
            TransientCaseForm,
            TransientCase(
                id=4, pattern_ids=[1], dt=0.01, n_steps=5, numberer="Plain", system="FullGeneral"
            ),
        ),
        (
            PushoverCaseForm,
            PushoverCase(
                id=4,
                pattern_ids=[1],
                control_node=2,
                control_dof=1,
                target_disp=0.1,
                numberer="Plain",
                system="ProfileSPD",
            ),
        ),
    ],
)
def test_forms_round_trip_the_options(qtbot, form_cls, case) -> None:  # type: ignore[no-untyped-def]
    form = form_cls(PATTERNS, [])
    qtbot.addWidget(form)
    form.populate(case)
    read = form.read()
    assert (read.numberer, read.system, read.system_args) == (
        case.numberer,
        case.system,
        case.system_args,
    )
