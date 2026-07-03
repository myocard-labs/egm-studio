"""Reusable Qt display widgets for the egm-studio shell (Block 5+).

The composable trace-display primitive (ADR-024): :class:`~.trace.TraceWidget`
renders one trace, :class:`~.trace.TraceContainer` stacks N of them with a shared
X-axis.
"""

from myocard_egm_studio.gui.widgets.filter import FilterPanel
from myocard_egm_studio.gui.widgets.phase_tree import PhaseTree
from myocard_egm_studio.gui.widgets.result_list import ResultList
from myocard_egm_studio.gui.widgets.time_scale import TimeScaleWidget
from myocard_egm_studio.gui.widgets.trace import TraceContainer, TraceData, TraceWidget
from myocard_egm_studio.gui.widgets.trace_selector import BankTrace, LoadedBank, TraceSelector
from myocard_egm_studio.gui.widgets.trace_view import TraceView

__all__ = [
    "BankTrace",
    "FilterPanel",
    "LoadedBank",
    "PhaseTree",
    "ResultList",
    "TimeScaleWidget",
    "TraceContainer",
    "TraceData",
    "TraceSelector",
    "TraceView",
    "TraceWidget",
]
