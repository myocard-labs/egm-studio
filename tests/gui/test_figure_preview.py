"""pytest-qt tests for the Flow C figure-preview panel (gui/widgets/figure_preview, B9)."""

from __future__ import annotations

import io

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import FigurePreview


def _png_bytes() -> bytes:
    fig = Figure()
    FigureCanvasAgg(fig)
    fig.add_subplot(1, 1, 1).plot([0, 1, 2], [0, 1, 0])
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=100)
    return buffer.getvalue()


def test_starts_in_the_empty_prompt(qtbot: QtBot) -> None:
    view = FigurePreview()
    qtbot.addWidget(view)
    assert not view.has_image
    assert "preview" in view._label.text().lower()


def test_show_png_displays_a_scaled_pixmap(qtbot: QtBot) -> None:
    view = FigurePreview()
    qtbot.addWidget(view)
    view.resize(400, 300)
    view.show_png(_png_bytes())
    assert view.has_image
    pixmap = view._label.pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() <= view._label.width()  # scaled to fit, aspect preserved


def test_show_error_replaces_the_image_with_text(qtbot: QtBot) -> None:
    view = FigurePreview()
    qtbot.addWidget(view)
    view.show_png(_png_bytes())
    view.show_error("recipe blew up")
    assert not view.has_image
    assert view._label.text() == "recipe blew up"


def test_clear_returns_to_the_prompt(qtbot: QtBot) -> None:
    view = FigurePreview()
    qtbot.addWidget(view)
    view.show_png(_png_bytes())
    view.clear()
    assert not view.has_image
    assert "preview" in view._label.text().lower()
