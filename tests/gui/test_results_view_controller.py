"""The results on screen live in ``ResultsViewController`` and run with no ``MainWindow``."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QInputDialog, QMainWindow, QMessageBox

from opensees_studio.core import (
    CombinationTerm,
    ElasticBeamColumn,
    LinearTimeSeries,
    LoadCombination,
    Node,
    PlainLoadPattern,
    Project,
    StaticCase,
)
from opensees_studio.services.results import StaticResults
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.viewmodels.results_session import ResultsSession
from opensees_studio.views.controllers.results_view import ResultsViewController
from opensees_studio.views.controllers.shell import Shell

pytestmark = pytest.mark.gui

_ACTIONS = (
    "display.show_reactions",
    "display.reactions_table",
    "display.reactions_dialog",
)


class _Canvas:
    """What the controller asks of the viewport: draw these reactions, or hide them."""

    def __init__(self) -> None:
        self.reactions: list[tuple[int, bool]] = []

    def set_reactions(self, rows, *, show: bool) -> None:  # type: ignore[no-untyped-def]
        self.reactions.append((len(rows), show))


class _Rig:
    """A controller on a bare window, and a record of what it asked of the window."""

    def __init__(self, qtbot, project: Project | None) -> None:  # type: ignore[no-untyped-def]
        self.parent = QMainWindow()
        qtbot.addWidget(self.parent)
        self.vm = ProjectViewModel(self.parent)
        if project is not None:
            self.vm.adopt(project)
        self.results = ResultsSession()
        self.canvas = _Canvas()
        self.log: list[str] = []
        self.calls: list[str] = []
        self.captions: list[str] = []
        self.actions = {name: QAction(name, self.parent) for name in _ACTIONS}
        self.actions["display.show_reactions"].setCheckable(True)
        shell = Shell(
            window=self.parent,
            vm=self.vm,
            canvas=lambda: self.canvas,  # type: ignore[arg-type, return-value]
            log=self.log.append,
            refresh_actions=lambda: self.calls.append("refresh_actions"),
        )
        self.view = ResultsViewController(
            shell,
            results=self.results,
            lock=lambda: self.calls.append("lock"),
            unlock=lambda: self.calls.append("unlock"),
            set_caption=self.captions.append,
            back_to_model=lambda: self.calls.append("back_to_model"),
            show_reactions_dock=lambda: self.calls.append("reactions_dock"),
            action=lambda action_id: self.actions[action_id],
        )
        self.actions["display.show_reactions"].triggered.connect(self.view.show_reactions)


def _project() -> Project:
    """One member, two static cases and an envelope of the two."""
    project = Project(ndm=3, ndf=6)
    project.nodes.extend([Node(id=1, coords=(0, 0, 0)), Node(id=2, coords=(4, 0, 0))])
    project.elements.append(ElasticBeamColumn(id=10, nodes=(1, 2), section_id=1))
    project.time_series.append(LinearTimeSeries(id=1, name="Ramp"))
    project.load_patterns.extend(
        [
            PlainLoadPattern(id=1, name="DEAD", time_series_id=1),
            PlainLoadPattern(id=2, name="LIVE", time_series_id=1),
        ]
    )
    project.analyses.extend(
        [
            StaticCase(id=1, name="DEAD", pattern_ids=[1]),
            StaticCase(id=2, name="LIVE", pattern_ids=[2]),
        ]
    )
    project.combinations.append(
        LoadCombination(
            id=1,
            name="ENV",
            combination_type="Envelope",
            terms=[CombinationTerm(ref_id=1), CombinationTerm(ref_id=2)],
        )
    )
    return project


def _static(case_id: int, name: str, *, steps: int = 1) -> StaticResults:
    return StaticResults(
        case_id=case_id,
        case_name=name,
        n_steps=steps,
        node_disp={1: np.zeros((steps, 6)), 2: np.zeros((steps, 6))},
        node_reaction={1: np.tile([100.0, 0.0, 0.0, 0.0, 0.0, 0.0], (steps, 1))},
        element_forces={10: np.zeros((steps, 12))},
    )


def test_the_window_owns_one_controller_and_places_its_widgets(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    view = mw.results_view
    assert isinstance(view, ResultsViewController) and view.parent() is mw
    for widget in (view.panel, view.reactions_panel, view.case_combo, view.step_back):
        assert widget.window() is mw
    assert mw._act_select_results is mw.action("display.select_results")
    assert mw._act_clear_results is mw.action("analyze.clear_results")
    assert mw.action("display.show_reactions").isCheckable()
    # A project with nothing run: no reactions to show, no case to choose.
    mw._vm.new_project()
    assert not mw.action("display.show_reactions").isEnabled()
    assert view.case_combo.count() == 0


def test_showing_a_case_points_everything_at_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, _project())
    dead, live = _static(1, "DEAD"), _static(2, "LIVE")
    rig.view.keep(dead)
    rig.view.keep(live)
    assert rig.calls == ["lock", "lock"]

    rig.view.on_finished(dead)

    assert rig.results.latest is dead
    assert [rig.view.case_combo.itemText(i) for i in range(2)] == [
        "DEAD · Static",
        "LIVE · Static",
    ]
    assert rig.view.case_combo.currentData() == 1 and rig.view.case_combo.isEnabled()
    assert rig.captions[-1] == "DEAD  ·  Static"
    assert rig.log == ["Analysis complete: DEAD  ·  Static."]
    assert all(rig.actions[name].isEnabled() for name in _ACTIONS)
    assert rig.canvas.reactions[-1] == (1, False)  # known, not drawn until asked for
    assert "refresh_actions" in rig.calls

    # The Case list of the toolbar repoints the window.
    rig.view.case_combo.setCurrentIndex(rig.view.case_combo.findData(2))
    assert rig.results.latest is live
    assert rig.captions[-1] == "LIVE  ·  Static"


def test_the_reactions_follow_the_tick_and_go_with_the_results(qtbot) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, _project())
    dead = _static(1, "DEAD")
    rig.view.keep(dead)
    rig.view.show(dead)
    overlay = rig.actions["display.show_reactions"]

    overlay.trigger()
    assert rig.canvas.reactions[-1] == (1, True)
    rig.view.reactions_table()
    assert rig.calls[-1] == "reactions_dock"

    rig.view.drop()

    assert rig.results.latest is None and rig.results.current(rig.vm.project) == {}
    assert not overlay.isChecked() and not overlay.isEnabled()
    assert rig.canvas.reactions[-1] == (0, False)
    assert rig.view.case_combo.count() == 0 and not rig.view.case_combo.isEnabled()
    assert rig.calls[-1] == "back_to_model"
    assert rig.view.panel.tables() == []


def test_a_key_resolves_to_results_or_says_why_not(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, _project())
    told: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text, *a, **k: told.append(text))

    assert rig.view.for_key("case:x") is None
    assert rig.view.for_key("case:1") is None
    assert rig.log == ["Case 1 has no current results: run it first."]
    assert rig.view.for_key("combination:1") is None  # its cases have not run
    assert len(told) == 1 and "Analyze → Run" in told[0]
    assert not rig.view.show_results_of("combination:1")

    dead, live = _static(1, "DEAD"), _static(2, "LIVE")
    rig.view.keep(dead)
    rig.view.keep(live)
    assert rig.view.for_key("case:2") is live
    assert rig.view.show_results_of("combination:1")
    assert rig.results.is_envelope()
    assert rig.captions[-1] == "ENV  ·  envelope"
    assert "back_to_model" in rig.calls


def test_show_results_of_offers_what_the_session_can_show(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    empty = _Rig(qtbot, None)
    told: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text, *a, **k: told.append(text))
    empty.view.pick()
    assert told and told[0].startswith("No results yet")

    rig = _Rig(qtbot, _project())
    dead = _static(1, "DEAD")
    rig.view.keep(dead)
    offered: list[list[str]] = []

    def _choose(_parent, _title, _label, items, *_a, **_k):  # type: ignore[no-untyped-def]
        offered.append(list(items))
        return items[0], True

    monkeypatch.setattr(QInputDialog, "getItem", _choose)
    rig.view.pick()

    assert offered == [["Case: DEAD  [StaticResults]", "Combination: ENV"]]
    assert rig.results.latest is dead


def test_the_step_arrows_wait_for_a_layer_that_can_step(qtbot) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, _project())
    pushed = _static(1, "DEAD", steps=3)
    rig.view.keep(pushed)
    rig.view.show(pushed)
    assert rig.view.step_label.text() == "Step 1/3"
    assert not rig.view.step_forward.isEnabled()  # nobody can redraw a step yet

    drawn: list[int] = []
    rig.view.step_apply = drawn.append
    rig.view.show(pushed)
    assert rig.view.step_forward.isEnabled() and rig.view.step_back.isEnabled()

    rig.view.step_forward.click()
    rig.view.shift_step(5)  # stops at the last step
    rig.view.shift_step(1)  # already there: nothing to redraw
    assert drawn == [1, 2]
    assert rig.view.step_label.text() == "Step 3/3"


def test_delete_all_results_asks_first(qtbot, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, _project())
    rig.vm._path = tmp_path / "model.osmodel"
    dead = _static(1, "DEAD")
    rig.view.on_case_finished(dead)  # kept, and written to the results database
    rig.view.show(dead)
    db = tmp_path / "model_results.sqlite"
    assert db.exists()
    answers = [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: answers.pop(0))

    rig.view.delete_all()
    assert rig.results.latest is dead and db.exists() and "unlock" not in rig.calls

    rig.view.delete_all()
    assert rig.results.latest is None and not db.exists()
    assert "unlock" in rig.calls
    assert rig.log[-1] == "All results deleted."
