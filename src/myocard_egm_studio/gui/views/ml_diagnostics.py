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
(result list over the shared per-trace detail, whose finds are the misclassification /
outlier diagnostics, B8g). The Explore filter is the shell's shared Banks-&-filter
panel: on Recalculate the shell narrows the list (:meth:`set_explore_results`) while
the metric tabs stay on the full eval set.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE, PgChartStyle
from myocard_egm_studio.gui.preferences import load_confusion_norm, save_confusion_norm
from myocard_egm_studio.gui.widgets import (
    ExploreDetail,
    Finder,
    MetricsView,
    OutputDistributionView,
    ResultList,
    TraceData,
    TrainingView,
)
from myocard_egm_studio.loaders import confusion_by_source, prediction_groups_by_source
from myocard_egm_studio.view_model import (
    ROW_ID,
    apply_filter,
    nearest_correct_pair,
    within_class_neighborhood,
)
from myocard_egm_studio.view_model.filtering import FilterSpec
from myocard_egm_studio.view_model.ml_outcomes import ML_COLUMNS

_LANDING = "Open a bank with model predictions (File ▸ Open bank) to run ML diagnostics."
_METRICS_EMPTY = "Open a labelled evaluated bank to see ROC / calibration / confusion."
_METRICS_UNLABELLED = "Metrics need truth labels — this eval set is unlabelled (the IAFDB shape)."
_TAB_OUTPUT, _TAB_METRICS, _TAB_TRAINING, _TAB_EXPLORE = 0, 1, 2, 3
_MISCLASSIFIED = ("FP", "FN")

#: Filter columns a find must ignore: the ML outcomes + truth labels. A find looks for a
#: correctly-classified / opposite-label / same-label counterpart, so a filter on any of
#: these (e.g. correctness_bucket == FP) would hide the very candidates it searches for.
_FINDER_EXCLUDE = frozenset(ML_COLUMNS) | {"label", "label_name"}


def _without_outcome(spec: FilterSpec) -> FilterSpec:
    """``spec`` with its ML-outcome / truth-label conditions dropped (see _FINDER_EXCLUDE)."""
    kept = tuple(
        condition for condition in spec.conditions if condition.column not in _FINDER_EXCLUDE
    )
    return FilterSpec(conditions=kept, combine=spec.combine)


def _nearest_correct(frame: pd.DataFrame, row_id: int, feature: str) -> list[int]:
    """The misclassification's nearest correctly-classified opposite-label trace (0 or 1)."""
    match = nearest_correct_pair(frame, row_id, feature)
    return [match] if match is not None else []


def _is_misclassified(frame: pd.DataFrame, row_id: int) -> bool:
    """Whether ``row_id`` is a misclassification (FP / FN) — gates the nearest-correct find."""
    if not {"correctness_bucket", ROW_ID}.issubset(frame.columns):
        return False
    by_id = frame.set_index(ROW_ID)
    return row_id in by_id.index and by_id.loc[row_id, "correctness_bucket"] in _MISCLASSIFIED


#: Flow B's find strategies: a misclassification's nearest-correct counterpart (only shown
#: for an FP / FN source) + any trace's k nearest same-label peers (the outlier view).
_NEAREST_CORRECT = Finder("Find nearest correct", _nearest_correct, can_run=_is_misclassified)
_IN_CLASS_PEERS = Finder(
    "Find in-class peers",
    lambda frame, row_id, feature: within_class_neighborhood(frame, row_id, feature, k=2),
)


