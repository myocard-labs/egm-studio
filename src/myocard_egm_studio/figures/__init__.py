"""Headless figure-render layer — the thin dispatch over ``charts/matplotlib``.

``render(spec, *, data)`` is the single public entry point (importable from
notebooks / CI, and wrapped by the ``egm-studio-render`` CLI and — later — the
GUI's figure-prep view). It looks up the spec's recipe, draws it from the
prepared ``data``, and writes the file. No PySide6, no pyqtgraph: this path
runs without a display. [ADR-005, ADR-015, architecture.md "The three-layer
rendering split"]

The :mod:`.loaders` step turns a spec's bank ids into that prepared ``data``.
Block 7 resolves the ids through the phase manifest; until then callers supply
a ``{bank_id: path}`` map by hand (the CLI's ``--bank`` / ``--banks`` flags).
The bank -> recipe-input adapters (e.g. :func:`prediction_group_from_bank`) are
permanent and reused once the manifest lands.
"""

from __future__ import annotations

from myocard_egm_studio.figures.loaders import (
    BankPaths,
    LoaderNotRegisteredError,
    UnmappedBankIdError,
    load_prediction_groups,
    prediction_group_from_bank,
    resolve_recipe_data,
)
from myocard_egm_studio.figures.render import (
    FigureDataNotLoadedError,
    UnknownRecipeError,
    render,
)

__all__ = [
    "BankPaths",
    "FigureDataNotLoadedError",
    "LoaderNotRegisteredError",
    "UnknownRecipeError",
    "UnmappedBankIdError",
    "load_prediction_groups",
    "prediction_group_from_bank",
    "render",
    "resolve_recipe_data",
]
