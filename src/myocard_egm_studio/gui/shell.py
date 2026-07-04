"""The egm-studio main window — the ADR-025 layout shell.

ADR-025: a fixed top menu / header bar over a resizable-column work area flanked by
collapsible left and right sidebars, every separator draggable. Each sidebar
collapses to a thin Activity-Bar-style icon strip and expands again from it; the
header carries the three-mode segmented control. The theme (ADR-012) persists via
:mod:`..preferences`. Real content for each region arrives in Blocks 5+.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from myocard_egm_contracts import role_of
from myocard_egm_data.phases import PhaseManifest, load_phase_dir
from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.gui.preferences import load_theme, save_theme
from myocard_egm_studio.gui.sources import frame_eval_mode, load_exploration
from myocard_egm_studio.gui.theme import (
    DEFAULT_THEME,
    THEME_NAMES,
    apply_theme,
    chart_style,
    plot_palette,
)
from myocard_egm_studio.gui.views import MlDiagnosticsView, SignalExplorationView
from myocard_egm_studio.gui.widgets import FilterPanel, LoadedBanksList, PhaseTree, TraceData
from myocard_egm_studio.loaders import training_curve_from_run
from myocard_egm_studio.view_model import (
    apply_filter,
    combine_view_models,
    entries_by_id,
    filter_columns,
    phase_artifact_groups,
)
from myocard_egm_studio.view_model.artifact_metadata import artifact_metadata_text
from myocard_egm_studio.view_model.filtering import FilterSpec
from myocard_egm_studio.view_model.phase_actions import reveal_target
from myocard_egm_studio.view_model.phase_status import ArtifactStatus, phase_statuses

_WINDOW_TITLE = "egm-studio"
_MIN_WIDTH = 1100
_MIN_HEIGHT = 720
_SIDEBAR_DEFAULT_W = 240
_SIDEBAR_MIN_W = 160
_MAIN_MIN_W = 480
_MAIN_DEFAULT_W = 620
_STRIP_W = 40  # width of a collapsed sidebar's icon strip
_UNCONSTRAINED_W = 16777215  # Qt's QWIDGETSIZE_MAX — undoes a fixed width
# Child order within the horizontal work-area splitter.
_COL_LEFT, _COL_MAIN, _COL_RIGHT = 0, 1, 2

_MODES = ("Signal exploration", "ML diagnostics", "Paper figures")

#: A filter rebuild only shows its progress dialog if it runs longer than this, so a
#: quick filter applies without flashing a dialog while a slow one still gets a bar.
_RECALC_DIALOG_DELAY_MS = 300

_Side = Literal["left", "right"]
# Chevrons: the panel's collapse button points at the edge it hides toward; the
# strip's expand button points back toward the centre.
_COLLAPSE_GLYPH: dict[_Side, str] = {"left": "◂", "right": "▸"}
_EXPAND_GLYPH: dict[_Side, str] = {"left": "▸", "right": "◂"}


class _LoadCancelled(Exception):
    """Raised by the load progress callback when the user hits Cancel mid-load."""


@dataclass
class _LoadedBank:
    """One bank open in Flow A: its label, path, per-bank frame + display traces."""

    label: str
    path: str
    frame: pd.DataFrame
    traces: list[TraceData]


class _Placeholder(QtWidgets.QFrame):
    """A labelled stand-in panel for the main work area until Blocks 5+ fill it."""

    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("regionPanel")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        heading = QtWidgets.QLabel(title)
        heading.setObjectName("placeholderTitle")
        heading.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        if subtitle:
            caption = QtWidgets.QLabel(subtitle)
            caption.setObjectName("placeholderSubtitle")
            caption.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            caption.setWordWrap(True)
            layout.addWidget(caption)


class CollapsibleSidebar(QtWidgets.QWidget):
    """A sidebar that swaps between a full panel and a thin icon strip (ADR-025).

    Two stacked pages — the expanded panel (title + collapse button + body) and the
    collapsed Activity-Bar-style strip (an expand button) — with the widget's width
    pinned to the strip while collapsed. Both buttons emit :attr:`toggleRequested`;
    the owning window performs the toggle so the View-menu checkmark stays in sync.
    """

    toggleRequested = QtCore.Signal()

    def __init__(self, *, title: str, subtitle: str, side: _Side) -> None:
        super().__init__()
        self._collapsed = False
        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self._build_panel(title, subtitle, side))
        self._stack.addWidget(self._build_strip(title, side))
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)
        self.expand()

    def _build_panel(self, title: str, subtitle: str, side: _Side) -> QtWidgets.QWidget:
        panel = QtWidgets.QFrame()
        panel.setObjectName("regionPanel")
        v = QtWidgets.QVBoxLayout(panel)

        header = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(title)
        label.setObjectName("sidebarTitle")
        button = self._toggle_button(_COLLAPSE_GLYPH[side], f"Collapse {title}")
        if side == "left":
            header.addWidget(label)
            header.addStretch(1)
            header.addWidget(button)
        else:
            header.addWidget(button)
            header.addStretch(1)
            header.addWidget(label)
        v.addLayout(header)

        body = QtWidgets.QLabel(subtitle)
        body.setObjectName("placeholderSubtitle")
        body.setWordWrap(True)
        body.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        v.addWidget(body, 1)
        self._panel_layout = v
        self._body: QtWidgets.QWidget = body
        return panel

    def _build_strip(self, title: str, side: _Side) -> QtWidgets.QWidget:
        strip = QtWidgets.QFrame()
        strip.setObjectName("activityStrip")
        v = QtWidgets.QVBoxLayout(strip)
        v.setContentsMargins(4, 6, 4, 6)
        v.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        v.addWidget(self._toggle_button(_EXPAND_GLYPH[side], f"Show {title}"))
        return strip

    def _toggle_button(self, glyph: str, tooltip: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName("sidebarToggle")
        button.setText(glyph)
        button.setToolTip(tooltip)
        button.clicked.connect(self._request_toggle)
        return button

    def _request_toggle(self) -> None:
        self.toggleRequested.emit()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle(self) -> None:
        self.expand() if self._collapsed else self.collapse()

    def collapse(self) -> None:
        self._stack.setCurrentIndex(1)
        self.setMinimumWidth(_STRIP_W)
        self.setMaximumWidth(_STRIP_W)
        self._collapsed = True

    def expand(self) -> None:
        self._stack.setCurrentIndex(0)
        self.setMinimumWidth(_SIDEBAR_MIN_W)
        self.setMaximumWidth(_UNCONSTRAINED_W)
        self._collapsed = False

    def set_body(self, widget: QtWidgets.QWidget) -> None:
        """Replace the sidebar panel's body (the placeholder subtitle) with ``widget``."""
        self._panel_layout.removeWidget(self._body)
        self._body.deleteLater()
        self._body = widget
        self._panel_layout.addWidget(widget, 1)


