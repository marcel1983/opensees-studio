"""Solver engines: settings, detection without importing, other Pythons, plug-ins."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from opensees_studio.services import engines


@pytest.fixture(autouse=True)
def _data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OPENSEES_STUDIO_DATA_DIR", str(tmp_path / "data"))
    return tmp_path


def _without_own_opensees(monkeypatch: pytest.MonkeyPatch) -> None:
    """This environment has OpenSeesPy (dev installs it): pretend it does not."""
    real = importlib.util.find_spec

    def find_spec(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "openseespy":
            for entry in sys.path:
                if (Path(entry) / "openseespy" / "__init__.py").is_file() and "fake" in entry:
                    return real(name, *args, **kwargs)
            return None
        return real(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)


def _fake_package(folder: Path, version: str = "3.8.0.0") -> Path:
    (folder / "openseespy").mkdir(parents=True)
    (folder / "openseespy" / "__init__.py").write_text("", encoding="utf-8")
    info = folder / f"openseespy-{version}.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: openseespy\nVersion: {version}\n", encoding="utf-8"
    )
    return folder


def test_settings_round_trip_and_defaults() -> None:
    assert engines.load_settings() == engines.SolverSettings()
    chosen = engines.SolverSettings(package_dir="/opt/os", python="/usr/bin/python3.12")
    engines.save_settings(chosen)
    assert engines.load_settings() == chosen
    assert json.loads(engines.settings_path().read_text())["package_dir"] == "/opt/os"


def test_unreadable_settings_fall_back_to_the_defaults() -> None:
    engines.settings_path().parent.mkdir(parents=True)
    engines.settings_path().write_text("{not json", encoding="utf-8")
    assert engines.load_settings() == engines.SolverSettings()


def test_this_environment_has_opensees() -> None:
    status = engines.current_status(engines.SolverSettings())
    assert status.available
    assert status.version == importlib.metadata.version("openseespy")
    assert "Static" in status.case_types


def test_without_opensees_the_status_says_how_to_get_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _without_own_opensees(monkeypatch)
    status = engines.current_status(engines.SolverSettings())
    assert not status.available
    assert "Options → Solver" in status.message
    assert "not available" in status.summary()


def test_a_folder_with_the_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_own_opensees(monkeypatch)
    folder = _fake_package(tmp_path / "fake-site", "3.8.0.0")
    settings = engines.SolverSettings(package_dir=str(folder))
    status = engines.current_status(settings)
    assert (status.available, status.version, status.location) == (True, "3.8.0.0", str(folder))
    assert engines.child_environment(settings) == {engines.ENGINE_PATH_ENV: str(folder)}


def test_a_folder_without_the_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_own_opensees(monkeypatch)
    status = engines.current_status(engines.SolverSettings(package_dir=str(tmp_path)))
    assert not status.available
    assert f"No openseespy package in {tmp_path}" in status.message


def test_this_environment_wins_over_a_folder(tmp_path: Path) -> None:
    folder = _fake_package(tmp_path / "other")
    status = engines.current_status(engines.SolverSettings(package_dir=str(folder)))
    assert status.available and "is not used" in status.message


def test_activate_appends_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    engines.activate(str(tmp_path))
    engines.activate(str(tmp_path))
    assert sys.path[-1] == str(tmp_path) and sys.path.count(str(tmp_path)) == 1
    engines.activate(None)
    monkeypatch.setenv(engines.ENGINE_PATH_ENV, str(tmp_path / "x"))
    engines.activate_from_environment()
    assert sys.path[-1] == str(tmp_path / "x")


def test_inspect_this_python() -> None:
    settings = engines.inspect_python(sys.executable)
    assert settings.python == sys.executable
    assert (Path(settings.package_dir) / "openseespy" / "__init__.py").is_file()  # type: ignore[arg-type]


def test_inspect_a_missing_interpreter(tmp_path: Path) -> None:
    with pytest.raises(engines.EngineError, match="Could not run"):
        engines.inspect_python(str(tmp_path / "no-python"))


@pytest.mark.skipif(os.name == "nt", reason="a shell script stands in for another Python")
@pytest.mark.parametrize(
    ("answer", "message"),
    [
        ('{"python": [3, 11]}', "is Python 3.11"),
        (f'{{"python": [{sys.version_info[0]}, {sys.version_info[1]}]}}', "has no openseespy"),
        ("not json", "not a Python interpreter"),
    ],
)
def test_inspect_refuses_another_version_or_no_openseespy(
    tmp_path: Path, answer: str, message: str
) -> None:
    fake = tmp_path / "python"
    fake.write_text(f"#!/bin/sh\necho '{answer}'\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    with pytest.raises(engines.EngineError, match=message):
        engines.inspect_python(str(fake))


class _Engine:
    key = "toy"
    name = "Toy solver"
    case_types = frozenset({"Static"})

    def status(self, settings):  # type: ignore[no-untyped-def]
        return engines.EngineStatus(engine=self.key, name=self.name, available=True)

    def child_environment(self, settings):  # type: ignore[no-untyped-def]
        return {"TOY": "1"}


class _Entry:
    def __init__(self, target) -> None:  # type: ignore[no-untyped-def]
        self._target = target

    def load(self):  # type: ignore[no-untyped-def]
        if isinstance(self._target, Exception):
            raise self._target
        return self._target


def test_plug_in_engines_register_and_broken_ones_are_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda group: [_Entry(_Engine), _Entry(ImportError("broken"))],
    )
    found = engines.engines()
    assert set(found) == {engines.OPENSEES_PY, "toy"}
    toy = engines.SolverSettings(engine="toy")
    assert engines.current_status(toy).name == "Toy solver"
    assert engines.child_environment(toy) == {"TOY": "1"}
    # An engine that is not installed falls back to the built-in one.
    assert engines.engine_for(engines.SolverSettings(engine="gone")).key == engines.OPENSEES_PY


def test_the_cli_reports_a_missing_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    from opensees_studio import run

    class _Protocol:
        lines: list[dict] = []  # noqa: RUF012

        def emit(self, **payload) -> None:  # type: ignore[no-untyped-def]
            self.lines.append(payload)

    protocol = _Protocol()
    assert run._solver_missing(protocol) is False  # type: ignore[arg-type]
    _without_own_opensees(monkeypatch)
    assert run._solver_missing(protocol) is True  # type: ignore[arg-type]
    (line,) = protocol.lines
    assert line["type"] == "error" and "Options → Solver" in line["message"]
