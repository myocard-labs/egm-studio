"""pytest-qt tests for the shared per-trace detail pane (gui/widgets/explore_detail, B8g)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.widgets import ExploreDetail, Finder, TraceData, TraceView


def _traces(n: int) -> list[TraceData]:
    return [TraceData(signal=np.zeros(8), fs_hz=1000.0, label=f"t{i}") for i in range(n)]


def _frame(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_id": range(n),
            "trace_idx": range(n),
            "peak_to_peak": np.arange(n, dtype=float),
            "source": "A",
            "label_name": "healthy",
        }
    )


def _detail(qtbot: QtBot, finders: list[Finder], n: int = 3) -> ExploreDetail:
    detail = ExploreDetail(plot_palette("dark"), finders)
    qtbot.addWidget(detail)
    detail.set_context(_frame(n), _traces(n))
    return detail


def test_single_selection_shows_the_detail(qtbot: QtBot) -> None:
    detail = _detail(qtbot, [])
    detail.on_selection([0])
    assert detail._stack.currentIndex() == 1
    assert isinstance(detail._waveforms.content, TraceView)


def test_empty_selection_returns_to_the_prompt(qtbot: QtBot) -> None:
    detail = _detail(qtbot, [])
    detail.on_selection([0])
    detail.on_selection([])
    assert detail._stack.currentIndex() == 0


def test_show_rows_caps_at_three(qtbot: QtBot) -> None:
    detail = _detail(qtbot, [], n=6)
    detail.show_rows(list(range(6)))
    assert detail._detail_table.columnCount() == 1 + 3  # attribute + 3 capped trace columns


def test_finder_button_hidden_when_can_run_vetoes(qtbot: QtBot) -> None:
    gated = Finder("gated", lambda _f, _r, _ft: [], can_run=lambda _f, _r: False)
    detail = _detail(qtbot, [gated])
    detail.on_selection([0])  # a single source is selected...
    assert detail._buttons[0].isHidden()  # ...but can_run hides the button (not just greys)
    assert not detail._buttons[0].isEnabled()


def test_finder_shows_source_beside_its_matches(qtbot: QtBot) -> None:
    finder = Finder("find one", lambda _f, row_id, _ft: [1] if row_id == 0 else [])
    detail = _detail(qtbot, [finder])
    detail.on_selection([0])
    assert detail._buttons[0].isEnabled()
    detail._buttons[0].click()
    assert detail._detail_table.columnCount() == 1 + 2  # attribute + source + its match
