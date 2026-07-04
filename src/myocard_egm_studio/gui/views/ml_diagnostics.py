"""Flow B — ML diagnostics over an evaluated bank (Block 8).

The main-area content for ML-diagnostics mode. There is no separate "load evaluated
bank" action: the single Open-bank path (:func:`gui.sources.load_exploration`) builds
one view-model, and when its traces carry predictions ``build_view_model`` joins the
ML-outcome columns (B8a). The shell reads the resulting mode with
:func:`gui.sources.frame_eval_mode` and calls :meth:`set_evaluated` (``"full"`` for a
labelled eval bank, ``"qualitative"`` for an unlabelled IAFDB one) or :meth:`clear`
when the load has no predictions.

Four tabs: **Output** (P(positive) overlay, B8e), **Metrics** (ROC / calibration /
confusion — labelled sets only, B8f), **Training** (loss + metric curves, fed by a
separate ``File ▸ Open training run`` path via :meth:`set_runs`, B8f), and **Explore**
(the evaluated traces + ML-outcome columns). The ML-outcome filter + pair-compare is
B8g.
"""

from __future__ import annotations

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE, PgChartStyle
from myocard_egm_studio.gui.preferences import load_confusion_norm, save_confusion_norm
from myocard_egm_studio.gui.widgets import (
    MetricsView,
    OutputDistributionView,
    ResultList,
    TrainingView,
)
from myocard_egm_studio.loaders import confusion_by_source, prediction_groups_by_source

_LANDING = "Open a bank with model predictions (File ▸ Open bank) to run ML diagnostics."
_METRICS_EMPTY = "Open a labelled evaluated bank to see ROC / calibration / confusion."
_METRICS_UNLABELLED = "Metrics need truth labels — this eval set is unlabelled (the IAFDB shape)."
_TAB_OUTPUT, _TAB_METRICS, _TAB_TRAINING, _TAB_EXPLORE = 0, 1, 2, 3


class MlDiagnosticsView(QtWidgets.QWidget):
    """The Flow B main area: evaluated-bank header + Output / Metrics / Training / Explore tabs."""

    runRemoveRequested = QtCore.Signal(str)  # a Training-tab run label the user asked to drop

    def __init__(
        self, chart_style: PgChartStyle = DEFAULT_STYLE, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mlDiagnosticsView")
        self._style = chart_style
        self._frame = pd.DataFrame()

        self._header = QtWidgets.QLabel(_LANDING)
        self._header.setObjectName("diagnosticsHeader")
        self._header.setWordWrap(True)

        self._output_view = OutputDistributionView(chart_style)  # P(positive) per source (B8e)
        self._metrics_view = MetricsView(chart_style)  # ROC / calibration / confusion (B8f)
        self._metrics_view.show_message(_METRICS_EMPTY)
        self._metrics_view.set_norm(load_confusion_norm("row"))  # persisted cell mode
        self._metrics_view.normChanged.connect(save_confusion_norm)
        self._training_view = TrainingView(chart_style)  # loss + metric curves (B8f)
        self._training_view.removeRequested.connect(self.runRemoveRequested)  # to the shell
        self._result_list = ResultList()  # the evaluated traces + their ML-outcome columns

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("flowBTabs")
        self._tabs.addTab(self._output_view, "Output")
        self._tabs.addTab(self._metrics_view, "Metrics")
        self._tabs.addTab(self._training_view, "Training")
        self._tabs.addTab(self._result_list, "Explore")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header)
        layout.addWidget(self._tabs, 1)

    def set_evaluated(self, frame: pd.DataFrame, mode: str) -> None:
        """Show a freshly loaded evaluated set: header + Output overlay + Metrics + trace list.

        Lands on the **Output** tab — the P(positive)-per-source overlay that is Flow B's
        headline (B8e). In ``"full"`` mode the Metrics tab draws ROC / calibration /
        per-source confusion; a ``"qualitative"`` (unlabelled) set shows a message there
        instead — those metrics need ground truth. The Training tab is independent (fed by
        :meth:`set_runs`). The header names the single source, or ``"N sources"`` for a
        multi-bank compare.
        """
        self._frame = frame
        groups = prediction_groups_by_source(frame)
        self._output_view.set_groups(groups)
        if mode == "full":
            self._metrics_view.set_metrics(groups, confusion_by_source(frame))
        else:
            self._metrics_view.show_message(_METRICS_UNLABELLED)
        self._result_list.set_frame(frame)
        source = (
            str(frame["source"].iloc[0])
            if "source" in frame.columns and len(frame.index)
            else "bank"
        )
        n_sources = frame["source"].nunique() if "source" in frame.columns else 1
        header = source if n_sources < 2 else f"{n_sources} sources"
        self._header.setText(f"{header}  ·  {len(frame.index):,} traces  ·  {mode} diagnostics")
        self._tabs.setCurrentIndex(_TAB_OUTPUT)  # land on the headline comparison

    def set_runs(self, runs: list[tuple[str, TrainingCurve]]) -> None:
        """Feed the Training tab (a separate ``run.json`` load path) and land on it."""
        self._training_view.set_runs(runs)
        if runs:
            self._tabs.setCurrentIndex(_TAB_TRAINING)

    def clear(self) -> None:
        """Reset the bank-derived tabs to landing — the current load carries no predictions.

        Leaves the Training tab alone: training runs load independently of banks, so a
        raw-bank load shouldn't drop a run the user is inspecting.
        """
        self._frame = pd.DataFrame()
        self._output_view.clear()
        self._metrics_view.show_message(_METRICS_EMPTY)
        self._result_list.set_frame(pd.DataFrame())
        self._header.setText(_LANDING)
        self._tabs.setCurrentIndex(_TAB_OUTPUT)

    def restyle(self, chart_style: PgChartStyle) -> None:
        """Re-apply the theme to every embedded chart (the shell calls this on a toggle)."""
        self._style = chart_style
        self._output_view.set_style(chart_style)
        self._metrics_view.set_style(chart_style)
        self._training_view.set_style(chart_style)

    @property
    def result_list(self) -> ResultList:
        return self._result_list
