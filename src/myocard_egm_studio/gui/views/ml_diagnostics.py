"""Flow B — ML diagnostics over an evaluated bank (Block 8).

The main-area content for ML-diagnostics mode. There is no separate "load evaluated
bank" action: the single Open-bank path (:func:`gui.sources.load_exploration`) builds
one view-model, and when its traces carry predictions ``build_view_model`` joins the
ML-outcome columns (B8a). The shell reads the resulting mode with
:func:`gui.sources.frame_eval_mode` and calls :meth:`set_evaluated` (``"full"`` for a
labelled eval bank, ``"qualitative"`` for an unlabelled IAFDB one) or :meth:`clear`
when the load has no predictions. This B8d scaffold assembles the sub-tabs and lists
the evaluated traces; the
Output-distribution overlay (B8e), the ROC / confusion / calibration / training-curve
metric suite (B8f), and the ML-outcome filter + pair-compare (B8g) fill the rest.
"""

from __future__ import annotations

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE, PgChartStyle
from myocard_egm_studio.gui.widgets import OutputDistributionView, ResultList
from myocard_egm_studio.loaders import prediction_groups_by_source

_LANDING = "Open a bank with model predictions (File ▸ Open bank) to run ML diagnostics."
_PENDING = {
    "Metrics": "ROC / confusion / calibration metric suite lands in B8f.",
    "Training": "Training-curve overlay lands in B8f.",
}


def _placeholder(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("placeholderSubtitle")
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class MlDiagnosticsView(QtWidgets.QWidget):
    """The Flow B main area: evaluated-bank header + Output / Metrics / Training / Explore tabs."""

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
        self._result_list = ResultList()  # the evaluated traces + their ML-outcome columns
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("flowBTabs")
        self._tabs.addTab(self._output_view, "Output")
        self._tabs.addTab(_placeholder(_PENDING["Metrics"]), "Metrics")
        self._tabs.addTab(_placeholder(_PENDING["Training"]), "Training")
        self._tabs.addTab(self._result_list, "Explore")
        self._TAB_EXPLORE = self._tabs.count() - 1

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header)
        layout.addWidget(self._tabs, 1)

    def set_evaluated(self, frame: pd.DataFrame, mode: str) -> None:
        """Show a freshly loaded evaluated set: header + the Output overlay + trace list.

        Lands on the **Output** tab — the P(positive)-per-source overlay that is Flow B's
        headline (B8e); the Explore tab lists every trace with its ML-outcome columns.
        ``mode`` (``"full"`` / ``"qualitative"``) reports whether the metric suite applies.
        The header names the single source, or ``"N sources"`` for a multi-bank compare.
        B8f-g fill the Metrics / Training tabs and add filtering + pair-compare.
        """
        self._frame = frame
        self._output_view.set_groups(prediction_groups_by_source(frame))
        self._result_list.set_frame(frame)
        source = (
            str(frame["source"].iloc[0])
            if "source" in frame.columns and len(frame.index)
            else "bank"
        )
        n_sources = frame["source"].nunique() if "source" in frame.columns else 1
        header = source if n_sources < 2 else f"{n_sources} sources"
        self._header.setText(f"{header}  ·  {len(frame.index):,} traces  ·  {mode} diagnostics")
        self._tabs.setCurrentIndex(0)  # land on the Output overlay — the headline comparison

    def clear(self) -> None:
        """Reset to the landing state — the current load carries no predictions."""
        self._frame = pd.DataFrame()
        self._output_view.clear()
        self._result_list.set_frame(pd.DataFrame())
        self._header.setText(_LANDING)
        self._tabs.setCurrentIndex(0)

    def restyle(self, chart_style: PgChartStyle) -> None:
        """Re-apply the theme to the embedded charts (the shell calls this on a toggle)."""
        self._style = chart_style
        self._output_view.set_style(chart_style)

    @property
    def result_list(self) -> ResultList:
        return self._result_list
