"""Mode views — the main-area content for each of the three egm-studio flows.

Each view assembles the reusable widgets (``gui/widgets``) into one flow. Flow A
(signal exploration) ships in Block 7; Flow B (ML diagnostics) and Flow C (paper
figures) land in Blocks 8-9.
"""

from myocard_egm_studio.gui.views.signal_exploration import SignalExplorationView

__all__ = ["SignalExplorationView"]
