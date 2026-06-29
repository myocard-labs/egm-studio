"""Figure-data loaders — turn a spec's bank ids into prepared recipe inputs.

This is the renderer's *loading step*: the bridge between egm-data banks on disk
and the in-memory inputs that recipes draw (``charts/matplotlib/inputs``). A
recipe stays pure plotting; this module does the I/O + adaptation.

Block 7 will resolve a spec's ``inputs.groups`` bank ids to file paths through
the phase manifest. Until then the caller supplies the id->path map by hand (the
``egm-studio-render --bank ID=PATH`` / ``--banks map.json`` flags), which is a
proto-manifest: the same ``{bank_id: path}`` resolution the manifest reader will
do later. The *adapter* below (bank -> PredictionGroup) is permanent and reused
unchanged once the manifest lands; only the source of the path map changes.

Loaders register per recipe (mirroring the ``charts/matplotlib`` recipe
registry): :func:`resolve_recipe_data` dispatches on ``spec.recipe`` into
:data:`LOADERS`. Today only ``prediction-histogram`` has a loader; more land as
recipes gain real-data paths.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from myocard_egm_data.banks import load_classifier_bank

from myocard_egm_studio.charts.matplotlib.inputs import PredictionGroup

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec
    from myocard_egm_data.banks import ClassifierBank

#: A ``{bank_id: path}`` map (the proto-manifest the CLI builds from --bank/--banks).
BankPaths = Mapping[str, str | Path]

#: A figure-data loader: resolves a spec + a ``{bank_id: path}`` map into the
#: prepared input its recipe expects (recipe-specific, hence ``Any``).
RecipeLoaderFn = Callable[["FigureSpec", BankPaths], Any]

#: Recipe name (the ``figure_spec.recipe`` value) -> its data loader.
LOADERS: dict[str, RecipeLoaderFn] = {}

__all__ = [
    "LOADERS",
    "BankPaths",
    "LoaderNotRegisteredError",
    "RecipeLoaderFn",
    "UnmappedBankIdError",
    "load_group_banks",
    "load_prediction_groups",
    "prediction_group_from_bank",
    "register_loader",
    "resolve_recipe_data",
]


class LoaderNotRegisteredError(LookupError):
    """No data loader is wired for ``spec.recipe`` yet.

    A recipe can render (it's in the recipe registry) before it has a loader
    that builds its input from banks. Carries the sorted list of recipes that
    *do* have loaders so the CLI can say what ``--bank`` loading supports today.
    """

    def __init__(self, recipe: str, known: list[str]) -> None:
        self.recipe = recipe
        self.known = known
        hint = ", ".join(known) if known else "(none yet)"
        super().__init__(
            f"no figure-data loader registered for recipe {recipe!r}; loaders exist for: {hint}."
        )


class UnmappedBankIdError(ValueError):
    """A spec group's ``bank_id`` has no entry in the supplied path map.

    Lists the unmapped ids + the ids that *were* provided so the caller can fix
    the ``--bank`` / ``--banks`` arguments.
    """

    def __init__(self, missing: list[str], provided: list[str]) -> None:
        self.missing = missing
        self.provided = provided
        prov = ", ".join(provided) if provided else "(none)"
        super().__init__(
            f"no path provided for bank id(s): {', '.join(missing)}. "
            f"Provided ids: {prov}. Pass --bank <bank_id>=<path> "
            "(or add it to the --banks JSON map)."
        )


def register_loader(name: str) -> Callable[[RecipeLoaderFn], RecipeLoaderFn]:
    """Decorator registering a figure-data loader under recipe ``name``."""

    def _decorator(fn: RecipeLoaderFn) -> RecipeLoaderFn:
        if name in LOADERS:
            raise ValueError(f"figure-data loader {name!r} is already registered.")
        LOADERS[name] = fn
        return fn

    return _decorator


def resolve_recipe_data(spec: FigureSpec, bank_paths: BankPaths) -> Any:
    """Build the prepared recipe input for ``spec`` from a ``{bank_id: path}`` map.

    Dispatches on ``spec.recipe`` into :data:`LOADERS`. Raises
    :class:`LoaderNotRegisteredError` if the recipe has no loader yet, and
    whatever the loader raises (e.g. :class:`UnmappedBankIdError`) otherwise.
    """
    loader = LOADERS.get(spec.recipe)
    if loader is None:
        raise LoaderNotRegisteredError(spec.recipe, sorted(LOADERS))
    return loader(spec, bank_paths)


def load_group_banks(spec: FigureSpec, bank_paths: BankPaths) -> list[tuple[str, ClassifierBank]]:
    """Resolve ``spec.inputs.groups`` to ``(group name, loaded ClassifierBank)`` pairs.

    The shared prologue every bank-backed recipe loader needs: pull the spec's
    groups (error if there are none), check each ``bank_id`` has a path in
    ``bank_paths`` (:class:`UnmappedBankIdError` naming any gaps), and load each
    bank via egm-data — in spec order. Recipe-specific loaders then adapt each
    bank into their own recipe input (e.g. :func:`load_prediction_groups` turns
    each into a :class:`PredictionGroup`), so the resolution logic lives once
    here rather than being re-copied per loader.
    """
    groups = (spec.inputs.groups if spec.inputs else None) or []
    if not groups:
        raise ValueError(f"spec {spec.id!r} has no inputs.groups to load.")
    missing = [g.bank_id for g in groups if g.bank_id not in bank_paths]
    if missing:
        raise UnmappedBankIdError(missing, sorted(bank_paths))
    return [(g.name, load_classifier_bank(bank_paths[g.bank_id])) for g in groups]


def _positive_prob(logits: dict[int, float], positive_label: int, *, bank_id: str | None) -> float:
    """Softmax over a trace's per-class logits; return P(``positive_label``).

    Softmax (not the stored ``label_prob``) so the probability of an arbitrary
    target class is well-defined, and so the same path generalizes beyond binary.
    """
    if positive_label not in logits:
        raise ValueError(
            f"positive_label {positive_label} is not among the pred_logits classes "
            f"{sorted(logits)} (bank {bank_id!r})."
        )
    keys = sorted(logits)
    z = np.array([logits[k] for k in keys], dtype=np.float64)
    z -= z.max()  # shift for numerical stability; softmax is shift-invariant
    e = np.exp(z)
    return float(e[keys.index(positive_label)] / e.sum())


def prediction_group_from_bank(
    bank: ClassifierBank, *, name: str, positive_label: int = 1
) -> PredictionGroup:
    """Adapt an eval predictions bank into a :class:`PredictionGroup`.

    Reads each trace's ``prediction.pred_logits`` -> P(``positive_label``) via
    softmax, and ``label_truth`` -> the per-trace class label. A fully labeled
    bank (an ``lpred_`` eval bank) yields ``labels`` + ``label_names``; a fully
    unlabeled bank (a ``upred_`` IAFDB bank) yields ``labels=None`` (one
    distribution, no class split). A bank that mixes the two, or whose traces
    carry no ``prediction``, is an error.
    """
    if not bank.traces:
        raise ValueError(f"bank {bank.id!r} has no traces to build a PredictionGroup from.")

    probs = np.empty(len(bank.traces), dtype=np.float64)
    for i, trace in enumerate(bank.traces):
        if trace.prediction is None:
            raise ValueError(
                f"trace {i} of bank {bank.id!r} has no prediction; prediction-histogram "
                "needs an eval predictions bank (lpred_ / upred_), not a raw bank."
            )
        probs[i] = _positive_prob(trace.prediction.pred_logits, positive_label, bank_id=bank.id)

    truth_present = [trace.label_truth is not None for trace in bank.traces]
    labels: np.ndarray | None
    label_names: dict[int, str] | None
    if all(truth_present):
        labels = np.array([int(trace.label_truth) for trace in bank.traces], dtype=np.int64)  # type: ignore[arg-type]
        label_names = dict(bank.labels) or None
    elif not any(truth_present):
        labels = None
        label_names = None
    else:
        raise ValueError(
            f"bank {bank.id!r} mixes traces with and without label_truth; prediction-histogram "
            "needs either an all-labeled (lpred_) or all-unlabeled (upred_) bank."
        )
    return PredictionGroup(name=name, probs=probs, labels=labels, label_names=label_names)


@register_loader("prediction-histogram")
def load_prediction_groups(spec: FigureSpec, bank_paths: BankPaths) -> list[PredictionGroup]:
    """Loader for ``prediction-histogram``: each spec group -> a PredictionGroup.

    Resolves + loads each group's bank via :func:`load_group_banks`, then adapts
    it with :func:`prediction_group_from_bank`.

    ``positive_label`` — which class's probability the histogram shows —
    defaults to 1 (the fibrotic / positive class of the binary v1 model), but a
    spec may override it via an ``inputs.positive_label`` key. That override is
    the multi-class hook: once the model emits more than two classes, one
    figure_spec per target class (each with its own ``positive_label``) renders
    P(class = k) individually.
    """
    extra = (spec.inputs.model_extra if spec.inputs else None) or {}
    positive_label = int(extra.get("positive_label", 1))
    return [
        prediction_group_from_bank(bank, name=name, positive_label=positive_label)
        for name, bank in load_group_banks(spec, bank_paths)
    ]
