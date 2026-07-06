"""Shared fixtures for the Qt GUI tests (tests/gui/)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6 import QtWidgets

from myocard_egm_studio.gui import shell as _shell


@pytest.fixture(autouse=True)
def isolated_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the shell's disk view-model cache at a per-test temp dir.

    ``MainWindow`` builds a ``DiskCache`` from ``default_cache_dir()`` (a platform cache
    location). Left alone, GUI tests would write pickles into the real user cache and could
    even be served a frame another test cached. Redirect it to ``tmp_path`` so every test is
    hermetic; returned so a test can inspect what was written.
    """
    cache_dir = tmp_path / "view-model-cache"
    monkeypatch.setattr(_shell, "default_cache_dir", lambda: str(cache_dir))
    return cache_dir


@pytest.fixture(autouse=True)
def _no_blocking_message_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop any static ``QMessageBox`` from opening a *blocking* modal in the headless suite.

    Offscreen has no one to click the button, so an un-stubbed
    ``QMessageBox.warning/information/critical/question`` runs its modal event loop forever —
    which froze CI for ~3 hours once. Each is replaced with a non-blocking default; a test that
    asserts on a box (e.g. captures the warning text, or answers a confirm "Yes") overrides this
    with its own ``monkeypatch.setattr`` in the test body, which wins.
    """
    button = QtWidgets.QMessageBox.StandardButton
    defaults = {
        "warning": button.Ok,
        "information": button.Ok,
        "critical": button.Ok,
        "question": button.No,  # decline destructive confirms unless a test opts in to Yes
    }
    for name, default in defaults.items():
        monkeypatch.setattr(QtWidgets.QMessageBox, name, lambda *a, _default=default, **k: _default)