def _run_label(path: str) -> str:
    """A short run label from a run.json path: the run directory name, else the file stem."""
    p = Path(path)
    return p.parent.name if p.stem == "run" else p.stem


class MainWindow(QtWidgets.QMainWindow):
    """Top-level shell: menu bar + header (mode switch) + collapsible column work area."""

    def __init__(self) -> None:
        super().__init__()
        self._bank_name = ""
        self._phase_manifest: PhaseManifest | None = None
        self._phase_dir = Path()
        self._last_metadata_text = ""  # last "Show metadata" text (for tests)
        self._metadata_dialog: QtWidgets.QDialog | None = None
        self._loaded_banks: list[_LoadedBank] = []  # banks open in Flow A (B7.8)
        self._explore_df: pd.DataFrame | None = None  # the combined view-model table
        self._loaded_runs: list[tuple[str, TrainingCurve]] = []  # training runs in Flow B (B8f)
        self.setWindowTitle(_WINDOW_TITLE)
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self._build_menu_bar()
        self._build_body()
        self.statusBar().showMessage("Ready")

    # -- menu bar -------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        self._open_action = file_menu.addAction("&Open bank…")
        self._open_action.setObjectName("openBank")
        self._open_action.triggered.connect(self._open_bank)
        run_action = file_menu.addAction("Open &training run…")
        run_action.setObjectName("openTrainingRun")
        run_action.triggered.connect(self._open_training_run)
        open_phase_action = file_menu.addAction("Open &phase…")
        open_phase_action.setObjectName("openPhase")
        open_phase_action.triggered.connect(self._open_phase)
        validate_action = file_menu.addAction("&Validate phase")
        validate_action.setObjectName("validatePhase")
        validate_action.triggered.connect(self._validate_phase)
        file_menu.addSeparator()
        file_menu.addAction("&Quit").triggered.connect(self.close)

        view_menu = menubar.addMenu("&View")
        self._left_action = self._sidebar_action(
            view_menu, "Toggle &left sidebar", "toggleLeftSidebar", "left"
        )
        self._right_action = self._sidebar_action(
            view_menu, "Toggle &right sidebar", "toggleRightSidebar", "right"
        )
        self._build_theme_menu(view_menu)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About egm-studio")

    def _sidebar_action(
        self, menu: QtWidgets.QMenu, text: str, object_name: str, side: _Side
    ) -> QtGui.QAction:
        """A checkable View action (ticked == expanded) that toggles one sidebar."""
        action = menu.addAction(text)
        action.setObjectName(object_name)
        action.setCheckable(True)
        action.setChecked(True)  # sidebars start expanded
        action.triggered.connect(lambda: self._toggle_sidebar(side))
        return action

    def _build_theme_menu(self, view_menu: QtWidgets.QMenu) -> None:
        """View > Theme: an exclusive, checkable group; the saved theme is ticked."""
        theme_menu = view_menu.addMenu("&Theme")
        current = load_theme(DEFAULT_THEME)
        self._current_theme = current
        self._theme_group = QtGui.QActionGroup(self)
        self._theme_group.setExclusive(True)
        for name in THEME_NAMES:
            action = theme_menu.addAction(name.capitalize())
            action.setObjectName(f"themeAction_{name}")
            action.setCheckable(True)
            action.setChecked(name == current)
            action.setData(name)
            self._theme_group.addAction(action)
        self._theme_group.triggered.connect(self._on_theme_selected)

    def _on_theme_selected(self, action: QtGui.QAction) -> None:
        """Apply the chosen theme to the running app and persist it for next launch."""
        name = action.data()
        app = QtWidgets.QApplication.instance()
        if isinstance(app, QtWidgets.QApplication):
            apply_theme(app, name)
        save_theme(name)
        self._current_theme = name
        self._explore_view.restyle(plot_palette(name), chart_style(name))
        self._diagnostics_view.restyle(plot_palette(name), chart_style(name))

    # -- body -----------------------------------------------------------------

    def _build_body(self) -> None:
        """Header strip stacked over the column splitter, filling the window."""
        central = QtWidgets.QWidget()
        column = QtWidgets.QVBoxLayout(central)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._build_header())
        column.addWidget(self._build_columns(), 1)
        self.setCentralWidget(central)

    def _build_header(self) -> QtWidgets.QWidget:
        """Fixed header below the menu bar: app title + the 3-mode segmented control."""
        header = QtWidgets.QFrame()
        header.setObjectName("headerBar")
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(12, 6, 12, 6)

        title = QtWidgets.QLabel(_WINDOW_TITLE)
        title.setObjectName("appTitle")
        row.addWidget(title)
        row.addStretch(1)

        self._mode_group = QtWidgets.QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for index, name in enumerate(_MODES):
            button = QtWidgets.QPushButton(name)
            button.setObjectName("modeButton")
            button.setCheckable(True)
            button.setChecked(index == 0)  # signal-exploration is the default mode
            self._mode_group.addButton(button, index)
            row.addWidget(button)
        self._mode_group.idClicked.connect(self._on_mode_changed)
        return header

    def _on_mode_changed(self, index: int) -> None:
        """Switch the main work area to the selected mode's view."""
        self._modes_stack.setCurrentIndex(index)
        self.statusBar().showMessage(f"Mode: {_MODES[index]}")

    def _build_columns(self) -> QtWidgets.QSplitter:
        """The draggable left | main | right work area (ADR-025)."""
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setObjectName("columnSplitter")
        splitter.setChildrenCollapsible(False)

        self._left_sidebar = CollapsibleSidebar(
            title="Banks & filters",
            subtitle="Open or add a bank to explore its traces",
            side="left",
        )
        self._left_sidebar.setObjectName("leftSidebar")
        self._left_sidebar.toggleRequested.connect(lambda: self._toggle_sidebar("left"))
        self._bank_list = LoadedBanksList()
        self._bank_list.removeRequested.connect(self._remove_bank)
        self._bank_list.bringToFrontRequested.connect(self._on_bring_to_front)
        self._filter_panel = FilterPanel()
        self._filter_panel.recalculateRequested.connect(self._on_recalculate)
        left_body = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_body)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(self._bank_list)
        left_layout.addWidget(self._filter_panel, 1)
        self._left_sidebar.set_body(left_body)

        self._explore_view = SignalExplorationView(
            plot_palette(self._current_theme), chart_style(self._current_theme)
        )
        self._diagnostics_view = MlDiagnosticsView(
            plot_palette(self._current_theme), chart_style(self._current_theme)
        )
        self._diagnostics_view.runRemoveRequested.connect(self._remove_training_run)
        self._modes_stack = QtWidgets.QStackedWidget()
        self._modes_stack.setMinimumWidth(_MAIN_MIN_W)
        self._modes_stack.addWidget(self._explore_view)  # 0 — signal exploration
        self._modes_stack.addWidget(self._diagnostics_view)  # 1 — ML diagnostics (Flow B)
        self._modes_stack.addWidget(_Placeholder("Paper figures", "Flow C — lands in Block 9"))

        self._right_sidebar = CollapsibleSidebar(
            title="Phase tree",
            subtitle="Open a phase (File ▸ Open phase…) to list its artifacts",
            side="right",
        )
        self._right_sidebar.setObjectName("rightSidebar")
        self._right_sidebar.toggleRequested.connect(lambda: self._toggle_sidebar("right"))
        self._phase_tree = PhaseTree()
        self._phase_tree.actionRequested.connect(self._on_phase_action)
        self._right_sidebar.set_body(self._phase_tree)

        splitter.addWidget(self._left_sidebar)
        splitter.addWidget(self._modes_stack)
        splitter.addWidget(self._right_sidebar)
        splitter.setStretchFactor(_COL_LEFT, 0)
        splitter.setStretchFactor(_COL_MAIN, 1)
        splitter.setStretchFactor(_COL_RIGHT, 0)
        splitter.setSizes([_SIDEBAR_DEFAULT_W, _MAIN_DEFAULT_W, _SIDEBAR_DEFAULT_W])
        self._splitter = splitter
        return splitter

    def _toggle_sidebar(self, side: _Side) -> None:
        """Collapse/expand a sidebar, resize the splitter, and sync the View checkmark."""
        sidebar = self._left_sidebar if side == "left" else self._right_sidebar
        action = self._left_action if side == "left" else self._right_action
        sidebar.toggle()
        collapsed = sidebar.is_collapsed()
        action.setChecked(not collapsed)
        self._apply_sidebar_width(side, collapsed=collapsed)

    def _apply_sidebar_width(self, side: _Side, *, collapsed: bool) -> None:
        """Drive the splitter to the strip / default width.

        A QSplitter owns its children's sizes and ignores their max-width, so a
        collapse won't shrink the column on its own — we set the sizes here,
        moving the delta to/from the main column.
        """
        sizes = self._splitter.sizes()
        if len(sizes) != 3:
            return
        slot = _COL_LEFT if side == "left" else _COL_RIGHT
        target = _STRIP_W if collapsed else _SIDEBAR_DEFAULT_W
        delta = target - sizes[slot]
        sizes[slot] = target
        sizes[_COL_MAIN] = max(_MAIN_MIN_W, sizes[_COL_MAIN] - delta)
        self._splitter.setSizes(sizes)

    # -- open / add banks (direct load; File > Open bank) ----------------------

    def _open_bank(self) -> None:
        """File > Open bank…: load bank file(s) — replace when nothing is loaded,
        append when one or more banks already are (the menu label reflects which).

        Starting fresh once banks are loaded is done by removing them in the
        loaded-banks roster, so this single action covers open + add.
        """
        replace_first = not self._loaded_banks
        title = "Add bank(s)" if self._loaded_banks else "Open bank(s)"
        for index, path in enumerate(self._pick_banks(title)):
            self._open_bank_explore(path, replace=replace_first and index == 0)

    def _pick_banks(self, title: str) -> list[str]:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, title, "", "EGM banks (*.h5 *.hdf5);;All files (*)"
        )
        return paths

    def _open_bank_explore(
        self,
        path: str,
        *,
        focus: Literal["summary", "explore"] | None = "summary",
        replace: bool = True,
    ) -> None:
        """Load one bank + add it to (or ``replace``) the loaded set; feed Flow A.

        ``focus`` picks the sub-tab to land on — Summary by default (File ▸ Open
        bank, "View feature distributions"), "explore" straight to the result list
        ("Explore signal"), or None to keep the current tab (Add / Remove bank).

        Feature extraction (O(T^2) sample entropy) is the slow step and runs on the
        GUI thread, so a large bank would freeze the window. A modal QProgressDialog
        keeps it responsive: it reports extraction progress and its Cancel button
        aborts the load — the ``progress`` callback raises :class:`_LoadCancelled`,
        which unwinds the in-flight :func:`load_exploration`.
        """
        dialog = QtWidgets.QProgressDialog("Loading bank…", "Cancel", 0, 0, self)
        dialog.setWindowTitle("Open bank")
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)  # show at once — the read can stall before progress
        dialog.setAutoClose(False)  # we close it in the finally, once, deterministically
        dialog.setAutoReset(False)
        dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)  # no per-open leak
        dialog.setValue(0)  # forces the (min-duration 0) dialog to paint immediately
        QtWidgets.QApplication.processEvents()

        def on_progress(done: int, total: int) -> None:
            if dialog.maximum() != total:
                dialog.setMaximum(total)  # 0 -> total: busy spinner becomes a real bar
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()  # paint + deliver the Cancel click
            if dialog.wasCanceled():
                raise _LoadCancelled

        try:
            frame, traces = load_exploration(path, progress=on_progress)
        except _LoadCancelled:
            self.statusBar().showMessage("Bank load canceled.")
            dialog.close()
            return
        except Exception as exc:  # surface any read / validation error to the status bar
            self.statusBar().showMessage(f"Could not open bank: {exc}")
            dialog.close()
            return

        # Extraction is done, but building the views (combine + summary grid + the
        # result table) is also slow on a big bank — keep the dialog up for a second
        # "Building views…" phase so the bar spans the whole load, not just extraction.
        dialog.setLabelText("Building views…")
        dialog.setCancelButton(None)  # past the point of a clean abort

        try:
            self._add_loaded_bank(
                path, frame, traces, replace=replace, focus=focus, progress=self._pump(dialog)
            )
        finally:
            dialog.close()

    def _recalc_dialog(self) -> QtWidgets.QProgressDialog:
        """A modal, cancel-less progress dialog for a filter-apply rebuild.

        Unlike the load dialog it isn't force-painted: ``_RECALC_DIALOG_DELAY_MS`` gates
        the show, so a quick filter finishes without flashing a dialog while a slow
        rebuild still surfaces one. ``setValue(0)`` starts that min-duration timer.
        """
        dialog = QtWidgets.QProgressDialog("Applying filter…", "", 0, 0, self)
        dialog.setCancelButton(None)
        dialog.setWindowTitle(_WINDOW_TITLE)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(_RECALC_DIALOG_DELAY_MS)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setValue(0)
        return dialog

    def _pump(self, dialog: QtWidgets.QProgressDialog) -> Callable[[int, int], None]:
        """A progress callback that advances ``dialog`` and keeps the UI painting."""

        def on_progress(done: int, total: int) -> None:
            if dialog.maximum() != total:
                dialog.setMaximum(total)  # 0 -> total: the busy spinner becomes a real bar
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()

        return on_progress

    def _add_loaded_bank(
        self,
        path: str,
        frame: pd.DataFrame,
        traces: list[TraceData],
        *,
        replace: bool,
        focus: Literal["summary", "explore"] | None,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Add (or ``replace`` the set with) a freshly loaded bank, then rebuild."""
        if frame.empty:
            self.statusBar().showMessage("That bank has no traces to display.")
            return
        label = str(frame["source"].iloc[0]) if "source" in frame.columns else Path(path).stem
        bank = _LoadedBank(label=label, path=path, frame=frame, traces=list(traces))
        kept = [] if replace else [b for b in self._loaded_banks if b.path != path]
        self._loaded_banks = [*kept, bank]
        self._refresh_loaded(focus=focus, progress=progress)

    def _remove_bank(self, path: str) -> None:
        """Drop the loaded bank at ``path`` (the loaded-banks list remove button)."""
        self._loaded_banks = [b for b in self._loaded_banks if b.path != path]
        self._refresh_loaded(focus=None)

    def _on_bring_to_front(self, path: str) -> None:
        """Raise the roster bank's points to the front of the scatter (by its source label)."""
        for bank in self._loaded_banks:
            if bank.path == path:
                self._explore_view.bring_scatter_to_front(bank.label)
                return

    # -- open training run (File > Open training run) --------------------------

    def _open_training_run(self) -> None:
        """File > Open training run…: load run.json record(s) into the Flow B Training tab.

        Additive like Add bank — each run overlays as another coloured line. A run.json is
        not a ClassifierBank, so runs load independently of the evaluated-bank path: this
        feeds the diagnostics view's Training tab directly, then switches to ML-diagnostics
        mode. A run already loaded (same label) is skipped; a read error is reported.
        """
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Open training run", "", "Run records (*.json);;All files (*)"
        )
        added = [self._load_training_run(path, _run_label(path)) for path in paths]
        if any(added):
            self._show_training_runs()

    def _load_training_run(self, path: str, label: str) -> bool:
        """Add one run.json to the Flow B run set; return whether it was newly added.

        Skips a run already loaded under ``label`` (no double-overlay) and reports a
        read error to the status bar. Shared by File ▸ Open training run and the phase
        tree's View-training-curves action.
        """
        if any(name == label for name, _ in self._loaded_runs):
            return False
        try:
            curve = training_curve_from_run(path)
        except Exception as exc:  # a bad / unreadable run.json -> status bar, no crash
            self.statusBar().showMessage(f"Could not open training run: {exc}")
            return False
        self._loaded_runs.append((label, curve))
        return True

    def _show_training_runs(self) -> None:
        """Feed the loaded runs to Flow B's Training tab + switch to ML-diagnostics mode."""
        self._diagnostics_view.set_runs(self._loaded_runs)
        self._show_mode(1)  # ML-diagnostics mode; the view lands on the Training tab
        self.statusBar().showMessage(f"Loaded {len(self._loaded_runs)} training run(s)")

    def _remove_training_run(self, label: str) -> None:
        """Drop the training run ``label`` (its Training-tab roster ✕) and re-feed the tab."""
        self._loaded_runs = [(name, curve) for name, curve in self._loaded_runs if name != label]
        self._diagnostics_view.set_runs(self._loaded_runs)  # empty -> back to the prompt
        remaining = len(self._loaded_runs)
        self.statusBar().showMessage(f"Removed run {label} — {remaining} run(s) loaded")

    def _refresh_loaded(
        self,
        *,
        focus: Literal["summary", "explore"] | None,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Rebuild the combined view-model + traces from the loaded banks; feed the view.

        The banks pool into one combined frame (unique row_id) + one traces list in
        load order, so the result list + detail span every loaded bank. The summary
        is fed the combined frame (B7.8c overlays it per source); an empty set (last
        bank removed) resets the view. ``progress`` reports the result-table build on
        the big-bank load (B7.8b-perf).
        """
        combined = combine_view_models([b.frame for b in self._loaded_banks])
        traces = [trace for b in self._loaded_banks for trace in b.traces]
        self._explore_df = combined if self._loaded_banks else None
        self._bank_name = ", ".join(b.label for b in self._loaded_banks)
        self._bank_list.set_banks(
            [(b.label, b.path, color_for(i)) for i, b in enumerate(self._loaded_banks)]
        )
        # Once a bank is loaded, the bank openers become "Add …" (B7.8b-fix).
        loaded = bool(self._loaded_banks)
        self._open_action.setText("&Add bank…" if loaded else "&Open bank…")
        self._phase_tree.set_add_mode(loaded)
        self._explore_view.set_traces(traces)
        # A fresh load shows the full frame; set_columns resets the filter to empty
        # (Recalculate re-enables once a condition is added, and never fires live).
        # set_results feeds list + scatter + summary grid/stats exactly once here —
        # progress-reported for the big load — then we land on the requested tab.
        self._filter_panel.set_columns(filter_columns(combined))
        self._explore_view.set_results(combined, progress=progress)
        # ML diagnostics (Flow B) auto-populate when the loaded set carries predictions
        # (build_view_model joined the ML columns); otherwise the diagnostics view resets.
        mode = frame_eval_mode(combined)
        if mode is not None:
            self._diagnostics_view.set_evaluated(combined, mode, traces=traces)
        else:
            self._diagnostics_view.clear()
        self._show_mode(0)
        if focus == "explore":
            self._explore_view.show_explore()
        else:  # "summary" or None (Add / Remove bank) land on the summary overview
            self._explore_view.show_summary()
        self.statusBar().showMessage(self._loaded_status(combined))

    def _loaded_status(self, combined: pd.DataFrame) -> str:
        count = len(self._loaded_banks)
        if count == 0:
            return "No banks loaded."
        banks = "1 bank" if count == 1 else f"{count} banks"
        return f"Loaded {banks} — {len(combined.index)} trace(s); filter or sort, then select"

    def _on_recalculate(self, spec: FilterSpec) -> None:
        """Apply the shared Banks-&-filter spec to the loaded frame; rebuild both flows' lists.

        Fired by the one FilterPanel's Recalculate button (not live), so several conditions
        apply in one pass. It drives Signal exploration (list + scatter + grid) and — when
        the loaded set is evaluated — the ML-diagnostics Explore list (the metric tabs keep
        the full set). The rebuild can be slow on a big bank, so it runs under a progress
        dialog like the initial load rather than freezing the window.
        """
        if self._explore_df is None:
            return
        filtered = self._explore_df[apply_filter(self._explore_df, spec)]
        dialog = self._recalc_dialog()
        try:
            self._explore_view.set_results(filtered, progress=self._pump(dialog))
            if frame_eval_mode(self._explore_df) is not None:  # Flow B is populated
                self._diagnostics_view.set_explore_results(filtered, spec)
        finally:
            dialog.close()
        total, kept = len(self._explore_df.index), len(filtered.index)
        if kept == total:
            self.statusBar().showMessage(f"{total} trace(s)")
        else:
            self.statusBar().showMessage(f"{kept} of {total} trace(s) match the filter")

    def _show_mode(self, index: int) -> None:
        """Activate a mode: switch the stack page and tick its header button."""
        self._modes_stack.setCurrentIndex(index)
        button = self._mode_group.button(index)
        if button is not None:
            button.setChecked(True)

    # -- open phase (File > Open phase) ---------------------------------------

    def _open_phase(self) -> None:
        """File > Open phase…: pick a phase folder and list its artifacts in the tree."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Open phase folder")
        if folder:
            self._load_phase_into_tree(folder)

    def _load_phase_into_tree(self, folder: str) -> None:
        """Load a phase's manifest and populate the right-rail Phase tree (testable)."""
        try:
            manifest = load_phase_dir(folder)
        except Exception as exc:  # a missing / malformed manifest -> status bar, tree unchanged
            self.statusBar().showMessage(f"Could not open phase: {exc}")
            return
        groups = phase_artifact_groups(manifest)
        self._phase_tree.set_groups(groups)
        self._phase_manifest = manifest
        self._phase_dir = Path(folder)
        statuses = phase_statuses(manifest, self._phase_dir)
        self._phase_tree.set_statuses(statuses)
        total = len(statuses)
        missing = sum(1 for status in statuses.values() if status is ArtifactStatus.MISSING)
        note = f"{missing} missing" if missing else "all present"
        self.statusBar().showMessage(
            f"Loaded phase {manifest.phase} — {total} artifact(s), {note}; not yet validated"
        )

    def _validate_phase(self) -> None:
        """File > Validate phase: run the full per-type format validation + re-mark."""
        if self._phase_manifest is None:
            self.statusBar().showMessage("Open a phase first.")
            return
        statuses = phase_statuses(self._phase_manifest, self._phase_dir, validate=True)
        self._phase_tree.set_statuses(statuses)
        counts = Counter(statuses.values())
        parts = [f"{counts[ArtifactStatus.OK]} ok"]
        if counts[ArtifactStatus.INVALID]:
            parts.append(f"{counts[ArtifactStatus.INVALID]} invalid")
        if counts[ArtifactStatus.MISSING]:
            parts.append(f"{counts[ArtifactStatus.MISSING]} missing")
        self.statusBar().showMessage(
            f"Validated phase {self._phase_manifest.phase} — {', '.join(parts)}"
        )

    # -- phase-tree right-click actions ---------------------------------------

    def _on_phase_action(self, action_id: str, artifact_id: str) -> None:
        """Execute a Phase-tree right-click action against one artifact."""
        if self._phase_manifest is None:
            return
        entry = entries_by_id(self._phase_manifest).get(artifact_id)
        if entry is None:
            return
        if action_id == "copy_id":
            self._copy_to_clipboard(entry.id)
        elif action_id == "show_metadata":
            resolved = self._phase_dir / entry.path
            try:
                text = artifact_metadata_text(role_of(entry.id), resolved)
            except Exception as exc:  # missing / malformed file -> friendly text, no crash
                text = f"Could not read metadata for {entry.id}:\n{exc}"
            self._show_metadata(entry.id, text)
        elif action_id == "reveal_file":
            self._reveal(reveal_target(self._phase_dir, entry.path))
        elif action_id == "explore_signal":
            # Explore signal always replaces the loaded set (B7.8b-fix).
            self._open_bank_explore(str(self._phase_dir / entry.path), focus="explore")
        elif action_id == "view_feature_distributions":
            # Additive when a bank is already loaded — builds the summary overlay.
            self._open_bank_explore(
                str(self._phase_dir / entry.path),
                focus="summary",
                replace=not self._loaded_banks,
            )
        elif action_id == "view_ml_diagnostics":
            # Load the predictions bank (additive) then land on Flow B — the single
            # Open-bank path already populates ML diagnostics when a bank has predictions.
            self._open_bank_explore(
                str(self._phase_dir / entry.path),
                focus=None,
                replace=not self._loaded_banks,
            )
            self._show_mode(1)  # ML-diagnostics mode
        elif action_id == "view_curves":
            # Load the run.json into Flow B's Training tab (same path as File ▸ Open
            # training run, but with the artifact resolved from the manifest).
            self._load_training_run(str(self._phase_dir / entry.path), entry.id)
            if any(name == entry.id for name, _ in self._loaded_runs):
                self._show_training_runs()

    def _copy_to_clipboard(self, text: str) -> None:
        app = QtWidgets.QApplication.instance()
        if isinstance(app, QtWidgets.QApplication):
            app.clipboard().setText(text)
        self.statusBar().showMessage(f"Copied id {text}")

    def _show_metadata(self, artifact_id: str, text: str) -> None:
        """Show an artifact's file metadata in a scrollable, non-modal dialog."""
        self._last_metadata_text = text
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"{artifact_id} — metadata")
        dialog.resize(560, 480)
        layout = QtWidgets.QVBoxLayout(dialog)
        view = QtWidgets.QPlainTextEdit(dialog)
        view.setReadOnly(True)
        view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        view.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont))
        view.setPlainText(text)
        layout.addWidget(view)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close, parent=dialog
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        self._metadata_dialog = dialog  # keep a reference so it isn't garbage-collected
        dialog.show()  # non-modal: hand control straight back to the app

    def _reveal(self, target: Path) -> None:
        """Open ``target`` (the artifact's folder) in the OS file browser."""
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(target)))
        self.statusBar().showMessage(f"Revealing {target}")
