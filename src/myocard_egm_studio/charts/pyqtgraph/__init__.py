"""pyqtgraph chart backend — GUI-embedded chart recipes (the live-display twin of
``charts/matplotlib``).

Reuses ``analysis/`` and the framework-free ``charts.palette`` so a pyqtgraph chart
matches its matplotlib counterpart. Unlike the matplotlib recipes (which return a
Figure for headless file output), these return live pyqtgraph widgets.
"""

from myocard_egm_studio.charts.pyqtgraph.feature_distribution import (
    draw_feature_panel,
    feature_distribution_overlay,
)
from myocard_egm_studio.charts.pyqtgraph.feature_scatter import draw_feature_scatter
from myocard_egm_studio.charts.pyqtgraph.metrics import (
    CONFUSION_NORMS,
    draw_calibration,
    draw_confusion,
    draw_roc,
)
from myocard_egm_studio.charts.pyqtgraph.output_distribution import (
    draw_output_distribution,
    output_distribution_overlay,
)
from myocard_egm_studio.charts.pyqtgraph.style import DEFAULT_STYLE, PgChartStyle
from myocard_egm_studio.charts.pyqtgraph.training import training_curves_overlay

__all__ = [
    "CONFUSION_NORMS",
    "DEFAULT_STYLE",
    "PgChartStyle",
    "draw_calibration",
    "draw_confusion",
    "draw_feature_panel",
    "draw_feature_scatter",
    "draw_output_distribution",
    "draw_roc",
    "feature_distribution_overlay",
    "output_distribution_overlay",
    "training_curves_overlay",
]
