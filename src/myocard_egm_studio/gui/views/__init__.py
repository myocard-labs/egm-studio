"""Mode views — the main-area content for each of the three egm-studio flows.

Each view assembles the reusable widgets (``gui/widgets``) into one flow: Flow A
(signal exploration, Block 7), Flow B (ML diagnostics, Block 8), and Flow C (paper
figure prep, Block 9).
"""

from myocard_egm_studio.gui.views.ml_diagnostics import MlDiagnosticsView
from myocard_egm_studio.gui.views.paper_figure_prep import PaperFigurePrepView
from myocard_egm_studio.gui.views.signal_exploration import SignalExplorationView

__all__ = ["MlDiagnosticsView", "PaperFigurePrepView", "SignalExplorationView"]
