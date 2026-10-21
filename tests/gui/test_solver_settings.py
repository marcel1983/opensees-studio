"""Options → Solver, and what the window does without a solver."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QDialog

from opensees_studio.services import engines
from opensees_studio.views.dialogs.solver_settings import SolverSettingsDialog

MISSING = engines.EngineStatus(
    engine=engines.OPENSEES_PY,
    name="OpenSeesPy",
    available=False,
    message="OpenSeesPy is not installed. Point to an installation in Options → Solver.",
)


@pytest.fixture(autouse=True)
def _data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENSEES_STUDIO_DATA_DIR", str(tmp_path / "data"))


def _window(qtbot):  # type: ignore[no-untyped-def]
    from opensees_studio.views.main_window import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw._vm.new_project(ndm=3, ndf=6, dead_case=True)
    mw._refresh_action_enablement()
    return mw


@pytest.mark.gui
def test_with_a_solver_everything_runs(qtbot) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    assert mw._solver.available
    for action in (mw._act_run, mw._act_run_all, mw._act_check_stability, mw._act_material_tester):
        assert action.isEnabled()


@pytest.mark.gui
def test_without_a_solver_the_analysis_tools_wait_and_modelling_does_not(
    qtbot, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(engines, "current_status", lambda settings=None: MISSING)
    mw = _window(qtbot)

    for action in (mw._act_run, mw._act_run_all, mw._act_check_stability, mw._act_material_tester):
        assert not action.isEnabled()
    assert "Options → Solver" in mw._act_run.statusTip()
    assert mw._act_export_script.isEnabled()
    assert mw._act_frame_wizard.isEnabled()


@pytest.mark.gui
def test_choosing_a_folder_is_saved_and_applied(qtbot, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mw = _window(qtbot)
    folder = Path(importlib.util.find_spec("openseespy").origin).parents[1]  # type: ignore[arg-type]

    def _fake_exec(self: SolverSettingsDialog) -> int:
        self._folder_radio.setChecked(True)
        self._folder_edit.setText(str(folder))
        self._refresh()
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(SolverSettingsDialog, "exec", _fake_exec)
    mw._act_solver_settings.trigger()

    assert engines.load_settings().package_dir == str(folder)
    assert mw._solver.available


@pytest.mark.gui
def test_the_dialog_refuses_what_it_cannot_use(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    dialog = SolverSettingsDialog(engines.SolverSettings())
    qtbot.addWidget(dialog)
    assert dialog._ok.isEnabled()
    assert "Ready" in dialog._status.text()

    dialog._folder_radio.setChecked(True)  # no folder chosen yet
    assert not dialog._ok.isEnabled()

    dialog._python_radio.setChecked(True)
    dialog._python_edit.setText(str(tmp_path / "no-python"))
    dialog._refresh()
    assert not dialog._ok.isEnabled()
    assert "Could not run" in dialog._status.text()


# ──────────────────────────── the download ────────────────────────────
@pytest.mark.gui
def test_the_download_needs_the_license_and_then_points_at_the_folder(
    qtbot, monkeypatch, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.viewmodels import engine_installer

    calls: list[Path] = []

    def fake_install(root, *, progress, cancelled):  # type: ignore[no-untyped-def]
        folder = tmp_path / "engines" / "openseespy-3.8.0.0"
        calls.append(folder)
        progress(50, 100)
        progress(100, 100)
        return engines.SolverSettings(package_dir=str(folder))

    monkeypatch.setattr(engine_installer, "install_opensees", fake_install)
    dialog = SolverSettingsDialog(engines.SolverSettings())
    qtbot.addWidget(dialog)

    monkeypatch.setattr(SolverSettingsDialog, "accept_license", lambda self: False)
    dialog._download.click()
    assert calls == []  # no acceptance, no download

    monkeypatch.setattr(SolverSettingsDialog, "accept_license", lambda self: True)
    dialog._download.click()
    with qtbot.waitSignal(dialog._installer.installed, timeout=10_000, raising=False):
        pass
    qtbot.waitUntil(lambda: dialog._folder_edit.text() != "", timeout=10_000)

    assert calls and dialog._folder_radio.isChecked()
    assert dialog._folder_edit.text() == str(calls[0])
    assert dialog._download.isEnabled()


@pytest.mark.gui
def test_a_failed_download_is_reported(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from opensees_studio.services.engine_install import InstallError
    from opensees_studio.viewmodels import engine_installer

    def failing(root, *, progress, cancelled):  # type: ignore[no-untyped-def]
        raise InstallError("Could not download openseespy: offline")

    monkeypatch.setattr(engine_installer, "install_opensees", failing)
    monkeypatch.setattr(SolverSettingsDialog, "accept_license", lambda self: True)
    dialog = SolverSettingsDialog(engines.SolverSettings())
    qtbot.addWidget(dialog)
    dialog._download.click()
    qtbot.waitUntil(lambda: "offline" in dialog._status.text(), timeout=10_000)
    assert dialog._download.isEnabled()
