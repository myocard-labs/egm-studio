"""QApplication entry point for the egm-studio desktop GUI.

``main()`` is the ``egm-studio`` console script (pyproject ``[project.scripts]``).
It owns the QApplication lifecycle, restores the user's saved theme (falling back
to the ADR-012 default), and shows the window (:class:`.shell.MainWindow`).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import cast

from PySide6 import QtWidgets

from myocard_egm_studio.gui.preferences import APP_NAME, ORG_NAME, load_theme
from myocard_egm_studio.gui.shell import MainWindow
from myocard_egm_studio.gui.theme import DEFAULT_THEME, apply_theme


def build_app(argv: Sequence[str] | None = None) -> QtWidgets.QApplication:
    """Return the process QApplication, creating it with app/org identity if needed.

    Reuses an existing ``QApplication.instance()`` when one is present, so this is
    safe to call under the shared pytest-qt ``qapp`` without spawning a second
    application. ``argv`` defaults to ``sys.argv``.
    """
    existing = QtWidgets.QApplication.instance()
    if existing is not None:
        return cast("QtWidgets.QApplication", existing)
    app = QtWidgets.QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    return app


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the desktop GUI; returns the Qt event-loop exit code."""
    app = build_app(argv)
    apply_theme(app, load_theme(DEFAULT_THEME))
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
