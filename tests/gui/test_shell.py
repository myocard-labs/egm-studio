"""pytest-qt smoke tests for the Block 4 layout shell (ADR-025).

Per ADR-013 these check structure + wiring, not pixel positions: the window
builds, the three work-area columns exist, the menu bar is populated, sidebars
collapse/expand (menu checkmark in sync), and the mode control is exclusive. Run
headless under the offscreen QPA platform (CI uses xvfb).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from myocard_egm_data.records import TrainingRunRecord, write_training_run_record
from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.gui import shell as shell_mod
from myocard_egm_studio.gui.shell import CollapsibleSidebar, MainWindow
from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.widgets import TraceContainer, TraceView
from myocard_egm_studio.view_model.filtering import Condition, FilterSpec


def test_shell_builds_with_three_columns(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "egm-studio"
    splitter = window.findChild(QtWidgets.QSplitter, "columnSplitter")
    assert splitter is not None
    assert splitter.count() == 3  # left | main | right


def test_menu_bar_has_expected_top_level_menus(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    titles = [action.text() for action in window.menuBar().actions()]
    assert titles == ["&File", "&View", "&Help"]


def test_left_sidebar_collapses_and_expands_via_menu(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    left = window.findChild(CollapsibleSidebar, "leftSidebar")
    action = window.findChild(QtGui.QAction, "toggleLeftSidebar")
    assert left is not None
    assert action is not None
    assert not left.is_collapsed()
    assert action.isChecked()  # ticked == expanded

    action.trigger()
    assert left.is_collapsed()
    assert not action.isChecked()

    action.trigger()
    assert not left.is_collapsed()
    assert action.isChecked()


def test_sidebar_toggle_button_keeps_menu_in_sync(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    right = window.findChild(CollapsibleSidebar, "rightSidebar")
    action = window.findChild(QtGui.QAction, "toggleRightSidebar")
    assert right is not None
    assert action is not None

    right.toggleRequested.emit()  # as if the in-panel collapse button was clicked
    assert right.is_collapsed()
    assert not action.isChecked()


def test_mode_control_is_exclusive(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    buttons = window.findChildren(QtWidgets.QPushButton, "modeButton")
    assert len(buttons) == 3
    assert buttons[0].isChecked()  # signal-exploration default

    buttons[2].click()
    assert buttons[2].isChecked()
    assert not buttons[0].isChecked()


def _open(qtbot: QtBot, bank: ClassifierBank, tmp_path: Path) -> MainWindow:
    path = tmp_path / "bank.h5"
    write_classifier_bank(bank, path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._open_bank_explore(str(path))
    return window


def test_open_bank_populates_result_list(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    table = window._explore_view.result_list._table
    assert table.rowCount() == len(tiny_classifier_bank.traces)
    assert "Loaded" in window.statusBar().currentMessage()


def test_open_bank_lands_on_summary_with_grid(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """File ▸ Open bank lands on the Summary tab with the distribution grid built."""
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    assert window._explore_view._tabs.currentIndex() == 0  # Summary landing
    assert len(window._explore_view._feature_grid.panels) > 0


def test_explore_focus_lands_on_explore_tab(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """focus="explore" (the "Explore signal" action) opens straight to the list."""
    path = tmp_path / "bank.h5"
    write_classifier_bank(tiny_classifier_bank, path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._open_bank_explore(str(path), focus="explore")
    assert window._explore_view._tabs.currentIndex() == 1  # Explore tab


def test_add_bank_combines_then_remove(
    qtbot: QtBot,
    tiny_classifier_bank: ClassifierBank,
    tiny_unlabeled_bank: ClassifierBank,
    tmp_path: Path,
) -> None:
    """Add a second bank -> the list pools both banks' traces + the roster shows two;
    removing one drops it back to a single bank."""
    a, b = tmp_path / "a.h5", tmp_path / "b.h5"
    write_classifier_bank(tiny_classifier_bank, a)
    write_classifier_bank(tiny_unlabeled_bank, b)
    window = MainWindow()
    qtbot.addWidget(window)

    window._open_bank_explore(str(a))  # open (replace)
    window._open_bank_explore(str(b), focus=None, replace=False)  # add
    total = len(tiny_classifier_bank.traces) + len(tiny_unlabeled_bank.traces)
    assert len(window._loaded_banks) == 2
    assert window._explore_view.result_list._table.rowCount() == total

    window._remove_bank(str(a))
    assert [bank.path for bank in window._loaded_banks] == [str(b)]
    assert window._explore_view.result_list._table.rowCount() == len(tiny_unlabeled_bank.traces)


def test_open_action_relabels_to_add_when_loaded(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """The Open-bank menu action toggles Open ↔ Add on the loaded state (B7.8b-fix)."""
    path = tmp_path / "bank.h5"
    write_classifier_bank(tiny_classifier_bank, path)
    window = MainWindow()
    qtbot.addWidget(window)
    assert window._open_action.text() == "&Open bank…"  # nothing loaded
    window._open_bank_explore(str(path))
    assert window._open_action.text() == "&Add bank…"  # a bank is loaded
    window._remove_bank(str(path))
    assert window._open_action.text() == "&Open bank…"  # back to empty


def test_selecting_a_trace_shows_the_detail(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    window._explore_view.result_list._table.selectRow(0)
    assert window.findChild(TraceContainer) is not None


def test_recalculate_narrows_the_result_list(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    total = window._explore_view.result_list._table.rowCount()
    window._on_recalculate(FilterSpec((Condition("label_name", "==", "fibrotic"),)))
    kept = window._explore_view.result_list._table.rowCount()
    assert 0 < kept < total
    assert "match" in window.statusBar().currentMessage()
    # the summary grid + stats reflect the filtered set too (point 3), not the full bank
    assert f"{kept:,} traces" in window._explore_view._summary_panel._count.text()


def test_bring_to_front_raises_the_scatter_source(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """The roster bring-to-front button maps the bank path to its scatter source."""
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    bank = window._loaded_banks[0]
    window._on_bring_to_front(bank.path)
    assert window._explore_view._scatter._front_source == bank.label


def test_opening_an_evaluated_bank_populates_flow_b(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """One Open-bank load also feeds ML diagnostics when the bank carries predictions."""
    window = _open(qtbot, tiny_predictions_bank, tmp_path)  # the single Open-bank path
    diagnostics = window._diagnostics_view
    assert diagnostics.result_list._table.rowCount() == tiny_predictions_bank.n_traces
    assert "full diagnostics" in diagnostics._header.text()


def test_opening_a_raw_bank_leaves_flow_b_in_the_landing_state(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """A bank with no predictions opens in signal exploration; ML diagnostics stays empty."""
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    diagnostics = window._diagnostics_view
    assert diagnostics.result_list._table.rowCount() == 0
    assert "Open a bank with model predictions" in diagnostics._header.text()


def test_flow_c_view_is_mounted_at_mode_two(qtbot: QtBot) -> None:
    """The paper-figure-prep view occupies mode-stack index 2 (Flow C, B9c)."""
    from myocard_egm_studio.gui.views import PaperFigurePrepView

    window = MainWindow()
    qtbot.addWidget(window)
    assert window._modes_stack.widget(2) is window._figure_view
    assert isinstance(window._figure_view, PaperFigurePrepView)


def test_recalculate_drives_flow_b_explore_from_the_shared_filter(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """The one Banks-&-filter panel narrows the Flow B Explore list too (B8g-r1)."""
    window = _open(qtbot, tiny_predictions_bank, tmp_path)
    total = window._diagnostics_view.result_list._table.rowCount()
    window._on_recalculate(FilterSpec((Condition("correctness_bucket", "==", "TP"),)))
    assert window._diagnostics_view.result_list._table.rowCount() < total  # Flow B list narrowed


def _training_record() -> TrainingRunRecord:
    """A 3-epoch training run record (falling loss, rising AUROC)."""
    return TrainingRunRecord.model_validate(
        {
            "schema_version": "1.1",
            "created_utc": "2026-06-30T00:00:00Z",
            "run": {},
            "config": {},
            "epochs": [
                {
                    "epoch": e,
                    "lr": 0.001,
                    "train_loss": 1.0 / e,
                    "val_loss": 1.0 / e + 0.1,
                    "epoch_seconds": 1.0,
                    "val_metrics": {"auroc": 0.6 + 0.1 * e},
                    "val_reliability": [],
                }
                for e in (1, 2, 3)
            ],
            "best": {"epoch": 3, "metric": "auroc", "value": 0.9},
        }
    )


def test_open_training_run_populates_flow_b_training(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """File ▸ Open training run reads a run.json into the Flow B Training tab."""
    run_dir = tmp_path / "v1p5_run"
    run_dir.mkdir()
    path = run_dir / "run.json"
    write_training_run_record(path, _training_record())
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(path)], "")
    )
    window._open_training_run()
    assert window._modes_stack.currentIndex() == 1  # switched to ML diagnostics
    assert window._diagnostics_view._tabs.currentIndex() == 2  # Training tab
    assert window._diagnostics_view._training_view.overlay is not None
    assert [name for name, _ in window._loaded_runs] == ["v1p5_run"]  # labelled by run dir


def _training_curve() -> TrainingCurve:
    epochs = np.arange(1, 4)
    return TrainingCurve(
        epochs=epochs,
        loss={"val": np.asarray(1.0 / epochs, dtype=np.float64)},
        metric={"val": np.asarray(0.6 + 0.1 * epochs, dtype=np.float64)},
        metric_name="AUROC",
    )


def test_remove_training_run_drops_it_and_refeeds(qtbot: QtBot) -> None:
    """The Training-tab remove ✕ (via runRemoveRequested) drops the run + re-feeds the tab."""
    window = MainWindow()
    qtbot.addWidget(window)
    window._loaded_runs = [("v1", _training_curve()), ("v1.5", _training_curve())]
    window._show_training_runs()
    window._diagnostics_view.runRemoveRequested.emit("v1")  # exercises the shell connection
    assert [name for name, _ in window._loaded_runs] == ["v1.5"]
    assert "Removed run v1" in window.statusBar().currentMessage()
    assert window._diagnostics_view._training_view.overlay is not None  # still one run


def test_remove_last_training_run_returns_to_prompt(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._loaded_runs = [("v1", _training_curve())]
    window._show_training_runs()
    window._remove_training_run("v1")
    assert window._loaded_runs == []
    assert window._diagnostics_view._training_view._stack.currentIndex() == 0  # landing prompt


def test_open_bank_cancel_aborts_the_load(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Hitting Cancel mid-load trips the progress dialog; the next progress tick
    raises, the load unwinds, and no bank state is committed."""
    window = MainWindow()
    qtbot.addWidget(window)

    def cancel_then_progress(_path: str, *, progress: Callable[[int, int], None]) -> object:
        dialog = window.findChild(QtWidgets.QProgressDialog)
        assert dialog is not None  # the shell shows it before load_exploration runs
        dialog.cancel()  # as if the user clicked Cancel
        progress(0, 10)  # sees wasCanceled -> raises _LoadCancelled
        raise AssertionError("progress tick did not abort after Cancel")

    monkeypatch.setattr(shell_mod, "load_exploration", cancel_then_progress)
    window._open_bank_explore(str(tmp_path / "unused.h5"))

    assert "canceled" in window.statusBar().currentMessage().lower()
    assert window._explore_df is None  # nothing committed


def test_theme_change_restyles_the_detail(
    qtbot: QtBot,
    qapp: QtWidgets.QApplication,
    tiny_classifier_bank: ClassifierBank,
    tmp_path: Path,
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    window._explore_view.result_list._table.selectRow(0)
    light = window.findChild(QtGui.QAction, "themeAction_light")
    assert light is not None
    light.trigger()
    content = window._explore_view._detail._waveforms.content
    assert isinstance(content, TraceView)
    assert content.container.palette == plot_palette("light")
