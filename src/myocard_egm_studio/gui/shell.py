"""The egm-studio main window — the ADR-025 layout shell.

ADR-025: a fixed top menu / header bar over a resizable-column work area flanked by
collapsible left and right sidebars, every separator draggable. Each sidebar
collapses to a thin Activity-Bar-style icon strip and expands again from it; the
header carries the three-mode segmented control. The theme (ADR-012) persists via
:mod:`..preferences`. Real content for each region arrives in Blocks 5+.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.gui.preferences import load_theme, save_theme
from myocard_egm_studio.gui.sources import load_bank
from myocard_egm_studio.gui.theme import DEFAULT_THEME, THEME_NAMES, apply_theme, plot_palette
from myocard_egm_studio.gui.widgets import BankTrace, TraceContainer, TraceData, TraceSelector

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
_MAX_TRACES = 8  # cap on traces stacked at once (full selection is Block 7)
_DEFAULT_SHOWN = 3  # traces auto-selected when a bank is first opened

_Side = Literal["left", "right"]
# Chevrons: the panel's collapse button points at the edge it hides toward; the
# strip's expand button points back toward the centre.
_COLLAPSE_GLYPH: dict[_Side, str] = {"left": "◂", "right": "▸"}
_EXPAND_GLYPH: dict[_Side, str] = {"left": "▸", "right": "◂"}


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


class _WorkArea(QtWidgets.QWidget):
    """The main column's swappable content host — placeholder until a bank is opened."""

    def __init__(self) -> None:
        super().__init__()
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._content: QtWidgets.QWidget = _Placeholder(
            "Work area", "Open a bank (File ▸ Open bank…) to view its traces"
        )
        self._layout.addWidget(self._content)

    def set_content(self, widget: QtWidgets.QWidget) -> None:
        """Replace the current content widget, deleting the old one."""
        self._layout.removeWidget(self._content)
        self._content.deleteLater()
        self._content = widget
        self._layout.addWidget(widget)

    @property
    def content(self) -> QtWidgets.QWidget:
        return self._content


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
        content = self._work_area.content
        if isinstance(content, TraceContainer):
            content.restyle(plot_palette(name))

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
        """Mode switch is a scaffold for now — reflect the choice in the status bar."""
        self.statusBar().showMessage(f"Mode: {_MODES[index]}")

    def _build_columns(self) -> QtWidgets.QSplitter:
        """The draggable left | main | right work area (ADR-025)."""
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setObjectName("columnSplitter")
        splitter.setChildrenCollapsible(False)

        self._left_sidebar = CollapsibleSidebar(
            title="Filters", subtitle="Open a bank to list its traces", side="left"
        )
        self._left_sidebar.setObjectName("leftSidebar")
        self._left_sidebar.toggleRequested.connect(lambda: self._toggle_sidebar("left"))
        self._trace_selector = TraceSelector()
        self._trace_selector.selectionChanged.connect(self._on_trace_selection)
        self._left_sidebar.set_body(self._trace_selector)

        self._work_area = _WorkArea()
        self._work_area.setMinimumWidth(_MAIN_MIN_W)

        self._right_sidebar = CollapsibleSidebar(
            title="Phase tree", subtitle="Saved observations & artifacts (Block 6+)", side="right"
        )
        self._right_sidebar.setObjectName("rightSidebar")
        self._right_sidebar.toggleRequested.connect(lambda: self._toggle_sidebar("right"))

        splitter.addWidget(self._left_sidebar)
        splitter.addWidget(self._work_area)
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
        """File > Open bank…: pick an HDF5 bank and show its first traces."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open bank", "", "EGM banks (*.h5 *.hdf5);;All files (*)"
        )
        if path:
            self._load_bank_into_view(path)

    def _load_bank_into_view(self, path: str) -> None:
        """Load a bank, list its traces in the selector, and show the first few (testable)."""
        try:
            loaded = load_bank(path)
        except Exception as exc:  # surface any read / validation error to the status bar
            self.statusBar().showMessage(f"Could not open bank: {exc}")
            return
        if not loaded.traces:
            self.statusBar().showMessage("That bank has no traces to display.")
            return
        self._bank_name = Path(path).name
        self._trace_selector.set_bank(loaded)
        self.statusBar().showMessage(
            f"Loaded {self._bank_name} — {len(loaded.traces)} traces; filter / select to view"
        )
        self._trace_selector.select_first(min(_DEFAULT_SHOWN, len(loaded.traces)))

    def _show_traces(self, traces: list[TraceData], *, source: str) -> None:
        """Put a TraceContainer for ``traces`` in the work area + note it in the status bar."""
        self._work_area.set_content(
            TraceContainer(traces, palette=plot_palette(self._current_theme))
        )
        self.statusBar().showMessage(f"Loaded {source} — showing {len(traces)} trace(s)")

    def _on_trace_selection(self, rows: list[BankTrace]) -> None:
        """Show the selected traces (capped at _MAX_TRACES) in the work area."""
        if not rows:
            return
        shown = rows[:_MAX_TRACES]
        self._show_traces(
            [bt.data for bt in shown], source=f"{self._bank_name} · {len(shown)} selected"
        )
