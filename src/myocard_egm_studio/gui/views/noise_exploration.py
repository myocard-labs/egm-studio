"""Noise view — sidebar controls + a full-height plot for a noise bank (Block 10g).

The **Noise** mode (the second top-level view). A noise bank is a different artifact from
a loaded classifier bank — N raw noise segments, each tagged with the IAFDB record + channel
it was cut from — so it gets its own view rather than a Flow A sub-tab.

The view is split so the shell can host each half where it belongs (like Flow A's sidebar
filter vs. main-area list): :class:`NoiseControls` (overview + record / channel filters +
segment table) lives in the left sidebar in place of "Banks & filters"; the plot,
:class:`NoiseExplorationView`, fills the main area. The controls emit the chosen segment as
a :class:`~gui.widgets.trace.TraceData`; the plot renders it. Selection is single-row (one
segment at a time); the table stays in bank order (no sort), so a row's position *is* its
segment index. The 66k-segment banks build the table once under a progress callback and
filter by hiding rows, not repopulating — so changing a filter is cheap.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.gui.theme import DEFAULT_THEME, PlotPalette, plot_palette
from myocard_egm_studio.gui.widgets.trace import TraceData
from myocard_egm_studio.gui.widgets.trace_view import TraceView
from myocard_egm_studio.view_model.noise import NoiseBankSegments, NoiseSegment

_ALL = "All"  # the filter combos' "no filter" sentinel (its userData is None)
_COL_INDEX, _COL_RECORD, _COL_CHANNEL = 0, 1, 2
_TABLE_CHUNK = 500  # rows built between progress ticks on a big-bank load

#: Cap the plot's height to this fraction of its width (+ absolute bounds), so a single
#: trace in a tall pane isn't stretched vertically. The plot centres inside the leftover space.
_MAX_ASPECT = 0.42
_MIN_PLOT_H, _MAX_PLOT_H = 200, 460


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


class _OverviewPanel(QtWidgets.QFrame):
    """The bank-provenance header: the id over one stats line."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("noiseOverview")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 6)
        outer.setSpacing(2)
        self._id = QtWidgets.QLabel("No noise bank loaded")
        self._id.setObjectName("noiseBankId")
        self._id.setWordWrap(True)
        self._stats = QtWidgets.QLabel()
        self._stats.setObjectName("noiseStats")
        self._stats.setWordWrap(True)
        outer.addWidget(self._id)
        outer.addWidget(self._stats)

    def set_bank(self, bank_id: str, bank: NoiseBankSegments) -> None:
        self._id.setText(bank_id)
        parts = [
            f"{len(bank.segments):,} segments",
            f"source {bank.source}",
            f"{bank.fs_hz:g} Hz",
            f"{len(bank.records())} records · {len(bank.channels())} channels",
        ]
        self._stats.setText("   ·   ".join(parts))