class MlDiagnosticsView(QtWidgets.QWidget):
    """The Flow B main area: evaluated-bank header + Output / Metrics / Training / Explore tabs."""

    runRemoveRequested = QtCore.Signal(str)  # a Training-tab run label the user asked to drop

    def __init__(
        self,
        palette: Any = None,
        chart_style: PgChartStyle = DEFAULT_STYLE,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mlDiagnosticsView")
        self._palette = palette
        self._style = chart_style
        self._frame = pd.DataFrame()
        self._traces: list[TraceData] = []

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

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("flowBTabs")
        self._tabs.addTab(self._output_view, "Output")
        self._tabs.addTab(self._metrics_view, "Metrics")
        self._tabs.addTab(self._training_view, "Training")
        self._tabs.addTab(self._build_explore_tab(), "Explore")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header)
        layout.addWidget(self._tabs, 1)

    def _build_explore_tab(self) -> QtWidgets.QWidget:
        """The result list over the shared per-trace detail (the shell owns the filter, B8g)."""
        self._result_list = ResultList()
        self._detail = ExploreDetail(self._palette, [_NEAREST_CORRECT, _IN_CLASS_PEERS])
        self._result_list.selectionChanged.connect(self._detail.on_selection)
        self._result_list.findSimilarRequested.connect(
            lambda row_id: self._detail.run_finder(0, row_id)  # right-click -> nearest correct
        )
        page = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        page.setObjectName("flowBExploreSplitter")
        page.addWidget(self._result_list)
        page.addWidget(self._detail)
        page.setStretchFactor(0, 3)
        page.setStretchFactor(1, 2)
        return page

    def set_evaluated(
        self, frame: pd.DataFrame, mode: str, *, traces: Sequence[TraceData] = ()
    ) -> None:
        """Show a freshly loaded evaluated set across the four tabs.

        Lands on the **Output** tab — the P(positive)-per-source overlay that is Flow B's
        headline (B8e). In ``"full"`` mode the Metrics tab draws ROC / calibration /
        per-source confusion; a ``"qualitative"`` (unlabelled) set shows a message instead.
        The Explore list + detail show the whole set (the shell's filter narrows them later
        via :meth:`set_explore_results`); ``traces`` are the display waveforms the detail
        resolves into. The Training tab is independent (fed by :meth:`set_runs`).
        """
        self._frame = frame
        self._traces = list(traces)
        groups = prediction_groups_by_source(frame)
        self._output_view.set_groups(groups)
        if mode == "full":
            self._metrics_view.set_metrics(groups, confusion_by_source(frame))
        else:
            self._metrics_view.show_message(_METRICS_UNLABELLED)
        self._apply_explore(frame, frame)  # full set on both the list and the find search
        source = (
            str(frame["source"].iloc[0])
            if "source" in frame.columns and len(frame.index)
            else "bank"
        )
        n_sources = frame["source"].nunique() if "source" in frame.columns else 1
        header = source if n_sources < 2 else f"{n_sources} sources"
        self._header.setText(f"{header}  ·  {len(frame.index):,} traces  ·  {mode} diagnostics")
        self._tabs.setCurrentIndex(_TAB_OUTPUT)  # land on the headline comparison

    def set_explore_results(self, display: pd.DataFrame, spec: FilterSpec) -> None:
        """Narrow the Explore list to ``display``; the metric tabs keep the full eval set.

        The find search frame keeps every filter *except* the ML-outcome / truth-label ones
        (:func:`_without_outcome`), so filtering the list to FP / FN still leaves the
        correct, opposite-label counterparts findable (B8g review).
        """
        search = (
            self._frame[apply_filter(self._frame, _without_outcome(spec))]
            if len(self._frame.index)
            else self._frame
        )
        self._apply_explore(display, search)

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
        self._traces = []
        self._output_view.clear()
        self._metrics_view.show_message(_METRICS_EMPTY)
        self._apply_explore(pd.DataFrame(), pd.DataFrame())
        self._header.setText(_LANDING)
        self._tabs.setCurrentIndex(_TAB_OUTPUT)

    def restyle(self, palette: Any, chart_style: PgChartStyle) -> None:
        """Re-apply the theme to every embedded chart + the detail (shell calls this)."""
        self._palette = palette
        self._style = chart_style
        self._output_view.set_style(chart_style)
        self._metrics_view.set_style(chart_style)
        self._training_view.set_style(chart_style)
        self._detail.restyle(palette)

    @property
    def result_list(self) -> ResultList:
        return self._result_list

    def _apply_explore(self, display: pd.DataFrame, search: pd.DataFrame) -> None:
        """Feed the (superset) search frame to the detail first, then the list ``display``.

        Ordering matters: ``set_frame`` clears the selection (emitting an empty selection ->
        the detail's prompt), so the detail must already hold the frame its finds search.
        """
        self._detail.set_context(search, self._traces)
        self._result_list.set_frame(display)
