"""Chart-building primitives — dual rendering backends.

``charts/matplotlib/`` renders publication-quality static figures (Agg,
headless); ``charts/pyqtgraph/`` (Block 5) renders the interactive,
GUI-embedded variants. Both backends consume :mod:`..analysis` for data prep so
a chart's computation lives once and is presented twice. Neither backend imports
the other's plotting library, and neither imports PySide6. [architecture.md
"Import boundaries"]
"""

from __future__ import annotations
