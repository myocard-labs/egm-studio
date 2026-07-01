"""pyqtgraph chart backend — GUI-embedded chart recipes (the live-display twin of
``charts/matplotlib``).

Reuses ``analysis/`` and the framework-free ``charts.palette`` so a pyqtgraph chart
matches its matplotlib counterpart. Unlike the matplotlib recipes (which return a
Figure for headless file output), these return live pyqtgraph widgets.
"""

from myocard_egm_studio.charts.pyqtgraph.feature_distribution import feature_distribution_overlay
from myocard_egm_studio.charts.pyqtgraph.style import DEFAULT_STYLE, PgChartStyle

__all__ = ["DEFAULT_STYLE", "PgChartStyle", "feature_distribution_overlay"]
