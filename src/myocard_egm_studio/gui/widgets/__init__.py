"""Reusable Qt display widgets for the egm-studio shell (Block 5+).

The composable trace-display primitive (ADR-024): :class:`~.trace.TraceWidget`
renders one trace, :class:`~.trace.TraceContainer` stacks N of them with a shared
X-axis.
"""

from myocard_egm_studio.gui.widgets.bank_list import LoadedBanksList
from myocard_egm_studio.gui.widgets.explore_detail import ExploreDetail, Finder
from myocard_egm_studio.gui.widgets.feature_grid import FeatureDistributionGrid
from myocard_egm_studio.gui.widgets.feature_scatter import FeatureScatterView
from myocard_egm_studio.gui.widgets.figure_form import FigureForm
from myocard_egm_studio.gui.widgets.figure_preview import FigurePreview
from myocard_egm_studio.gui.widgets.filter import FilterPanel
from myocard_egm_studio.gui.widgets.metrics_view import MetricsView
from myocard_egm_studio.gui.widgets.output_distribution import OutputDistributionView
from myocard_egm_studio.gui.widgets.phase_tree import PhaseTree
from myocard_egm_studio.gui.widgets.result_list import ResultList
from myocard_egm_studio.gui.widgets.run_list import LoadedRunsList
from myocard_egm_studio.gui.widgets.scratch_list import ScratchList
from myocard_egm_studio.gui.widgets.time_scale import TimeScaleWidget
from myocard_egm_studio.gui.widgets.trace import TraceContainer, TraceData, TraceWidget
from myocard_egm_studio.gui.widgets.trace_view import TraceView
from myocard_egm_studio.gui.widgets.training_view import TrainingView

__all__ = [
    "ExploreDetail",
    "FeatureDistributionGrid",
    "FeatureScatterView",
    "FigureForm",
    "FigurePreview",
    "FilterPanel",
    "Finder",
    "LoadedBanksList",
    "LoadedRunsList",
    "MetricsView",
    "OutputDistributionView",
    "PhaseTree",
    "ResultList",
    "ScratchList",
    "TimeScaleWidget",
    "TraceContainer",
    "TraceData",
    "TraceView",
    "TraceWidget",
    "TrainingView",
]
