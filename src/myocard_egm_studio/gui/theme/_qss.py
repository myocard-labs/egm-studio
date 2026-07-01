"""The shared QSS template + builder (ADR-012).

One ``string.Template`` styles all themes; :func:`build_stylesheet` substitutes a
:class:`~.palette.Palette`'s tokens (``$window_bg`` etc.) plus the typography
scale. ``string.Template`` (not ``str.format``) is used so QSS's own ``{ }``
blocks need no escaping — only ``$name`` placeholders are substituted.
"""

from __future__ import annotations

from string import Template

from myocard_egm_studio.gui.theme.palette import (
    FONT_PT_BODY,
    FONT_PT_SMALL,
    FONT_PT_TITLE,
    Palette,
)

_TEMPLATE = Template(
    """
QWidget {
    background-color: $window_bg;
    color: $text;
    font-size: ${font_body}px;
}
QFrame#headerBar {
    background-color: $header_bg;
    border-bottom: 1px solid $border;
}
QLabel#appTitle {
    font-size: ${font_title}px;
    font-weight: 600;
    color: $title;
    background: transparent;
}
QPushButton#modeButton {
    background: transparent;
    color: $text_muted;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 12px;
}
QPushButton#modeButton:hover {
    color: $accent_alt;
}
QPushButton#modeButton:checked {
    color: $accent;
    background-color: $surface;
    border: 1px solid $accent;
}
QFrame#regionPanel {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 4px;
}
QLabel#sidebarTitle {
    font-size: ${font_body}px;
    font-weight: 600;
    color: $title;
    background: transparent;
}
QFrame#activityStrip {
    background-color: $header_bg;
    border: 1px solid $border;
    border-radius: 4px;
}
QToolButton#sidebarToggle {
    background: transparent;
    color: $text_muted;
    border: none;
    font-size: ${font_title}px;
    padding: 2px 4px;
}
QToolButton#sidebarToggle:hover {
    color: $accent;
}
QLabel#placeholderTitle {
    font-size: ${font_title}px;
    font-weight: 600;
    color: $title;
    background: transparent;
}
QLabel#placeholderSubtitle {
    font-size: ${font_small}px;
    color: $text_muted;
    background: transparent;
}
QMenuBar {
    background-color: $header_bg;
    color: $text;
}
QMenuBar::item:selected {
    background-color: $accent;
    color: $window_bg;
}
QMenu {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
}
QMenu::item:selected {
    background-color: $accent;
    color: $window_bg;
}
QTableView {
    background-color: $surface;
    color: $text;
    gridline-color: $border;
    border: 1px solid $border;
    selection-background-color: $accent;
    selection-color: $window_bg;
}
QHeaderView::section {
    background-color: $header_bg;
    color: $text_muted;
    border: none;
    padding: 3px 6px;
}
QSplitter::handle {
    background-color: $border;
}
QStatusBar {
    background-color: $header_bg;
    color: $text_muted;
}
"""
)


def build_stylesheet(palette: Palette) -> str:
    """Return the full QSS for one palette (used by ``theme.apply_theme``)."""
    return _TEMPLATE.substitute(
        window_bg=palette.window_bg,
        surface=palette.surface,
        border=palette.border,
        text=palette.text,
        text_muted=palette.text_muted,
        title=palette.title,
        accent=palette.accent,
        accent_alt=palette.accent_alt,
        header_bg=palette.header_bg,
        font_body=FONT_PT_BODY,
        font_title=FONT_PT_TITLE,
        font_small=FONT_PT_SMALL,
    )
