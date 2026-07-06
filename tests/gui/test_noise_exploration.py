"""Tests for the Noise view — sidebar controls (emit) + plot (render), the fourth mode."""

from __future__ import annotations

import numpy as np
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.views.noise_exploration import NoiseControls, NoiseExplorationView
from myocard_egm_studio.gui.widgets.trace import TraceData
from myocard_egm_studio.gui.widgets.trace_view import TraceView
from myocard_egm_studio.view_model.noise import NoiseBankSegments, NoiseSegment


def _bank(records: list[str], channels: list[str]) -> NoiseBankSegments:
    """A NoiseBankSegments with one segment per (record, channel) pair, in order."""
    segments = tuple(
        NoiseSegment(
            index=i,
            source_record=rec,
            source_channel=ch,
            signal=np.full(16, float(i), dtype=np.float64),
        )
        for i, (rec, ch) in enumerate(zip(records, channels, strict=True))
    )
    return NoiseBankSegments(segments=segments, fs_hz=1000.0, source="iafdb")


def _controls(qtbot: QtBot, bank: NoiseBankSegments) -> tuple[NoiseControls, list[object]]:
    """A NoiseControls with the bank loaded + a list capturing every segmentChosen payload."""
    widget = NoiseControls()
    qtbot.addWidget(widget)
    chosen: list[object] = []
    widget.segmentChosen.connect(chosen.append)
    widget.set_bank(bank, bank_id="nbank_fixture_2026-06-15")
    return widget, chosen


def _visible_rows(controls: NoiseControls) -> list[int]:
    table = controls._table
    return [r for r in range(table.rowCount()) if not table.isRowHidden(r)]


def test_set_bank_populates_table_filters_and_emits_first(qtbot: QtBot) -> None:
    controls, chosen = _controls(qtbot, _bank(["a", "a", "b"], ["0", "1", "0"]))
    assert controls._table.rowCount() == 3  # one row per segment, in bank order
    assert controls._record_filter.count() == 3  # All, a, b
    assert controls._channel_filter.count() == 3  # All, 0, 1
    assert controls._record_filter.itemData(1) == "a"  # userData is the raw value, not the label
    assert "3 of 3" in controls._count.text()
    assert isinstance(chosen[-1], TraceData)  # first segment auto-emitted
    assert chosen[-1].label == "seg 0 · a · ch 0"


def test_filter_by_record_hides_nonmatching_rows(qtbot: QtBot) -> None:
    controls, _ = _controls(qtbot, _bank(["a", "a", "b"], ["0", "1", "0"]))
    controls._record_filter.setCurrentIndex(controls._record_filter.findData("b"))
    assert _visible_rows(controls) == [2]  # only the record-"b" segment remains
    assert "1 of 3" in controls._count.text()


def test_filtering_out_the_selection_reemits_first_visible(qtbot: QtBot) -> None:
    controls, chosen = _controls(qtbot, _bank(["a", "a", "b"], ["0", "1", "0"]))
    # segment 0 (record "a") is selected on load; filter to record "b" drops it
    controls._record_filter.setCurrentIndex(controls._record_filter.findData("b"))
    assert isinstance(chosen[-1], TraceData)
    assert chosen[-1].label == "seg 2 · b · ch 0"  # falls to the first visible segment


def test_selecting_a_row_emits_that_segment(qtbot: QtBot) -> None:
    controls, chosen = _controls(qtbot, _bank(["a", "a", "b"], ["0", "1", "0"]))
    controls._table.selectRow(1)
    assert isinstance(chosen[-1], TraceData)
    assert chosen[-1].label == "seg 1 · a · ch 1"


def test_empty_bank_emits_none_and_zero_count(qtbot: QtBot) -> None:
    controls, chosen = _controls(qtbot, _bank([], []))
    assert controls._table.rowCount() == 0
    assert "0 of 0" in controls._count.text()
    assert chosen[-1] is None  # no segment -> the plot clears to its prompt


def test_view_renders_a_tracedata_and_clears_on_none(qtbot: QtBot) -> None:
    view = NoiseExplorationView()
    qtbot.addWidget(view)
    view.on_segment(TraceData(signal=np.zeros(16, dtype=np.float64), fs_hz=1000.0, label="seg 0"))
    assert view._holder.findChild(TraceView) is not None  # the trace is plotted
    view.on_segment(None)
    assert view._holder.findChild(TraceView) is None  # cleared back to the prompt


def test_view_caps_the_plot_aspect_ratio(qtbot: QtBot) -> None:
    view = NoiseExplorationView()
    qtbot.addWidget(view)
    view.resize(1000, 900)  # a tall pane...
    view.on_segment(TraceData(signal=np.zeros(16, dtype=np.float64), fs_hz=1000.0, label="s"))
    # ...must not let the plot band fill the height: it's capped to a fraction of the width
    assert view._holder.maximumHeight() < 900
