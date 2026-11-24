"""The Case combo lists the cases and switching one repoints the window."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from opensees_studio.services.results import StaticResults
from opensees_studio.views.main_window import MainWindow


@pytest.fixture
def window(qtbot):  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    w._vm.new_project()
    return w


def _case(case_id: int, name: str) -> StaticResults:
    return StaticResults(case_id=case_id, case_name=name, n_steps=1)


@pytest.mark.gui
def test_showing_a_case_fills_the_combo(window) -> None:  # type: ignore[no-untyped-def]
    """The first bug here was `_display_results` never refreshing the list."""
    results = _case(1, "DEAD")
    window.results.cases.put(window._vm.project, results)

    window.results_view.show(results)

    assert window.results_view.case_combo.count() == 1
    assert window.results_view.case_combo.itemText(0) == "DEAD · Static"
    assert window.results_view.case_combo.isEnabled()


@pytest.mark.gui
def test_choosing_another_case_repoints_the_window(window) -> None:  # type: ignore[no-untyped-def]
    first, second = _case(1, "DEAD"), _case(2, "EQX")
    window.results.cases.put(window._vm.project, first)
    window.results.cases.put(window._vm.project, second)
    window.results_view.show(first)
    assert window.results.latest is first

    index = window.results_view.case_combo.findData(2)
    window.results_view.case_combo.setCurrentIndex(index)

    assert window.results.latest is second


@pytest.mark.gui
def test_without_results_the_combo_is_empty_and_disabled(window) -> None:  # type: ignore[no-untyped-def]
    window.results_view.refresh_case_combo()

    assert window.results_view.case_combo.count() == 0
    assert not window.results_view.case_combo.isEnabled()


@pytest.mark.gui
def test_renaming_a_case_relabels_the_results(window) -> None:  # type: ignore[no-untyped-def]
    """The numbers did not move: only the label has to follow."""
    from opensees_studio.commands import AddAnalysisCasesCommand, RenameAnalysisCaseCommand
    from opensees_studio.core import StaticCase

    window._vm.apply_command(
        AddAnalysisCasesCommand(window._vm, [StaticCase(id=1, name="DEAD", pattern_ids=[1])])
    )
    results = _case(1, "DEAD")
    window.results.cases.put(window._vm.project, results)
    window.results_view.show(results)
    assert window.results_view.case_combo.itemText(0) == "DEAD · Static"

    window._vm.apply_command(RenameAnalysisCaseCommand(window._vm, 1, "GRAVITY"))

    assert window.results_view.case_combo.itemText(0) == "GRAVITY · Static"
    assert window.results.latest is results
    assert window.results.caption_for(window._vm.project, results).startswith("GRAVITY")
