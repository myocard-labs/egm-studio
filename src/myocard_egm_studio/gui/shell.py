"""The egm-studio main window — the ADR-025 layout shell.

ADR-025: a fixed top menu / header bar over a resizable-column work area flanked by
collapsible left and right sidebars, every separator draggable. Each sidebar
collapses to a thin Activity-Bar-style icon strip and expands again from it; the
header carries the three-mode segmented control. The theme (ADR-012) persists via
:mod:`..preferences`. Real content for each region arrives in Blocks 5+.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd
from myocard_egm_contracts import Role, role_of
from myocard_egm_data.phases import (
    MANIFEST_FILENAME,
    FigureSpec,
    Observation,
    ObservationEntry,
    PhaseManifest,
    TraceRef,
    load_figure_spec,
    load_observation,
    load_phase_dir,
)
from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.gui.new_phase_dialog import NewPhaseDialog
from myocard_egm_studio.gui.preferences import (
    load_scratch_dir,
    load_theme,
    save_scratch_dir,
    save_theme,
)
from myocard_egm_studio.gui.save_observation_dialog import SaveObservationDialog
from myocard_egm_studio.gui.settings_dialog import SettingsDialog
from myocard_egm_studio.gui.sources import frame_eval_mode, load_exploration
from myocard_egm_studio.gui.theme import (
    DEFAULT_THEME,
    THEME_NAMES,
    ThemeName,
    apply_theme,
    chart_style,
    plot_palette,
)
from myocard_egm_studio.gui.views import (
    MlDiagnosticsView,
    PaperFigurePrepView,
    SignalExplorationView,
)
from myocard_egm_studio.gui.widgets import (
    FilterPanel,
    LoadedBanksList,
    PhaseTree,
    TraceData,
)
from myocard_egm_studio.loaders import (
    bank_paths_from_manifest,
    resolve_bank_paths,
    training_curve_from_run,
)
from myocard_egm_studio.save import (
    SCRATCH_PHASE,
    bank_entry,
    build_observation,
    capture_view_state,
    describe_filter,
    empty_manifest,
    figure_entry,
    load_scratch,
    manifest_section,
    observation_entry,
    parse_filter,
    references_from,
    remove_entry,
    run_entry,
    save_figure_spec,
    save_manifest,
    save_observation,
    update_observation,
    with_entry,
)
from myocard_egm_studio.view_model import (
    apply_filter,
    combine_view_models,
    entries_by_id,
    filter_columns,
    phase_artifact_groups,
)
from myocard_egm_studio.view_model.artifact_metadata import artifact_metadata_text
from myocard_egm_studio.view_model.combine import ROW_ID
from myocard_egm_studio.view_model.dependencies import manifest_ids
from myocard_egm_studio.view_model.figure_output import figure_output_exists_map, figure_output_path
from myocard_egm_studio.view_model.filtering import FilterSpec
from myocard_egm_studio.view_model.phase_actions import reveal_target
from myocard_egm_studio.view_model.phase_status import (
    ArtifactStatus,
    StatusReport,
    phase_status_report,
)

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
#: Where a loaded producer artifact (or an authored save) is indexed.
_Target = Literal["scratch", "phase"]


class _ArtifactEntry(Protocol):
    """The pointer fields a tree action needs off any manifest entry."""

    id: str
    path: str


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
        self._body.hide()  # drop it from view now; deleteLater alone lingers off the event loop
        self._body.deleteLater()
        self._body = widget
        self._panel_layout.addWidget(widget, 1)


def _run_label(path: str) -> str:
    """A short run label from a run.json path: the run directory name, else the file stem."""
    p = Path(path)
    return p.parent.name if p.stem == "run" else p.stem


def _status_summary(report: dict[str, StatusReport]) -> str:
    """A short "N ok, M unresolved, …" line from a status report (for the status bar)."""
    counts = Counter(r.status for r in report.values())
    parts = [f"{counts[ArtifactStatus.OK]} ok"]
    for status, label in (
        (ArtifactStatus.UNRESOLVED, "unresolved"),
        (ArtifactStatus.INVALID, "invalid"),
        (ArtifactStatus.MISSING, "missing"),
    ):
        if counts[status]:
            parts.append(f"{counts[status]} {label}")
    return ", ".join(parts)


class MainWindow(QtWidgets.QMainWindow):
    """Top-level shell: menu bar + header (mode switch) + collapsible column work area."""

    def __init__(self) -> None:
        super().__init__()
        self._bank_name = ""
        self._phase_manifest: PhaseManifest | None = None
        self._phase_dir = Path()
        self._phase_validated = False  # has Validate phase run on the current phase?
        self._scratch_dir = load_scratch_dir()  # where no-phase saves land (Settings-editable)
        self._scratch_manifest = empty_manifest(
            SCRATCH_PHASE
        )  # _refresh_scratch loads the real one
        self._scratch_validated = False  # has Validate run over the scratch area?
        self._last_metadata_text = ""  # last "Show metadata" text (for tests)
        self._metadata_dialog: QtWidgets.QDialog | None = None
        self._loaded_banks: list[_LoadedBank] = []  # banks open in Flow A (B7.8)
        self._explore_df: pd.DataFrame | None = None  # the combined view-model table
        self._applied_spec: FilterSpec = FilterSpec(())  # last-applied filter (B10 capture)
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
        self._phase_target_actions: list[QtGui.QAction] = []  # "…to phase", enabled with a phase
        file_menu.aboutToShow.connect(self._sync_phase_targets)
        # Loading a producer opens it for viewing AND indexes it into the chosen area — a
        # submenu picks scratch vs the loaded phase (B10h-2b). The bank submenu relabels to
        # "Add bank" once banks are loaded (the openers are additive, B7.8b-fix).
        self._bank_menu = file_menu.addMenu("&Open bank")
        self._bank_menu.setObjectName("openBank")
        self._add_load_targets(self._bank_menu, "openBank", self._load_banks)
        run_menu = file_menu.addMenu("Open &training run")
        run_menu.setObjectName("openTrainingRun")
        self._add_load_targets(run_menu, "openTrainingRun", self._load_runs)
        new_phase_action = file_menu.addAction("&New phase…")
        new_phase_action.setObjectName("newPhase")
        new_phase_action.triggered.connect(self._new_phase)
        open_phase_action = file_menu.addAction("Open &phase…")
        open_phase_action.setObjectName("openPhase")
        open_phase_action.triggered.connect(self._open_phase)
        validate_action = file_menu.addAction("&Validate phase")
        validate_action.setObjectName("validatePhase")
        validate_action.triggered.connect(self._validate_phase)
        file_menu.addSeparator()
        save_obs_action = file_menu.addAction("&Save observation…")
        save_obs_action.setObjectName("saveObservation")
        save_obs_action.triggered.connect(self._save_observation)
        file_menu.addSeparator()
        settings_action = file_menu.addAction("Se&ttings…")
        settings_action.setObjectName("openSettings")
        settings_action.triggered.connect(self._open_settings)
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

    def _add_load_targets(
        self, menu: QtWidgets.QMenu, key: str, handler: Callable[[_Target], None]
    ) -> None:
        """Give a load submenu its two targets: Load to scratch / Load to phase."""
        to_scratch = menu.addAction("Load to &scratch…")
        to_scratch.setObjectName(f"{key}ToScratch")
        to_scratch.triggered.connect(lambda: handler("scratch"))
        to_phase = menu.addAction("Load to &phase…")
        to_phase.setObjectName(f"{key}ToPhase")
        to_phase.triggered.connect(lambda: handler("phase"))
        self._phase_target_actions.append(to_phase)

    def _sync_phase_targets(self) -> None:
        """Enable the "…to phase" actions only while a phase is loaded (menu aboutToShow)."""
        has_phase = self._phase_manifest is not None
        for action in self._phase_target_actions:
            action.setEnabled(has_phase)

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
        """Apply the theme chosen from the View ▸ Theme menu."""
        self._set_theme(action.data())

    def _set_theme(self, name: str) -> None:
        """Apply ``name`` to the running app, persist it, restyle, and tick the menu.

        Shared by the View ▸ Theme menu and the Settings dialog, so both entry points
        stay in sync (the menu's checkmark follows a change made in Settings). An
        unrecognised name falls back to the default.
        """
        theme = self._as_theme(name)
        app = QtWidgets.QApplication.instance()
        if isinstance(app, QtWidgets.QApplication):
            apply_theme(app, theme)
        save_theme(theme)
        self._current_theme = theme
        self._explore_view.restyle(plot_palette(theme), chart_style(theme))
        self._diagnostics_view.restyle(plot_palette(theme), chart_style(theme))
        for action in self._theme_group.actions():
            action.setChecked(action.data() == theme)

    @staticmethod
    def _as_theme(name: str) -> ThemeName:
        """Narrow an arbitrary string to a known ``ThemeName`` (default if unrecognised)."""
        for candidate in THEME_NAMES:
            if candidate == name:
                return candidate
        return DEFAULT_THEME

    def _open_settings(self) -> None:
        """File ▸ Settings…: edit the scratch folder + theme; apply the choices on accept."""
        dialog = SettingsDialog(
            self, scratch_dir=self._scratch_dir, theme=self._current_theme, themes=THEME_NAMES
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted.value:
            self._scratch_dir = dialog.scratch_dir()
            save_scratch_dir(self._scratch_dir)
            self._set_theme(dialog.theme())

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
        self._figure_view = PaperFigurePrepView()
        self._figure_view.statusMessage.connect(self.statusBar().showMessage)
        self._figure_view.figureGenerated.connect(self._refresh_figure_outputs)
        self._figure_view.saveIntoPhaseRequested.connect(self._save_figure_into_phase)
        self._modes_stack = QtWidgets.QStackedWidget()
        self._modes_stack.setMinimumWidth(_MAIN_MIN_W)
        self._modes_stack.addWidget(self._explore_view)  # 0 — signal exploration
        self._modes_stack.addWidget(self._diagnostics_view)  # 1 — ML diagnostics (Flow B)
        self._modes_stack.addWidget(self._figure_view)  # 2 — paper figure prep (Flow C)

        self._right_sidebar = CollapsibleSidebar(
            title="Phase tree",
            subtitle="Open a phase (File ▸ Open phase…) to list its artifacts",
            side="right",
        )
        self._right_sidebar.setObjectName("rightSidebar")
        self._right_sidebar.toggleRequested.connect(lambda: self._toggle_sidebar("right"))
        self._phase_tree = PhaseTree()
        self._phase_tree.actionRequested.connect(self._on_phase_action)
        # Scratch is a staging area rendered as its own phase tree (same organization +
        # actions, plus Promote/Delete). It sits under the phase tree and stays hidden until
        # it holds something, leaving the sidebar unchanged for an empty scratch.
        self._scratch_tree = PhaseTree(scratch=True)
        self._scratch_tree.actionRequested.connect(self._on_scratch_action)
        self._scratch_pane = QtWidgets.QWidget()
        scratch_layout = QtWidgets.QVBoxLayout(self._scratch_pane)
        scratch_layout.setContentsMargins(0, 0, 0, 0)
        scratch_title = QtWidgets.QLabel("Scratch")
        scratch_title.setObjectName("sidebarTitle")
        scratch_layout.addWidget(scratch_title)
        scratch_layout.addWidget(self._scratch_tree, 1)
        self._scratch_pane.setVisible(False)
        right_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        right_split.setObjectName("rightSplit")
        right_split.addWidget(self._phase_tree)
        right_split.addWidget(self._scratch_pane)
        right_split.setStretchFactor(0, 3)  # the phase tree dominates; scratch takes the rest
        right_split.setStretchFactor(1, 1)
        self._right_sidebar.set_body(right_split)
        self._refresh_scratch()  # show the scratch tree if the folder already has items

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

    def _load_banks(self, target: _Target) -> None:
        """File > Open bank ▸ Load to scratch / phase: view the bank(s) in Flow A and index
        each into ``target``. Replaces the loaded set when nothing is loaded, else appends
        (the submenu title reflects which; starting fresh is done via the roster remove)."""
        replace_first = not self._loaded_banks
        title = "Add bank(s)" if self._loaded_banks else "Open bank(s)"
        for index, path in enumerate(self._pick_banks(title)):
            self._open_bank_explore(path, replace=replace_first and index == 0)
            self._index_producer(path, kind="bank", target=target)

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

    def _load_runs(self, target: _Target) -> None:
        """File > Open training run ▸ Load to scratch / phase: overlay run.json record(s) in
        the Flow B Training tab and index each into ``target``.

        Additive like Add bank — each run overlays as another coloured line. A run already
        loaded (same label) is skipped for the overlay; a read error is reported.
        """
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Open training run", "", "Run records (*.json);;All files (*)"
        )
        added = [self._load_training_run(path, _run_label(path)) for path in paths]
        if any(added):
            self._show_training_runs()
        for path in paths:
            self._index_producer(path, kind="run", target=target)

    def _index_producer(self, path: str, *, kind: Literal["bank", "run"], target: _Target) -> None:
        """Index a loaded producer artifact (a path pointer) into scratch or the loaded phase."""
        try:
            entry = bank_entry(path) if kind == "bank" else run_entry(path)
        except Exception as exc:  # unreadable / id-less file -> viewed, but not indexed
            self.statusBar().showMessage(f"Loaded, but could not index {Path(path).name}: {exc}")
            return
        section = manifest_section(entry.id)
        if target == "phase" and self._phase_manifest is not None:
            save_manifest(with_entry(self._phase_manifest, section, entry), self._phase_dir)
            self._reindex_phase_after_write()
            self.statusBar().showMessage(f"Loaded {entry.id} into the phase")
        else:
            save_manifest(
                with_entry(load_scratch(self._scratch_dir), section, entry), self._scratch_dir
            )
            self._refresh_scratch()
            self.statusBar().showMessage(f"Loaded {entry.id} into scratch")

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
        self._bank_menu.setTitle("&Add bank" if loaded else "&Open bank")
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
        self._applied_spec = spec  # remembered for observation capture (B10)
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

    # -- new / open phase (File > New phase, File > Open phase) ----------------

    def _new_phase(self) -> None:
        """File > New phase…: write an empty in-progress phase into a folder and open it."""
        dialog = NewPhaseDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        folder = Path(dialog.folder())
        if (folder / MANIFEST_FILENAME).exists():
            self.statusBar().showMessage(f"{folder} already holds a phase manifest — not created.")
            return
        phase = dialog.phase()
        save_manifest(empty_manifest(phase), folder)
        self._load_phase_into_tree(str(folder))  # opens the freshly-created empty phase
        self.statusBar().showMessage(f"Created phase {phase:g} in {folder}")

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
        self._phase_validated = False  # a freshly-loaded phase is existence-checked only
        # Flow C resolves a figure spec's bank ids against scratch + this phase, and offers
        # the phase's observations as illustrate-able links.
        self._figure_view.set_bank_paths(self._all_bank_paths())
        self._figure_view.set_observations(self._existing_observation_ids())
        self._refresh_figure_outputs()  # tune the figure menus to which images exist
        report = self._mark_statuses(manifest, validate=False)
        total = len(report)
        missing = sum(1 for r in report.values() if r.status is ArtifactStatus.MISSING)
        note = f"{missing} missing" if missing else "all present"
        self.statusBar().showMessage(
            f"Loaded phase {manifest.phase} — {total} artifact(s), {note}; not yet validated"
        )

    def _validate_phase(self) -> None:
        """File > Validate phase: fully validate the loaded phase *and* the scratch area."""
        messages: list[str] = []
        if self._phase_manifest is not None:
            report = self._mark_statuses(self._phase_manifest, validate=True)
            self._phase_validated = True  # indicators now reflect a full validation
            messages.append(f"phase {self._phase_manifest.phase} — {_status_summary(report)}")
        if manifest_ids(self._scratch_manifest):
            self._scratch_validated = True
            scratch_report = self._paint_scratch(validate=True)
            messages.append(f"scratch — {_status_summary(scratch_report)}")
        self.statusBar().showMessage(
            f"Validated {'; '.join(messages)}" if messages else "Nothing to validate."
        )

    def _mark_statuses(self, manifest: PhaseManifest, *, validate: bool) -> dict[str, StatusReport]:
        """Compute the phase's status report and paint the tree (dots + 'why' tooltips)."""
        report = phase_status_report(manifest, self._phase_dir, validate=validate)
        self._phase_tree.set_statuses(
            {i: r.status for i, r in report.items()},
            {i: r.detail for i, r in report.items()},
        )
        return report

    def _all_bank_paths(self) -> dict[str, Path]:
        """Every artifact id -> path across scratch + the loaded phase, so Flow C previews a
        figure whether its banks are staged in scratch or indexed in the phase (2c / item 3)."""
        paths = bank_paths_from_manifest(self._scratch_manifest, self._scratch_dir)
        if self._phase_manifest is not None:
            paths |= bank_paths_from_manifest(self._phase_manifest, self._phase_dir)
        return paths

    # -- phase-tree right-click actions ---------------------------------------

    def _on_phase_action(self, action_id: str, artifact_id: str) -> None:
        """Execute a Phase-tree right-click action against one artifact (phase scope)."""
        if self._phase_manifest is None:
            return
        entry = entries_by_id(self._phase_manifest).get(artifact_id)
        if entry is not None:
            self._run_artifact_action(
                action_id, entry, base_dir=self._phase_dir, scope_dirs=[self._phase_dir]
            )

    def _run_artifact_action(
        self,
        action_id: str,
        entry: _ArtifactEntry,
        *,
        base_dir: Path,
        scope_dirs: Sequence[Path],
    ) -> None:
        """Run a tree action against ``entry`` under ``base_dir``. Shared by the phase tree
        and the scratch tree; ``scope_dirs`` is where an observation's banks resolve — the
        phase alone, or [scratch, phase] for a scratch item (2c)."""
        resolved = base_dir / entry.path
        if action_id == "copy_id":
            self._copy_to_clipboard(entry.id)
        elif action_id == "show_metadata":
            try:
                text = artifact_metadata_text(role_of(entry.id), resolved)
            except Exception as exc:  # missing / malformed file -> friendly text, no crash
                text = f"Could not read metadata for {entry.id}:\n{exc}"
            self._show_metadata(entry.id, text)
        elif action_id == "reveal_file":
            self._reveal(reveal_target(base_dir, entry.path))
        elif action_id == "explore_signal":
            self._open_bank_explore(str(resolved), focus="explore")  # replaces (B7.8b-fix)
        elif action_id == "view_feature_distributions":
            self._open_bank_explore(str(resolved), focus="summary", replace=not self._loaded_banks)
        elif action_id == "view_ml_diagnostics":
            self._open_bank_explore(str(resolved), focus=None, replace=not self._loaded_banks)
            self._show_mode(1)  # ML-diagnostics mode
        elif action_id == "view_curves":
            self._load_training_run(str(resolved), entry.id)
            if any(name == entry.id for name, _ in self._loaded_runs):
                self._show_training_runs()
        elif action_id == "edit_spec":
            self._figure_view.load_spec(str(resolved))  # bank_paths are cross-scope (2c)
            self._show_mode(2)  # paper-figure-prep mode
        elif action_id == "view_figure":
            self._view_figure(resolved)
        elif action_id == "generate_figure":
            self._figure_view.generate_to_file(str(resolved))
            self._show_mode(2)
        elif action_id == "open_observation":
            self._open_observation(entry.id, resolved, scope_dirs=scope_dirs)
        elif action_id == "edit_observation":
            self._edit_observation(entry.id, resolved)

    def _refresh_figure_outputs(self) -> None:
        """Retune the figure menus to which images exist (on phase load + after a render)."""
        if self._phase_manifest is None:
            return
        self._phase_tree.set_figure_outputs(
            figure_output_exists_map(self._phase_manifest, self._phase_dir)
        )

    def _view_figure(self, spec_path: Path) -> None:
        """Open a figure's rendered image (View figure) in the OS default viewer."""
        try:
            spec = load_figure_spec(spec_path)
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"Could not read figure spec: {exc}")
            return
        out = figure_output_path(spec, spec_path)
        if not out.exists():
            self.statusBar().showMessage(f"Figure not generated yet: {out}")
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(out)))

    # -- save observation (File > Save observation, ADR-017 / B10) -------------

    def _save_observation(self) -> None:
        """Gather a title + description, then write an observation — into the loaded phase,
        or to the scratch folder when no phase is open (ADR-017 scratch mode)."""
        if self._explore_df is None or not len(self._explore_df.index):
            self.statusBar().showMessage("Load a bank before saving an observation.")
            return
        dialog = SaveObservationDialog(
            self,
            summary=self._observation_summary(),
            parent_observations=self._existing_observation_ids(),
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted.value:
            self._write_observation(dialog.title(), dialog.description(), dialog.parents())

    def _write_observation(self, title: str, description: str, parents: Sequence[str] = ()) -> None:
        """Capture the current state into an observation; save into the phase (indexed) or,
        with no phase open, to the scratch folder (the testable core)."""
        assert self._explore_df is not None
        spec = self._applied_spec
        shown = (
            self._explore_df[apply_filter(self._explore_df, spec)]
            if spec.conditions
            else self._explore_df
        )
        view_state, traces = capture_view_state(
            shown, filter_spec=spec, selected_row_ids=self._current_selection()
        )
        observation = build_observation(
            title=title,
            description=description,
            view_state=view_state,
            traces=traces,
            references=references_from(observations=parents),
        )
        if self._phase_manifest is not None:
            save_observation(observation, self._phase_dir)
            save_manifest(
                with_entry(self._phase_manifest, "observations", observation_entry(observation)),
                self._phase_dir,
            )
            self._reindex_phase_after_write()  # tree shows it; validation preserved
            self.statusBar().showMessage(f"Saved observation {observation.id}")
        else:
            save_observation(observation, self._scratch_dir)  # into the scratch area...
            save_manifest(  # ...and index it in the scratch manifest
                with_entry(
                    load_scratch(self._scratch_dir), "observations", observation_entry(observation)
                ),
                self._scratch_dir,
            )
            self._refresh_scratch()
            self.statusBar().showMessage(f"Saved observation {observation.id} to scratch")

    def _existing_observation_ids(self) -> list[str]:
        """Observation ids to offer as parent links — the loaded phase's, else scratch's."""
        source = (
            self._phase_manifest
            if self._phase_manifest is not None
            else load_scratch(self._scratch_dir)
        )
        return [entry.id for entry in (source.observations or ())]

    def _reindex_phase_after_write(self) -> None:
        """Reload the phase tree after a manifest write, re-running validation only if the
        phase had already been validated — so saving an observation restores (never wipes)
        the validation indicators, but doesn't fabricate them for an unvalidated phase.
        """
        was_validated = self._phase_validated
        self._load_phase_into_tree(str(self._phase_dir))  # rebuilds tree; resets the flag
        if was_validated:
            self._validate_phase()  # re-marks indicators + re-sets the flag

    def _open_observation(
        self, observation_id: str, path: Path, *, scope_dirs: Sequence[Path]
    ) -> None:
        """Reload the view a saved observation captured — its banks, filter, and selection.
        Banks resolve across ``scope_dirs`` (the phase, or scratch + phase for a scratch obs)."""
        try:
            observation = load_observation(path)
        except Exception as exc:  # missing / malformed file -> friendly text, no crash
            self.statusBar().showMessage(f"Could not open observation {observation_id}: {exc}")
            return
        view = observation.view_state
        if view is None:
            self.statusBar().showMessage(f"Observation {observation_id} saved no view to reload.")
            return
        bank_ids = [b.root for b in (view.banks_loaded or ())]
        loaded, missing = self._reload_banks(bank_ids, scope_dirs)
        if loaded == 0:
            self.statusBar().showMessage(
                f"Observation {observation_id}: none of its {len(bank_ids)} bank(s) are available."
            )
            return
        filter_note = self._restore_filter(view.filter)
        selected = self._restore_selection(list(observation.traces or []))
        self._show_mode(0)
        self._explore_view.show_explore()
        banks = f"{loaded} bank(s)" + (f" ({missing} missing)" if missing else "")
        self.statusBar().showMessage(
            f"Reloaded {observation_id}: {banks}, {filter_note}, {selected} trace(s) selected"
        )

    def _reload_banks(self, bank_ids: Sequence[str], scope_dirs: Sequence[Path]) -> tuple[int, int]:
        """Load the banks named by ``bank_ids`` into Flow A (first replaces, rest add),
        searching ``scope_dirs`` in order (a phase, or scratch + phase for a scratch obs).

        Resolution tolerates a bank whose stamped id has drifted from its manifest entry
        id (:func:`resolve_bank_paths`). Returns ``(loaded, missing)``.
        """
        paths, missing = resolve_bank_paths(scope_dirs, bank_ids)
        for i, bank_path in enumerate(paths):
            self._open_bank_explore(str(bank_path), focus=None, replace=(i == 0))
        return len(paths), len(missing)

    def _restore_filter(self, text: str | None) -> str:
        """Re-apply a saved filter string if it round-trips; else surface it for manual re-entry."""
        if not text:
            return "no filter"
        spec = parse_filter(text)
        if spec is None:  # a free-text filter this GUI can't reconstruct exactly
            return f"filter '{text}' not auto-applied"
        self._filter_panel.set_spec(spec)
        self._on_recalculate(spec)
        return f"filter: {text}"

    def _restore_selection(self, traces: Sequence[TraceRef]) -> int:
        """Select the observation's pinned traces (matched by bank id + index) in Flow A."""
        df = self._explore_df
        if df is None or not traces or "source" not in df.columns:
            return 0
        row_ids: list[int] = []
        for trace in traces:
            match = df[(df["source"] == trace.bank) & (df["trace_idx"] == trace.index)]
            row_ids.extend(int(row_id) for row_id in match[ROW_ID])
        if row_ids:
            self._explore_view.result_list.select_row_ids(row_ids)
        return len(row_ids)

    def _edit_observation(self, observation_id: str, path: Path) -> None:
        """Open an existing observation's prose + parent links for editing, then re-save it."""
        try:
            existing = load_observation(path)
        except Exception as exc:  # missing / malformed file -> friendly text, no crash
            self.statusBar().showMessage(f"Could not open observation {observation_id}: {exc}")
            return
        refs = existing.references
        selected = [o.root for o in (refs.observations or ())] if refs else []
        candidates = [obs for obs in self._existing_observation_ids() if obs != observation_id]
        dialog = SaveObservationDialog(
            self,
            observation_id=observation_id,
            title=existing.title,
            description=existing.description,
            parent_observations=candidates,
            selected_parents=selected,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted.value:
            self._apply_observation_edit(
                existing, dialog.title(), dialog.description(), dialog.parents()
            )

    def _apply_observation_edit(
        self, existing: Observation, title: str, description: str, parents: Sequence[str]
    ) -> None:
        """Write the edited observation back (same id/path/usage) + refresh the tree."""
        assert self._phase_manifest is not None
        entry = entries_by_id(self._phase_manifest)[existing.id]
        assert isinstance(entry, ObservationEntry)  # editing an observation -> ObservationEntry
        usage = entry.usage_tag.value if entry.usage_tag is not None else "exploratory"
        updated = update_observation(
            existing,
            title=title,
            description=description,
            references=references_from(observations=parents),
        )
        save_observation(updated, self._phase_dir)
        save_manifest(
            with_entry(
                self._phase_manifest,
                "observations",
                observation_entry(updated, usage_tag=usage, usage_notes=entry.usage_notes),
            ),
            self._phase_dir,
        )
        self._reindex_phase_after_write()  # validation indicators preserved across the edit
        self.statusBar().showMessage(f"Updated observation {updated.id}")

    def _save_figure_into_phase(self, spec: FigureSpec) -> None:
        """Write a Flow C figure spec into the loaded phase (indexed), or to the scratch
        folder when no phase is open (ADR-017 scratch mode)."""
        if self._phase_manifest is not None:
            save_figure_spec(spec, self._phase_dir)
            save_manifest(
                with_entry(self._phase_manifest, "figures", figure_entry(spec)), self._phase_dir
            )
            self._reindex_phase_after_write()  # tree shows the figure; validation preserved
            self.statusBar().showMessage(f"Saved figure {spec.id} into the phase")
        else:
            save_figure_spec(spec, self._scratch_dir)  # into the scratch area...
            save_manifest(  # ...and index it in the scratch manifest
                with_entry(load_scratch(self._scratch_dir), "figures", figure_entry(spec)),
                self._scratch_dir,
            )
            self._refresh_scratch()
            self.statusBar().showMessage(f"Saved figure {spec.id} to scratch")

    # -- scratch (save-with-no-phase staging area, B10e / B10h-2a) --------------

    def _refresh_scratch(self) -> None:
        """Reload the scratch manifest and paint the scratch tree; hide it when empty."""
        self._scratch_manifest = load_scratch(self._scratch_dir)
        groups = [g for g in phase_artifact_groups(self._scratch_manifest) if g.rows]  # compact
        self._scratch_tree.set_groups(groups)
        self._paint_scratch(validate=self._scratch_validated)  # keep a prior validation
        self._scratch_pane.setVisible(bool(groups))
        self._figure_view.set_bank_paths(self._all_bank_paths())  # scratch banks feed Flow C

    def _paint_scratch(self, *, validate: bool) -> dict[str, StatusReport]:
        """Paint the scratch tree. A scratch item resolves its dependencies cross-scope —
        against scratch plus the loaded phase's ids (2c-A) — so a staged observation whose
        banks sit in scratch or the phase reads OK, and one whose banks are nowhere is
        flagged unresolved."""
        phase_ids = manifest_ids(self._phase_manifest) if self._phase_manifest is not None else None
        report = phase_status_report(
            self._scratch_manifest, self._scratch_dir, validate=validate, extra_ids=phase_ids
        )
        self._scratch_tree.set_statuses(
            {i: r.status for i, r in report.items()},
            {i: r.detail for i, r in report.items()},
        )
        return report

    def _on_scratch_action(self, action_id: str, artifact_id: str) -> None:
        """Run a scratch-tree action: Promote / Delete, else the shared artifact actions
        (viewers + info) resolved cross-scope against scratch + the loaded phase (2c)."""
        entry = entries_by_id(self._scratch_manifest).get(artifact_id)
        if entry is None:
            return
        if action_id == "promote_scratch":
            self._promote_scratch(artifact_id)
            return
        if action_id == "delete_scratch":
            self._delete_scratch(artifact_id)
            return
        scratch = Path(self._scratch_dir)
        scope = [scratch, self._phase_dir] if self._phase_manifest is not None else [scratch]
        self._run_artifact_action(action_id, entry, base_dir=scratch, scope_dirs=scope)

    def _promote_scratch(self, artifact_id: str) -> None:
        """Move a scratch artifact into the loaded phase (Promote to phase).

        An authored artifact (observation / figure) has its file re-written into the phase
        folder; a producer artifact is a path pointer, so it is simply re-indexed (its file
        stays put). Either way the entry leaves the scratch manifest.
        """
        if self._phase_manifest is None:
            self.statusBar().showMessage("Open a phase (File ▸ Open phase) to promote into it.")
            return
        entry = entries_by_id(self._scratch_manifest).get(artifact_id)
        if entry is None:
            return
        role = role_of(artifact_id)
        section = manifest_section(artifact_id)
        authored_file: Path | None = None  # set for authored artifacts (their file moves)
        try:
            if role is Role.observation:
                authored_file = Path(self._scratch_dir) / entry.path
                observation = load_observation(authored_file)
                save_observation(observation, self._phase_dir)
                phase = with_entry(self._phase_manifest, section, observation_entry(observation))
            elif role is Role.figure:
                authored_file = Path(self._scratch_dir) / entry.path
                spec = load_figure_spec(authored_file)
                save_figure_spec(spec, self._phase_dir)
                phase = with_entry(self._phase_manifest, section, figure_entry(spec))
            else:  # a producer pointer — re-index the same entry, no file move
                phase = with_entry(self._phase_manifest, section, entry)
        except Exception as exc:  # unreadable / invalid scratch file -> status, keep it in scratch
            self.statusBar().showMessage(f"Could not promote {artifact_id}: {exc}")
            return
        save_manifest(phase, self._phase_dir)
        save_manifest(remove_entry(self._scratch_manifest, section, artifact_id), self._scratch_dir)
        if authored_file is not None:
            authored_file.unlink(missing_ok=True)  # the authored copy moved into the phase
        self._reindex_phase_after_write()
        self._refresh_scratch()
        self.statusBar().showMessage(f"Promoted {artifact_id} into the phase")

    def _delete_scratch(self, artifact_id: str) -> None:
        """Remove a scratch artifact — its entry, plus its file for authored artifacts."""
        entry = entries_by_id(self._scratch_manifest).get(artifact_id)
        if entry is None:
            return
        if role_of(artifact_id) in (Role.observation, Role.figure):
            (Path(self._scratch_dir) / entry.path).unlink(missing_ok=True)  # authored file
        section = manifest_section(artifact_id)
        save_manifest(remove_entry(self._scratch_manifest, section, artifact_id), self._scratch_dir)
        self._refresh_scratch()
        self.statusBar().showMessage(f"Deleted {artifact_id} from scratch")

    def _current_selection(self) -> list[int]:
        """The selected trace row_ids in the active flow (empty for Flow C / figure prep)."""
        mode = self._modes_stack.currentIndex()
        if mode == 0:
            return self._explore_view.result_list.selected_row_ids()
        if mode == 1:
            return self._diagnostics_view.result_list.selected_row_ids()
        return []

    def _observation_summary(self) -> str:
        assert self._explore_df is not None
        banks = self._explore_df["source"].nunique() if "source" in self._explore_df.columns else 0
        return (
            f"Will capture: {banks} bank(s), {describe_filter(self._applied_spec) or 'no filter'}, "
            f"{len(self._current_selection())} trace(s) selected."
        )

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
