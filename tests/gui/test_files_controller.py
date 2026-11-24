"""New, Open and Save live in ``FilesController`` and run with no ``MainWindow``."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMenu, QMessageBox

from opensees_studio.commands import AddNodesCommand
from opensees_studio.core import Node
from opensees_studio.viewmodels.project_vm import ProjectViewModel
from opensees_studio.views.controllers.files import FilesController
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.start_page import RecentFiles

pytestmark = pytest.mark.gui


class _Rig:
    """A controller on a bare window, and a record of what it asked of the window."""

    def __init__(self, qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
        self.parent = QMainWindow()
        qtbot.addWidget(self.parent)
        self.vm = ProjectViewModel(self.parent)
        self.log: list[str] = []
        self.calls: list[str] = []
        self.running = False
        self.recent = RecentFiles(
            QSettings(str(tmp_path / "recent.ini"), QSettings.Format.IniFormat)
        )
        shell = Shell(
            window=self.parent,
            vm=self.vm,
            canvas=lambda: None,  # type: ignore[arg-type, return-value]
            log=self.log.append,
            refresh_actions=lambda: None,
        )

        @contextlib.contextmanager
        def _busy(message: str):  # type: ignore[no-untyped-def]
            self.calls.append(f"busy: {message}")
            yield

        self.files = FilesController(
            shell,
            recent=self.recent,
            recent_changed=lambda: self.calls.append("recent_changed"),
            busy=_busy,
            store_view=lambda: self.calls.append("store_view"),
            restore_view=lambda: self.calls.append("restore_view"),
            offer_stored_results=lambda: self.calls.append("offer_stored_results"),
            is_running=lambda: self.running,
        )

    def edit(self) -> None:
        """One unsaved change."""
        project = self.vm.project
        assert project is not None
        node = Node(id=project.next_node_id(), coords=(1.0, 0.0, 0.0))
        self.vm.apply_command(AddNodesCommand(self.vm, [node]))


def _answer(monkeypatch, button) -> list[str]:  # type: ignore[no-untyped-def]
    """The unsaved-changes box answers ``button``; returns the texts it was shown with."""
    seen: list[str] = []

    def _warning(_parent, _title, text, *_a, **_k):  # type: ignore[no-untyped-def]
        seen.append(text)
        return button

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(_warning))
    return seen


def test_the_window_owns_one_controller_and_the_file_menu_reaches_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.files, FilesController) and mw.files.parent() is mw
    # One list for File → Open Recent and the start page.
    assert mw.files.recent is mw._start_page._recent

    mw.action("file.new").trigger()
    assert mw._vm.project is not None and mw._vm.project.ndm == 3
    mw.action("file.new_2d_truss").trigger()
    assert (mw._vm.project.ndm, mw._vm.project.ndf) == (2, 2)


def test_nothing_unsaved_nothing_asked(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, tmp_path)
    seen = _answer(monkeypatch, QMessageBox.StandardButton.Cancel)

    assert rig.files.confirm_discard("Closing the application")  # no project
    rig.files.new_blank()
    assert rig.vm.project is not None
    assert rig.files.confirm_discard("Closing the application")  # nothing changed
    assert seen == []


def test_unsaved_changes_are_kept_discarded_or_saved(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, tmp_path)
    rig.files.new_blank()
    rig.edit()
    kept = rig.vm.project

    seen = _answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    rig.files.new_blank()
    assert rig.vm.project is kept
    assert seen == [
        "Creating a new project will discard changes that have not been saved.\n\n"
        "Save the project first?"
    ]

    # Save, with the file dialog cancelled: the save did not happen, so nothing is dropped.
    _answer(monkeypatch, QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    assert not rig.files.confirm_discard("Opening another project")
    assert rig.vm.project is kept and rig.vm.is_dirty

    # Save, with a path: written, and it is safe to go on.
    target = tmp_path / "kept.osmodel"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    assert rig.files.confirm_discard("Opening another project")
    assert target.is_file() and not rig.vm.is_dirty
    assert "store_view" in rig.calls  # the viewport goes into the file
    assert rig.recent.paths() == [target.resolve()]

    rig.edit()
    _answer(monkeypatch, QMessageBox.StandardButton.Discard)
    rig.files.new_2d_truss()
    assert rig.vm.project is not kept and rig.vm.project.ndf == 2


def test_save_writes_to_the_path_it_has_and_reports_a_failure(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, tmp_path)
    rig.files.new_blank()
    target = tmp_path / "frame.osmodel"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    assert rig.files.save()  # no path yet: asks for one
    rig.edit()
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: pytest.fail("asked again"))
    )
    assert rig.files.save() and not rig.vm.is_dirty
    assert rig.log[-1] == f"Saved: {rig.vm.path}"

    failures: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda _p, title, *_a, **_k: failures.append(title))
    )

    def _refuse(*_a, **_k):  # type: ignore[no-untyped-def]
        raise OSError("disk full")

    monkeypatch.setattr(rig.vm, "save", _refuse)
    rig.edit()
    assert not rig.files.save()
    assert failures == ["Save failed"]


def test_opening_restores_the_view_and_offers_what_is_stored(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, tmp_path)
    rig.files.new_blank()
    target = tmp_path / "frame.osmodel"
    rig.vm.save(target)
    rig.calls.clear()

    assert rig.files.open_project(target)
    assert rig.calls == ["busy: Opening frame.osmodel…", "restore_view", "offer_stored_results"]
    assert rig.recent.paths() == [target.resolve()]
    assert rig.log[-1] == f"Opened: {target}"

    failures: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda _p, title, *_a, **_k: failures.append(title))
    )
    assert not rig.files.open_project(tmp_path / "missing.osmodel")
    assert failures == ["Open failed"]

    # File → Open: the dialog cancelled opens nothing; a path opens it.
    picked = [("", ""), (str(target), "")]
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: picked.pop(0)))
    rig.calls.clear()
    rig.files.open_file()
    assert rig.calls == []
    rig.files.open_file()
    assert "restore_view" in rig.calls


def test_the_recent_menu_lists_the_projects_and_clears(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    rig = _Rig(qtbot, tmp_path)
    menu = QMenu(rig.parent)
    rig.files.fill_recent_menu(menu)
    assert [a.text() for a in menu.actions() if not a.isSeparator()] == [
        "No recent projects",
        "&Clear List",
    ]

    rig.files.new_blank()
    first, second = tmp_path / "a.osmodel", tmp_path / "b.osmodel"
    rig.vm.save(first)
    rig.vm.save(second)
    rig.recent.add(first)
    rig.recent.add(second)
    rig.files.fill_recent_menu(menu)
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts == ["&1 b.osmodel", "&2 a.osmodel", "&Clear List"]

    menu.actions()[1].trigger()  # the second entry: a.osmodel
    assert rig.vm.path == first

    rig.files.clear_recent()
    assert rig.recent.paths() == [] and rig.calls[-1] == "recent_changed"


def test_the_recovery_copy_waits_for_unsaved_changes_and_for_the_run_to_end(
    qtbot, tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("OPENSEES_STUDIO_DATA_DIR", str(tmp_path / "data"))
    rig = _Rig(qtbot, tmp_path)
    rig.files.autosave()  # no project
    rig.files.new_blank()
    target = tmp_path / "frame.osmodel"
    rig.vm.save(target)
    snapshot = tmp_path / "frame.run-snapshot.osmodel"

    rig.files.autosave()  # nothing unsaved
    assert not snapshot.exists()

    rig.edit()
    rig.running = True
    rig.files.autosave()  # an analysis is writing its own snapshot
    assert not snapshot.exists()

    rig.running = False
    rig.files.autosave()
    assert snapshot.is_file()
    assert target.is_file() and rig.vm.is_dirty  # the project file is not touched
