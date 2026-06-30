"""Shared typed accessors over a FigureSpec's loose ``inputs`` / ``styling`` dicts.

Some scalar figure_spec fields are read in more than one place and must be read
*identically* there — first among them ``inputs.positive_label``, which the
predictions-bank loader and the ROC / calibration recipes have to agree on (the
loader scores ``PredictionGroup.probs`` as P(that class); the recipes binarize
the truth labels against it). Parsing each such field once here keeps the call
sites in lockstep.

Lives in ``charts/matplotlib`` so both the recipes (here) and the loader
(``figures/loaders``, which already imports this package) can reach it without
crossing an import boundary — the same placement rationale as ``selection.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

__all__ = ["positive_label"]


def positive_label(spec: FigureSpec) -> int:
    """``inputs.positive_label`` (default 1) — the binary positive class.

    The predictions-bank loader scores ``PredictionGroup.probs`` as P(this class)
    and the ROC / calibration recipes binarize their truth labels against it, so
    the two must read the same value — hence one reader. The default of 1 is the
    fibrotic / positive class of the binary v1 model; a multi-class spec overrides
    it per target class.
    """
    extra = (spec.inputs.model_extra if spec.inputs else None) or {}
    return int(extra.get("positive_label", 1))
