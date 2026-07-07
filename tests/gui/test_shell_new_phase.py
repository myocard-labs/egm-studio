"""Tests for File > New phase wiring in the shell (Block 10e)."""

from __future__ import annotations

import types
from pathlib import Path

import pytest
from myocard_egm_data.phases import MANIFEST_FILENAME, load_phase_dir
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui import shell as shell_mod
from myocard_egm_studio.gui.shell import MainWindow
from myocard_egm_studio.save import empty_manifest, save_manifest


def _window(qtbot: QtBot) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def _stub_dialog(
    monkeypatch: pytest.MonkeyPatch, *, folder: Path, phase: float, accepted: bool = True
) -> None:
    """Replace NewPhaseDialog so _new_phase runs without a modal popup."""
    code = QtWidgets.QDialog.DialogCode
    fake = types.SimpleNamespace(
        exec=lambda: code.Accepted if accepted else code.Rejected,
        folder=lambda: str(folder),
        phase=lambda: phase,
    )
    monkeypatch.setattr(shell_mod, "NewPhaseDialog", lambda _parent: fake)


def test_new_phase_creates_and_opens_an_empty_phase(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = _window(qtbot)
    folder = tmp_path / "phase_1_5"
    folder.mkdir()
    _stub_dialog(monkeypatch, folder=folder, phase=1.5)

    window._new_phase()

    assert (folder / MANIFEST_FILENAME).exists()
    assert load_phase_dir(folder).phase == 1.5
    assert window._phase_manifest is not None and window._phase_manifest.phase == 1.5  # opened it
    assert "Created phase 1.5" in window.statusBar().currentMessage()


def test_new_phase_refuses_to_overwrite_an_existing_manifest(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = _window(qtbot)
    folder = tmp_path / "phase_existing"
    folder.mkdir()
    save_manifest(empty_manifest(9.0), folder)  # a phase already lives here
    _stub_dialog(monkeypatch, folder=folder, phase=1.0)

    window._new_phase()

    assert "already holds a phase manifest" in window.statusBar().currentMessage()
    assert load_phase_dir(folder).phase == 9.0  # untouched, not clobbered
    assert window._phase_manifest is None  # nothing was opened


def test_new_phase_cancelled_writes_nothing(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = _window(qtbot)
    folder = tmp_path / "phase_cancel"
    folder.mkdir()
    _stub_dialog(monkeypatch, folder=folder, phase=2.0, accepted=False)

    window._new_phase()

    assert not (folder / MANIFEST_FILENAME).exists()
    assert window._phase_manifest is None
