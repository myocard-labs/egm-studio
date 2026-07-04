"""The egm-studio main window — the ADR-025 layout shell.

ADR-025: a fixed top menu / header bar over a resizable-column work area flanked by
collapsible left and right sidebars, every separator draggable. Each sidebar
collapses to a thin Activity-Bar-style icon strip and expands again from it; the
header carries the three-mode segmented control. The theme (ADR-012) persists via
:mod:`..preferences`. Real content for each region arrives in Blocks 5+.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

import pandas as pd
from myocard_egm_contracts import role_of
from myocard_egm_data.phases import PhaseManifest, load_phase_dir
from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.gui.preferences import load_theme, save_theme
from myocard_egm_studio.gui.sources import load_exploration
from myocard_egm_studio.gui.theme import (
    DEFAULT_THEME,
    THEME_NAMES,
    apply_theme,
    chart_style,
    plot_palette,
)
from myocard_egm_studio.gui.views import SignalExplorationView
from myocard_egm_studio.gui.widgets import FilterPanel, PhaseTree, TraceData
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

_Side = Literal["left", "right"]
# Chevrons: the panel's collapse button points at the edge it hides toward; the
# strip's expand button points back toward the centre.
_COLLAPSE_GLYPH: dict[_Side, str] = {"left": "◂", "right": "▸"}
_EXPAND_GLYPH: dict[_Side, str] = {"left": "▸", "right": "◂"}


class _LoadCancelled(Exception):
    """Raised by the load progress callback when the user hits Cancel mid-load."""


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


class MainWindow(QtWidgets.QMainWindow):
    """Top-level shell: menu bar + header (mode switch) + collapsible column work area."""

    def __init__(self) -> None:
        super().__init__()
        self._bank_name = ""
        self._phase_manifest: PhaseManifest | None = None
        self._phase_dir = Path()
        self._last_metadata_text = ""  # last "Show metadata" text (for tests)
        self._metadata_dialog: QtWidgets.QDialog | None = None
        self._explore_df: pd.DataFrame | None = None  # the loaded bank's view-model table
        self.setWindowTitle(_WINDOW_TITLE)
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self._build_menu_bar()
        self._build_body()
        self.statusBar().showMessage("Ready")

    # -- menu bar -------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        open_action = file_menu.addAction("&Open bank…")
        open_action.setObjectName("openBank")
        open_action.triggered.connect(self._open_bank)
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
            title="Filters", subtitle="Open a bank to filter its traces", side="left"
        )
        self._left_sidebar.setObjectName("leftSidebar")
        self._left_sidebar.toggleRequested.connect(lambda: self._toggle_sidebar("left"))
        self._filter_panel = FilterPanel()
        self._filter_panel.filterChanged.connect(self._on_filter_changed)
        self._left_sidebar.set_body(self._filter_panel)

        self._explore_view = SignalExplorationView(
            plot_palette(self._current_theme), chart_style(self._current_theme)
        )
        self._modes_stack = QtWidgets.QStackedWidget()
        self._modes_stack.setMinimumWidth(_MAIN_MIN_W)
        self._modes_stack.addWidget(self._explore_view)  # 0 — signal exploration
        self._modes_stack.addWidget(_Placeholder("ML diagnostics", "Flow B — lands in Block 8"))
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

    # -- open bank (direct load; File > Open bank) -----------------------------

    def _open_bank(self) -> None:
        """File > Open bank…: pick an HDF5 bank and open it in Signal exploration."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open bank", "", "EGM banks (*.h5 *.hdf5);;All files (*)"
        )
        if path:
            self._open_bank_explore(path)

    def _open_bank_explore(
        self, path: str, *, focus: Literal["summary", "explore"] = "summary"
    ) -> None:
        """Load a bank as the view-model table + traces; feed the filter + Flow A view.

        ``focus`` picks the sub-tab to land on: the Summary landing by default
        (File ▸ Open bank, "View feature distributions"), or "explore" straight to
        the result list ("Explore signal").

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
            return
        except Exception as exc:  # surface any read / validation error to the status bar
            self.statusBar().showMessage(f"Could not open bank: {exc}")
            return
        finally:
            dialog.close()

        self._on_bank_loaded(path, frame, traces, focus=focus)

    def _on_bank_loaded(
        self,
        path: str,
        frame: pd.DataFrame,
        traces: list[TraceData],
        *,
        focus: Literal["summary", "explore"] = "summary",
    ) -> None:
        """Populate the filter + Flow A view from a freshly loaded bank."""
        if frame.empty:
            self.statusBar().showMessage("That bank has no traces to display.")
            return
        self._bank_name = Path(path).name
        # Route even a single bank through the combiner so the GUI always keys on
        # row_id (the B7.8 global row key); multi-bank loading joins here in B7.8b.
        combined = combine_view_models([frame])
        self._explore_df = combined
        self._explore_view.set_traces(traces)
        self._explore_view.set_summary(combined)  # full-bank stats + grid; lands on Summary
        # set_columns emits filterChanged -> _on_filter_changed, which populates the list.
        self._filter_panel.set_columns(filter_columns(combined))
        self._show_mode(0)
        if focus == "explore":
            self._explore_view.show_explore()
        self.statusBar().showMessage(
            f"Loaded {self._bank_name} — {len(frame.index)} trace(s); filter or sort, then select"
        )

    def _on_filter_changed(self, spec: FilterSpec) -> None:
        """Re-apply the filter to the loaded frame and refresh the result list."""
        if self._explore_df is None:
            return
        filtered = self._explore_df[apply_filter(self._explore_df, spec)]
        self._explore_view.set_results(filtered)
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
        elif action_id in ("explore_signal", "view_feature_distributions"):
            focus: Literal["summary", "explore"] = (
                "explore" if action_id == "explore_signal" else "summary"
            )
            self._open_bank_explore(str(self._phase_dir / entry.path), focus=focus)

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
