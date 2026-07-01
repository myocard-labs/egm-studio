"""TraceView — a TraceContainer stacked over its time-scale slider (Block 5.2).

The work area holds one of these per open selection: the stacked traces plus a
time-scale slider bound to their shared X-axis. ``restyle`` forwards a theme change
to the container.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtWidgets

from myocard_egm_studio.gui.theme import PlotPalette
from myocard_egm_studio.gui.widgets.time_scale import TimeScaleWidget
from myocard_egm_studio.gui.widgets.trace import TraceContainer, TraceData


class TraceView(QtWidgets.QWidget):
    """The stacked traces + a time-scale slider bound to their shared X-axis."""

    def __init__(self, traces: Sequence[TraceData], *, palette: PlotPalette | None = None) -> None:
        super().__init__()
        self._container = TraceContainer(traces, palette=palette)
        self._time_scale = TimeScaleWidget()
        self._time_scale.bind(self._container)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._container, 1)
        layout.addWidget(self._time_scale)

    @property
    def container(self) -> TraceContainer:
        return self._container

    def restyle(self, palette: PlotPalette) -> None:
        """Forward a theme change to the stacked traces."""
        self._container.restyle(palette)
