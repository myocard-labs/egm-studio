"""Pure data computation for egm-studio — NO rendering, NO Qt.

The bottom layer of the three-layer rendering split (``analysis`` →
``charts`` → ``figures`` / ``gui``). Everything here is a pure function over
numpy / pandas / scipy / egm-features: statistical primitives, group
aggregations, and similarity scaffolding. Both rendering backends
(``charts/matplotlib`` for static export, ``charts/pyqtgraph`` for the GUI)
consume these so no chart's data prep is computed — or duplicated — twice.

Hard import rule (see ``project/architecture.md`` "Import boundaries"):
``analysis`` MUST NOT import matplotlib, pyqtgraph, or PySide6. Keeping that
boundary is what lets the headless figure path run in CI / notebooks without
a display.

Submodules (one per analytical concern):

- :mod:`.distributions` — CDFs, KS / Wasserstein distance, histogram, KDE.
- :mod:`.aggregation` — per-feature distribution distance between groups +
  the single-scalar aggregate roll-up.
- :mod:`.similarity` — per-feature nearest-trace lookup (ADR-020); the
  richer nearest-correct-pair / within-class-neighborhood diagnostics land
  in Block 8.
"""

from __future__ import annotations
