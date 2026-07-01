"""Time-scale slider bound to a TraceContainer's shared X-axis (Block 5.2).

A discoverability aid for time-axis navigation — the traces also pan / zoom with
the mouse. The slider sets the visible time-window *width*, and mouse pan / zoom
updates the slider back; both drive the same shared X range. Reentrancy between
the two directions is guarded by ``_syncing``.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.gui.widgets.trace import TraceContainer

_SLIDER_MAX = 100
_SLIDER_MIN = 2  # smallest visible window = 2% of the full range


class TimeScaleWidget(QtWidgets.QWidget):
    """A 'time scale' slider that sets the visible X-window width of a TraceContainer."""

    def __init__(self) -> None:
        super().__init__()
        self._container: TraceContainer | None = None
        self._bounds = (0.0, 1.0)
        self._syncing = False

        self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._slider.setRange(_SLIDER_MIN, _SLIDER_MAX)
        self._slider.setValue(_SLIDER_MAX)
        self._slider.valueChanged.connect(self._on_slider)
        self._readout = QtWidgets.QLabel()

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        row.addWidget(QtWidgets.QLabel("Time scale"))
        row.addWidget(self._slider, 1)
        row.addWidget(self._readout)

    def bind(self, container: TraceContainer) -> None:
        """Bind to ``container``'s shared X-axis (two-way), starting at the full view."""
        self._container = container
        self._bounds = container.x_data_bounds()
        viewbox = container.shared_viewbox()
        if viewbox is not None:
            viewbox.sigXRangeChanged.connect(self._on_range)
        lo, hi = self._bounds
        self._syncing = True
        try:
            container.set_x_range(lo, hi)
            self._slider.setValue(_SLIDER_MAX)
            self._update_readout(hi - lo)
        finally:
            self._syncing = False

    def _full_width(self) -> float:
        lo, hi = self._bounds
        return max(hi - lo, 1e-9)

    def _on_slider(self, value: int) -> None:
        if self._syncing or self._container is None:
            return
        viewbox = self._container.shared_viewbox()
        if viewbox is None:
            return
        self._syncing = True
        try:
            width = (value / _SLIDER_MAX) * self._full_width()
            cur_lo, cur_hi = viewbox.viewRange()[0]
            center = (cur_lo + cur_hi) / 2.0
            lo, hi = self._bounds
            new_lo = max(lo, center - width / 2.0)
            new_hi = min(hi, new_lo + width)
            new_lo = max(lo, new_hi - width)
            self._container.set_x_range(new_lo, new_hi)
            self._update_readout(new_hi - new_lo)
        finally:
            self._syncing = False

    def _on_range(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._sync_from_range()
        finally:
            self._syncing = False

    def _sync_from_range(self) -> None:
        if self._container is None:
            return
        viewbox = self._container.shared_viewbox()
        if viewbox is None:
            return
        lo, hi = viewbox.viewRange()[0]
        width = hi - lo
        value = round((width / self._full_width()) * _SLIDER_MAX)
        self._slider.setValue(max(_SLIDER_MIN, min(_SLIDER_MAX, value)))
        self._update_readout(width)

    def _update_readout(self, width: float) -> None:
        self._readout.setText(f"{width:.0f} ms")
