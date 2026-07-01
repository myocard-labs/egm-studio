"""Interactive Qt desktop shell for myocard-egm-studio (Block 4+).

A thin PySide6 frontend over the same headless core the ``egm-studio-render`` CLI
drives (``analysis`` computes -> ``charts`` renders -> ``figures`` dispatches). This
package owns the window: the layout shell (ADR-025), theming (ADR-012), and the
interactive views added in later blocks. Nothing in the headless figure path
imports it, so ``egm-studio-render`` never pulls in Qt.

Console-script entry point: :func:`myocard_egm_studio.gui.app.main` (``egm-studio``).
"""

from myocard_egm_studio.gui.app import main
from myocard_egm_studio.gui.shell import MainWindow

__all__ = ["MainWindow", "main"]
