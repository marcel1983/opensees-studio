"""The project file: New, Open, Open Recent, Save, the recovery copy and the batch door."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

from opensees_studio.commands import SetProjectMetaCommand
from opensees_studio.services import PROJECT_FILE_SUFFIX, load_project, run_snapshot_path
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import ProjectInfoDialog
from opensees_studio.views.dialogs.batch_run import BatchRunDialog
from opensees_studio.views.start_page import RecentFiles


class FilesController(QObject):
    """File → New Blank 3D Model, New 2D Truss, Open, Open Recent, Save, Save As,
    Project Information and Run Batch; the autosaved recovery copy.

    :meth:`confirm_discard` is the one prompt for unsaved changes: New, Open and
    the close of the window all go through it, so the three cannot drift apart.
    :meth:`save` and :meth:`save_as` return ``True`` when the file was written,
    which is what lets that prompt go on after "Save".

    ``recent`` is the list File → Open Recent and the start page share
    (``recent_changed`` tells the start page to read it again). ``busy`` is the
    window's wait cursor, ``store_view`` writes the viewport into the project
    before a save and ``restore_view`` applies the one an opened project
    carries, ``offer_stored_results`` offers what a batch left for the model,
    and ``is_running`` says whether an analysis is under way (no recovery copy
    is written meanwhile).
    """

    def __init__(
        self,
        shell: Shell,
        *,
        recent: RecentFiles,
        recent_changed: Callable[[], None],
        busy: Callable[[str], AbstractContextManager[None]],
        store_view: Callable[[], None],
        restore_view: Callable[[], None],
        offer_stored_results: Callable[[], None],
        is_running: Callable[[], bool],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        #: The projects opened or saved last, newest first.
        self.recent = recent
        self._recent_changed = recent_changed
        self._busy = busy
        self._store_view = store_view
        self._restore_view = restore_view
        self._offer_stored_results = offer_stored_results
        self._is_running = is_running

    def new_blank(self) -> None:
        """File → New Blank 3D Model (and what a command does when no project is open)."""
        if not self.confirm_discard("Creating a new project"):
            return
        self._vm.new_project(dead_case=True, default_materials=True)

    def new_2d_truss(self) -> None:
        """Planar truss model — (ndm=2, ndf=2): only Ux, Uz per joint (the X-Z plane).

        Matches OpenSees's ``model BasicBuilder -ndm 2 -ndf 2`` from
        the Basic Truss Example and keeps the stiffness matrix well
        posed (no empty rotational rows).
        """
        if not self.confirm_discard("Creating a new project"):
            return
        self._vm.new_project(ndm=2, ndf=2, dead_case=True, default_materials=True)
        self._shell.log("New empty project.")

    def open_file(self) -> None:
        """File → Open…"""
        if not self.confirm_discard("Opening another project"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self._window,
            "Open project",
            "",
            f"OpenSees Studio model (*{PROJECT_FILE_SUFFIX});;All files (*)",
        )
        if not path:
            return
        self.open_project(path)

    def open_recent(self, path: str) -> None:
        """File → Open Recent, or a project picked on the start page."""
        if not self.confirm_discard("Opening another project"):
            return
        self.open_project(path)

    def fill_recent_menu(self, menu: QMenu) -> None:
        """Rebuild File → Open Recent from the stored list each time it opens."""
        menu.clear()
        paths = self.recent.paths()
        for number, path in enumerate(paths, 1):
            action = menu.addAction(f"&{number % 10} {path.name}")
            action.setToolTip(str(path))
            action.setStatusTip(str(path))
            action.triggered.connect(lambda _checked=False, p=str(path): self.open_recent(p))
        if not paths:
            menu.addAction("No recent projects").setEnabled(False)
        menu.addSeparator()
        clear = menu.addAction("&Clear List")
        clear.setEnabled(bool(paths))
        clear.triggered.connect(self.clear_recent)

    def clear_recent(self) -> None:
        """Open Recent → Clear List."""
        self.recent.clear()
        self._recent_changed()

    def open_project(self, path: str | Path) -> bool:
        """Open ``path``; offer to restore a newer pre-run snapshot if one exists.

        Returns True when the project was opened (with or without the
        recovered changes).
        """
        try:
            with self._busy(f"Opening {Path(path).name}…"):
                self._vm.open(path)
            self._shell.log(f"Opened: {path}")
        except Exception as exc:
            QMessageBox.critical(self._window, "Open failed", str(exc))
            return False
        self.recent.add(path)
        snapshot = self._vm.pending_run_snapshot()
        if snapshot is None:
            self._restore_view()
            self._confirm_custom_commands()
            self._offer_stored_results()
            return True
        if self.ask_restore_snapshot(snapshot):
            try:
                self._vm.restore_run_snapshot()
                self._shell.log(f"Restored unsaved changes from {snapshot.name} (not yet saved).")
            except Exception as exc:
                QMessageBox.critical(self._window, "Restore failed", str(exc))
        else:
            self._vm.discard_run_snapshot()
            self._shell.log(f"Discarded {snapshot.name}.")
        self._restore_view()
        self._confirm_custom_commands()
        self._offer_stored_results()
        return True

    def _confirm_custom_commands(self) -> None:
        """A file's custom Python blocks run only once the user trusts them."""
        project = self._vm.project
        blocks = [b for b in project.custom_commands if b.enabled] if project is not None else []
        if not blocks:
            return
        names = ", ".join(b.name or str(b.id) for b in blocks)
        answer = QMessageBox.warning(
            self._window,
            "Custom OpenSees commands",
            f"This project contains {len(blocks)} custom Python block(s) ({names}) that run "
            "on this computer when the model is analysed.\n\nRun them only if you trust "
            "where the file came from. Enable them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            for block in blocks:
                block.enabled = False
            self._shell.log(
                f"Custom command blocks disabled: {names}. "
                "Enable them in Define → Custom OpenSees Commands."
            )

    def ask_restore_snapshot(self, snapshot: Path) -> bool:
        """Ask whether the newer pre-run snapshot should replace the file's content."""
        answer = QMessageBox.question(
            self._window,
            "Recover unsaved changes",
            "A snapshot written before the last analysis run is newer than this "
            "project file.\n\nRestore unsaved changes from the last analysis run?\n\n"
            f"Snapshot: {snapshot}\n"
            "Yes loads the snapshot as unsaved changes; No deletes it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def recover_untitled(self) -> None:
        """Start page → Recover: the autosaved never-saved project, as unsaved changes."""
        snapshot = run_snapshot_path(None)
        try:
            project = load_project(snapshot)
        except Exception as exc:
            QMessageBox.critical(self._window, "Recover failed", str(exc))
            return
        self._vm.adopt(project)
        self._shell.log(f"Recovered the unsaved project from {snapshot} (not yet saved).")

    def confirm_discard(self, action: str) -> bool:
        """Ask before throwing away unsaved work. True when it is safe to go on.

        ``is_dirty`` used to drive only the ``*`` in the window title, so
        closing, opening and File → New dropped the model without a word.
        Returns False when the user cancels, or chooses Save and the save
        does not go through (dialog cancelled, write failed).
        """
        if self._vm.project is None or not self._vm.is_dirty:
            return True
        answer = QMessageBox.warning(
            self._window,
            "Unsaved changes",
            f"{action} will discard changes that have not been saved.\n\nSave the project first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return True

    def save(self) -> bool:
        """Save to the current path (asking for one if needed). True when written."""
        if self._vm.path is None:
            return self.save_as()
        try:
            self._store_view()
            self._warn_case_references()
            self._vm.save()
            self._shell.log(f"Saved: {self._vm.path}")
        except Exception as exc:
            QMessageBox.critical(self._window, "Save failed", str(exc))
            return False
        return True

    def save_as(self) -> bool:
        """Ask for a path and save there. True when written."""
        path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save project as",
            "",
            f"OpenSees Studio model (*{PROJECT_FILE_SUFFIX})",
        )
        if not path:
            return False
        try:
            self._store_view()
            self._warn_case_references()
            out = self._vm.save(path)
            self._shell.log(f"Saved: {out}")
        except Exception as exc:
            QMessageBox.critical(self._window, "Save failed", str(exc))
            return False
        self.recent.add(out)
        return True

    def _warn_case_references(self) -> None:
        project = self._vm.project
        if project is None:
            return
        errors = [
            error for case in project.analyses for error in project.case_reference_errors(case)
        ]
        if errors:
            QMessageBox.warning(
                self._window, "Saving with invalid case references", "\n".join(errors)
            )

    def autosave(self) -> None:
        """Write the recovery copy of unsaved changes (the project file is not touched).

        It is the same copy a run writes before it starts: opening the project
        after a crash offers it, and a save removes it.
        """
        if self._vm.project is None or not self._vm.is_dirty or self._is_running():
            return
        try:
            path = self._vm.write_run_snapshot()
        except OSError as exc:
            self._shell.log(f"Autosave failed: {exc}")
            return
        self._window.statusBar().showMessage(f"Recovery copy saved ({path.name}).", 3000)

    def project_info(self) -> None:
        """File → Project Information: the cover data of the calculation report."""
        project = self._vm.project
        if project is None:
            return
        dialog = ProjectInfoDialog(project.meta, self._window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._vm.apply_command(SetProjectMetaCommand(self._vm, dialog.meta()))
        self._shell.log("Project information updated.")

    def run_batch(self) -> None:
        """File → Run Batch…"""
        start_dir = self._vm.path.parent if self._vm.path is not None else None
        dlg = BatchRunDialog(self._window, start_dir=start_dir)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()
