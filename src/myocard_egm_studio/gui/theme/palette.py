"""Colour + size tokens for each egm-studio theme (ADR-012).

A ``Palette`` is the full set of tokens the QSS template needs; ``DARK`` (default),
``LIGHT``, and ``VIBRANT`` are the shipped instances. Keeping every token in one
frozen dataclass means the template can't reference a colour a theme forgot to
define.

DARK and LIGHT are the restrained, professional pair; VIBRANT is a
programmer-editor-style dark theme (bright green headings, cyan accents, purple
highlights) for users who prefer that look. The ``title`` and ``accent_alt``
tokens let VIBRANT recolour headings + the mode strip while the restrained pair
map them back to plain text / muted text, so DARK and LIGHT are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: The user-facing theme identifier (also the View > Theme label, capitalised).
ThemeName = Literal["dark", "light", "vibrant"]

# Typography scale (px) — ADR-012's "small set of font sizes".
FONT_PT_BODY = 13
FONT_PT_TITLE = 16
FONT_PT_SMALL = 11


@dataclass(frozen=True)
class Palette:
    """Named colours for one theme; every value is a QSS-ready colour string."""

    window_bg: str
    surface: str
    border: str
    text: str
    text_muted: str
    title: str  # heading colour (app + panel titles); == text in the restrained pair
    accent: str  # interactive highlight (menu selection)
    accent_alt: str  # secondary accent (mode strip); == text_muted in the restrained pair
    header_bg: str


#: Default theme — a deep neutral slate, restrained blue accent (a scientific
#: tool, not a dashboard). Kept close to VS Code / clinical-viewer dark greys.
DARK = Palette(
    window_bg="#1e2127",
    surface="#262a31",
    border="#3a404a",
    text="#e6e9ef",
    text_muted="#9aa3b2",
    title="#e6e9ef",
    accent="#5aa0f2",
    accent_alt="#9aa3b2",
    header_bg="#22262d",
)

#: Light alternative — same structure, high-contrast on near-white surfaces.
LIGHT = Palette(
    window_bg="#f4f5f7",
    surface="#ffffff",
    border="#d3d7de",
    text="#1c1f26",
    text_muted="#5c6470",
    title="#1c1f26",
    accent="#2f6fe0",
    accent_alt="#5c6470",
    header_bg="#e9ecf1",
)

#: Vibrant dark — programmer-editor palette (Tokyo-Night-ish): bright green
#: headings, cyan mode strip, purple selection, luminous body text.
VIBRANT = Palette(
    window_bg="#1a1b26",
    surface="#24283b",
    border="#414868",
    text="#c0caf5",
    text_muted="#9aa5ce",
    title="#9ece6a",
    accent="#bb9af7",
    accent_alt="#7dcfff",
    header_bg="#16161e",
)

PALETTES: dict[ThemeName, Palette] = {"dark": DARK, "light": LIGHT, "vibrant": VIBRANT}
