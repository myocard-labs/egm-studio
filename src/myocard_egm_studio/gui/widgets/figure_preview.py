"""Figure-preview panel — shows a rendered figure PNG, scaled to fit (Block 9).

The right half of the Flow C figure-prep view. It is deliberately dumb: it holds a
PNG (the bytes :func:`figures.preview.preview_png` returns for the current spec) and
paints it into a label, scaled to fit the panel with the aspect ratio preserved. All
the fidelity lives upstream in the shared render pipeline; this widget only displays.

Because the preview is a raster of the real matplotlib figure, what the user sees here
is what the exported PDF will contain (WYSIWYG, ADR-019). An empty state prompts until
the first render; :meth:`show_error` surfaces a render failure as text instead of a
stale image.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

_EMPTY_PROMPT = "Edit the spec on the left to preview the figure."

__all__ = ["FigurePreview"]


class FigurePreview(QtWidgets.QWidget):
    """Displays a figure PNG scaled to fit, preserving aspect ratio."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("figurePreview")
        self._source: QtGui.QPixmap | None = None  # the full-res render; None = empty state

        self._label = QtWidgets.QLabel(_EMPTY_PROMPT)
        self._label.setObjectName("figurePreviewLabel")
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setMinimumSize(240, 180)  # keep a usable canvas when the panel is small

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def show_png(self, data: bytes) -> None:
        """Display the figure PNG in ``data``, scaled to the current panel size."""
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(data)  # PNG is auto-detected from the header
        self._source = pixmap
        self._rescale()

    def show_error(self, message: str) -> None:
        """Clear the image and show ``message`` (a render failure) in its place."""
        self._source = None
        self._label.setText(message)

    def clear(self) -> None:
        """Return to the empty prompt (no spec / no preview yet)."""
        self._source = None
        self._label.setText(_EMPTY_PROMPT)

    @property
    def has_image(self) -> bool:
        return self._source is not None

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # Qt override (camelCase)
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source is None:
            return
        self._label.setPixmap(
            self._source.scaled(
                self._label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )
