"""Mode views — the main-area content for each of the egm-studio top-level modes.

Each view assembles the reusable widgets (``gui/widgets``) into one flow: Flow A
(signal exploration, Block 7), Flow B (ML diagnostics, Block 8), Flow C (paper
figure prep, Block 9), and the Noise view (noise-bank segments, Block 10g).
"""

from myocard_egm_studio.gui.views.ml_diagnostics import MlDiagnosticsView
from myocard_egm_studio.gui.views.noise_exploration import NoiseControls, NoiseExplorationView
from myocard_egm_studio.gui.views.paper_figure_prep import PaperFigurePrepView
from myocard_egm_studio.gui.views.signal_exploration import SignalExplorationView

__all__ = [
    "MlDiagnosticsView",
    "NoiseControls",
    "NoiseExplorationView",
    "PaperFigurePrepView",
    "SignalExplorationView",
]