class NoiseControls(QtWidgets.QWidget):
    """Sidebar controls for the Noise view: overview + record / channel filters + table.

    Emits :attr:`segmentChosen` (a :class:`TraceData`, or ``None`` to clear) whenever the
    selected segment changes — the shell wires that to the :class:`NoiseExplorationView` plot.
    """

    segmentChosen = QtCore.Signal(object)  # TraceData for the selected segment, or None

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("noiseControls")
        self._segments: tuple[NoiseSegment, ...] = ()
        self._fs_hz = 1.0

        self._overview = _OverviewPanel()
        self._record_filter = QtWidgets.QComboBox()
        self._record_filter.setObjectName("noiseRecordFilter")
        self._channel_filter = QtWidgets.QComboBox()
        self._channel_filter.setObjectName("noiseChannelFilter")
        for combo in (self._record_filter, self._channel_filter):
            combo.currentIndexChanged.connect(self._apply_filter)
        filters = QtWidgets.QFormLayout()
        filters.setContentsMargins(0, 0, 0, 0)
        filters.addRow("Record", self._record_filter)
        filters.addRow("Channel", self._channel_filter)

        self._count = QtWidgets.QLabel("No noise bank loaded")
        self._count.setObjectName("noiseCount")

        self._table = QtWidgets.QTableWidget(0, 3)
        self._table.setObjectName("noiseTable")
        self._table.setHorizontalHeaderLabels(["#", "record", "channel"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._emit_selected)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._overview)
        layout.addLayout(filters)
        layout.addWidget(self._count)
        layout.addWidget(self._table, 1)

    def set_bank(
        self,
        bank: NoiseBankSegments,
        *,
        bank_id: str | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Show a loaded noise bank: overview + filters + the full segment table.

        The bank names itself (``noise_bank`` 1.1, B20), so ``bank_id`` is only a **fallback**
        for one written before that attr existed — pass the manifest entry's id there. The
        bank's own id wins when it has one: it is the artifact's identity, where the manifest's
        is what a curator recorded about it.

        ``progress`` (the big-bank load) is called ``(rows_done, rows_total)`` while the
        table populates so the caller can drive a progress bar; None for small banks.
        """
        self._segments = bank.segments
        self._fs_hz = bank.fs_hz
        self._overview.set_bank(bank.bank_id or bank_id or "(no bank id)", bank)
        self._fill_filters(bank)
        self._fill_table(progress)
        self._apply_filter()  # sets the count + shows every row, then selects the first segment

    def _fill_filters(self, bank: NoiseBankSegments) -> None:
        """Populate the record / channel combos with counts, without re-triggering filter."""
        record_counts = Counter(seg.source_record for seg in bank.segments)
        channel_counts = Counter(seg.source_channel for seg in bank.segments)
        for combo, values, counts in (
            (self._record_filter, bank.records(), record_counts),
            (self._channel_filter, bank.channels(), channel_counts),
        ):
            combo.blockSignals(True)  # rebuilding must not fire a premature _apply_filter
            combo.clear()
            combo.addItem(f"{_ALL} ({len(bank.segments):,})", userData=None)
            for value in values:
                combo.addItem(f"{value} ({counts[value]:,})", userData=value)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def _fill_table(self, progress: Callable[[int, int], None] | None) -> None:
        """Build one row per segment, in bank order (row index == segment index)."""
        self._table.clearContents()
        rows = len(self._segments)
        self._table.setRowCount(rows)
        for row, seg in enumerate(self._segments):
            self._table.setItem(row, _COL_INDEX, QtWidgets.QTableWidgetItem(str(seg.index)))
            self._table.setItem(row, _COL_RECORD, QtWidgets.QTableWidgetItem(seg.source_record))
            self._table.setItem(row, _COL_CHANNEL, QtWidgets.QTableWidgetItem(seg.source_channel))
            if progress is not None and row % _TABLE_CHUNK == 0:
                progress(row, rows)
        if progress is not None:
            progress(rows, rows)
        self._table.resizeColumnToContents(_COL_INDEX)

    def _apply_filter(self) -> None:
        """Hide rows whose record / channel don't match the combos (cheap — no rebuild)."""
        record = self._record_filter.currentData()
        channel = self._channel_filter.currentData()
        shown = 0
        for row, seg in enumerate(self._segments):
            hide = (record is not None and seg.source_record != record) or (
                channel is not None and seg.source_channel != channel
            )
            self._table.setRowHidden(row, hide)
            shown += not hide
        self._count.setText(f"{shown:,} of {len(self._segments):,} segment(s)")
        if self._selected_row() is None:  # the selection got filtered out
            self._select_first_visible()

    def _selected_row(self) -> int | None:
        """The selected row if it's currently visible, else None."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        return None if self._table.isRowHidden(row) else row

    def _select_first_visible(self) -> None:
        for row in range(self._table.rowCount()):
            if not self._table.isRowHidden(row):
                self._table.selectRow(row)
                return
        self.segmentChosen.emit(None)  # nothing matches the filter -> clear the plot

    def _emit_selected(self) -> None:
        """Emit the selected segment (single-selection) as a TraceData for the plot."""
        row = self._selected_row()
        if row is None:
            return
        seg = self._segments[row]
        label = f"seg {seg.index} · {seg.source_record} · ch {seg.source_channel}"
        self.segmentChosen.emit(TraceData(signal=seg.signal, fs_hz=self._fs_hz, label=label))


class NoiseExplorationView(QtWidgets.QWidget):
    """The Noise view's main area: a single selected segment plotted, aspect-capped.

    Renders the :class:`TraceData` the :class:`NoiseControls` emit. The plot's height is
    capped to a fraction of its width (:data:`_MAX_ASPECT`) and centred, so one trace in a
    tall pane reads as a signal band rather than a vertically-stretched line.
    """

    def __init__(
        self, palette: PlotPalette | None = None, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("noiseExplorationView")
        self._palette = palette or plot_palette(DEFAULT_THEME)

        self._holder = QtWidgets.QWidget()
        self._holder_layout = QtWidgets.QVBoxLayout(self._holder)
        self._holder_layout.setContentsMargins(0, 0, 0, 0)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addStretch(1)  # centre the aspect-capped plot band vertically
        outer.addWidget(self._holder)
        outer.addStretch(1)
        self._show_prompt()

    def on_segment(self, data: object) -> None:
        """Slot for :attr:`NoiseControls.segmentChosen`: show the trace, or the prompt if None."""
        if isinstance(data, TraceData):
            self._set_widget(TraceView([data], palette=self._palette))
        else:
            self._show_prompt()

    def _show_prompt(self) -> None:
        prompt = QtWidgets.QLabel("Select a segment to plot it")
        prompt.setObjectName("noisePrompt")
        prompt.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._set_widget(prompt)

    def _set_widget(self, widget: QtWidgets.QWidget) -> None:
        _clear_layout(self._holder_layout)
        self._holder_layout.addWidget(widget)
        self._apply_aspect_cap()

    def _apply_aspect_cap(self) -> None:
        """Bound the plot band's height to _MAX_ASPECT of its width (within absolute limits)."""
        cap = min(_MAX_PLOT_H, max(_MIN_PLOT_H, int(self.width() * _MAX_ASPECT)))
        self._holder.setMaximumHeight(cap)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_aspect_cap()

    def restyle(self, palette: PlotPalette) -> None:
        """Re-apply the theme to the open plot (if a segment is shown)."""
        self._palette = palette
        for i in range(self._holder_layout.count()):
            item = self._holder_layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if isinstance(widget, TraceView):
                widget.restyle(palette)
