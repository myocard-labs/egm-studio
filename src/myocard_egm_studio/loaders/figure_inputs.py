"""Figure-data loaders — turn a spec's bank ids into prepared recipe inputs.

This is the renderer's *loading step*: the bridge between egm-data banks on disk
and the in-memory inputs that recipes draw (``charts/matplotlib/inputs``). A
recipe stays pure plotting; this module does the I/O + adaptation.

:func:`resolve_recipe_data` takes the spec + a ``{artifact_id: path}`` map. That
map comes either from a phase folder's manifest (:func:`..manifest.bank_paths_from_phase`,
the ``egm-studio-render --phase`` path) or, for ad-hoc rendering, from the CLI's
hand-supplied ``--bank`` / ``--banks`` flags — both are the same ``{id: path}``
shape. The bank -> recipe-input adapters below (e.g. :func:`prediction_group_from_bank`)
are permanent and source-agnostic.

Loaders register per recipe (mirroring the ``charts/matplotlib`` recipe
registry): :func:`resolve_recipe_data` dispatches on ``spec.recipe`` into
:data:`LOADERS`. ``prediction-histogram``, ``feature-distribution-overlay``,
``bar-chart-with-deltas``, ``roc-curve-multi-line``, and
``calibration-reliability-diagram`` have loaders so far (the last two reuse
``prediction-histogram``'s — all three build the same per-trace P(positive) +
truth); more land as recipes gain real-data paths.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from myocard_egm_data.banks import load_classifier_bank
from myocard_egm_data.records import (
    NoiseBankRunRecord,
    TrainingRunRecord,
    load_noise_bank_run_record,
    load_training_run_record,
)
from numpy.typing import NDArray

from myocard_egm_studio.analysis.aggregation import aggregate_distance, feature_distances
from myocard_egm_studio.analysis.metrics import positive_prob
from myocard_egm_studio.analysis.similarity import nearest_along_feature
from myocard_egm_studio.charts.inputs import (
    BarChartData,
    FeatureGroup,
    PredictionGroup,
    TableData,
    TracePair,
    TracePairGallery,
    TrainingCurve,
)
from myocard_egm_studio.charts.matplotlib import spec_fields
from myocard_egm_studio.charts.matplotlib.selection import (
    select_from_available,
    select_layout_features,
)
from myocard_egm_studio.loaders.feature_group import feature_group_from_frame
from myocard_egm_studio.view_model import FEATURE_COLUMNS, build_view_model

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
    "load_bar_chart_distances",
    "load_curation_summary_table",
    "load_feature_groups",
    "load_group_banks",
    "load_prediction_groups",
    "load_trace_pair_gallery",
    "load_training_curve",
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
    """P(``positive_label``) via :func:`analysis.metrics.positive_prob`, naming the bank on error."""
    try:
        return positive_prob(logits, positive_label)
    except ValueError as exc:
        raise ValueError(f"{exc} (bank {bank_id!r})") from exc


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
        # `all(truth_present)` proves every label_truth is set, but the narrowing lives in a
        # separate list, so mypy still sees `int | None` on the traces themselves.
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
@register_loader("roc-curve-multi-line")
@register_loader("calibration-reliability-diagram")
def load_prediction_groups(spec: FigureSpec, bank_paths: BankPaths) -> list[PredictionGroup]:
    """Loader for ``prediction-histogram``, ``roc-curve-multi-line``, and
    ``calibration-reliability-diagram``: each spec group -> a PredictionGroup.

    All three need the same per-trace P(positive) + truth, so they share this
    loader (the two metric recipes additionally *require* truth, which they
    enforce at draw time). Resolves + loads each group's bank via
    :func:`load_group_banks`, then adapts it with :func:`prediction_group_from_bank`.

    ``positive_label`` — which class's probability the histogram shows —
    defaults to 1 (the fibrotic / positive class of the binary v1 model), but a
    spec may override it via an ``inputs.positive_label`` key. That override is
    the multi-class hook: once the model emits more than two classes, one
    figure_spec per target class (each with its own ``positive_label``) renders
    P(class = k) individually.
    """
    positive_label = spec_fields.positive_label(spec)
    return [
        prediction_group_from_bank(bank, name=name, positive_label=positive_label)
        for name, bank in load_group_banks(spec, bank_paths)
    ]


@register_loader("feature-distribution-overlay")
def load_feature_groups(spec: FigureSpec, bank_paths: BankPaths) -> list[FeatureGroup]:
    """Loader for ``feature-distribution-overlay``: each spec group -> its
    per-feature egm-features distributions.

    Resolves + loads each group's bank via :func:`load_group_banks`, builds the
    per-trace view-model (which runs ``bundle.extract_all``), and pulls the 11
    :data:`~myocard_egm_studio.view_model.FEATURE_COLUMNS` out as plain arrays —
    one :class:`FeatureGroup` per spec group, in spec order. Feature-level, so it
    works on labeled and unlabeled banks alike (it reads signals, not labels).
    """
    return [
        feature_group_from_frame(build_view_model(bank, source=name), name=name)
        for name, bank in load_group_banks(spec, bank_paths)
    ]


@register_loader("bar-chart-with-deltas")
def load_bar_chart_distances(spec: FigureSpec, bank_paths: BankPaths) -> BarChartData:
    """Loader for ``bar-chart-with-deltas`` (F-1.5.3): per-group aggregate
    sim-realism distance to a reference bank.

    ``inputs.groups`` lists every bank; ``inputs.reference`` names which group is
    the comparison reference (the IAFDB bank). One bar per *other* group, its
    height the aggregate per-feature distance between that group's features and
    the reference's (``analysis/aggregation``). ``styling.metric`` is ``"ks"``
    (default — unitless, so averaging across the heterogeneous features is sound)
    or ``"wasserstein"``; ``layout.features`` optionally restricts which
    egm-features columns define the distance (default: all); ``layout.baseline``
    optionally names the bar to use as the delta reference.

    Until the Phase-1.5 intervention banks exist, the "groups" are synthetic-
    pipeline variants we can already generate (IAFDB-noise on/off, fraction-
    healthy / density-range tweaks) — enough to prove the distance->bar pipeline
    end to end.
    """
    extra = (spec.inputs.model_extra if spec.inputs else None) or {}
    reference_name = extra.get("reference")
    if not reference_name:
        raise ValueError(
            "bar-chart-with-deltas needs inputs.reference — the name of the group every "
            "other group's distance is measured against (e.g. the IAFDB bank)."
        )
    metric = str((spec.styling or {}).get("metric", "ks"))
    feature_cols = select_layout_features(spec, FEATURE_COLUMNS)

    banks = load_group_banks(spec, bank_paths)
    names = [name for name, _ in banks]
    if reference_name not in names:
        raise ValueError(f"inputs.reference {reference_name!r} is not among the groups {names}.")

    frames = {name: build_view_model(bank) for name, bank in banks}
    reference_frame = frames[reference_name]

    categories: list[str] = []
    values: list[float] = []
    for name in names:
        if name == reference_name:
            continue
        distances = feature_distances(
            frames[name], reference_frame, feature_cols=feature_cols, metric=metric
        )
        categories.append(name)
        values.append(aggregate_distance(distances))
    if not categories:
        raise ValueError(
            f"bar-chart-with-deltas needs at least one group besides the reference "
            f"{reference_name!r}."
        )

    baseline_index: int | None = None
    baseline_name = (spec.layout or {}).get("baseline")
    if baseline_name:
        if baseline_name not in categories:
            raise ValueError(
                f"layout.baseline {baseline_name!r} is not one of the bar categories "
                f"{categories} (it can't be the reference group)."
            )
        baseline_index = categories.index(baseline_name)

    return BarChartData(
        categories=categories,
        values=np.array(values, dtype=np.float64),
        baseline_index=baseline_index,
        value_label=f"mean {metric.upper()} distance to {reference_name}",
    )


#: Default gallery row count when ``styling.n_pairs`` is unset.
_DEFAULT_N_PAIRS = 8


def _spread_indices(values: NDArray[np.float64], n: int) -> NDArray[np.intp]:
    """Positional indices of ``n`` rows spread evenly across the finite ``values``.

    Sorts by the (finite) feature value and samples ``n`` evenly along it, so the
    gallery spans the feature's range rather than whatever order the bank is in.
    Non-finite values are dropped and the picks de-duplicated, so fewer than ``n``
    rows can come back for a small bank.
    """
    finite_pos = np.flatnonzero(np.isfinite(values))
    if finite_pos.size == 0:
        raise ValueError("no source traces have a finite feature value to match on.")
    order = finite_pos[np.argsort(values[finite_pos], kind="stable")]
    k = min(n, order.size)
    picks = order[np.linspace(0, order.size - 1, k).round().astype(np.intp)]
    return np.unique(picks)


@register_loader("trace-pair-gallery")
def load_trace_pair_gallery(spec: FigureSpec, bank_paths: BankPaths) -> TracePairGallery:
    """Loader for ``trace-pair-gallery`` (F-1.5.7): pair source traces to their
    nearest pool-bank match along one egm-feature.

    Exactly two ``inputs.groups`` are required: the **first** is the source (left
    column, e.g. synthetic), the **second** the match pool (right column, e.g.
    IAFDB). ``styling.feature`` (required — the per-feature similarity axis is
    ADR-020's open question, so there is no default) names the egm-features column
    to match on; ``styling.n_pairs`` (default 8) sets the row count.

    Builds the per-trace view-model for both banks, selects a spread of source
    traces along ``feature``, finds each one's nearest pool trace along the same
    feature (:func:`...analysis.similarity.nearest_along_feature`), and pulls the
    raw signals (``bank.signal_array()``) for both — feature- + signal-level, so
    it works on labeled and unlabeled banks alike.

    Note: building the pool view-model runs ``bundle.extract_all`` over every pool
    trace, which is slow on a full IAFDB bank (the O(T^2) sample-entropy pass) —
    see the roadmap's feature-extraction progress-feedback item.
    """
    styling = spec.styling or {}
    feature = styling.get("feature")
    if not feature:
        raise ValueError(
            "trace-pair-gallery needs styling.feature — the egm-features column to match "
            "traces on (per-feature similarity, ADR-020; no default since the metric is open)."
        )
    feature = str(feature)
    if feature not in FEATURE_COLUMNS:
        raise ValueError(
            f"styling.feature {feature!r} is not an egm-features column; "
            f"choose one of {list(FEATURE_COLUMNS)}."
        )
    n_pairs = int(styling.get("n_pairs", _DEFAULT_N_PAIRS))
    if n_pairs < 1:
        raise ValueError(f"styling.n_pairs must be >= 1, got {n_pairs}.")

    groups = (spec.inputs.groups if spec.inputs else None) or []
    if len(groups) != 2:
        raise ValueError(
            f"trace-pair-gallery needs exactly 2 inputs.groups (source, pool); got {len(groups)}."
        )
    (source_name, source_bank), (pool_name, pool_bank) = load_group_banks(spec, bank_paths)

    source_values = build_view_model(source_bank)[feature].to_numpy(dtype=np.float64)
    pool_vm = build_view_model(pool_bank)
    pool_values = pool_vm[feature].to_numpy(dtype=np.float64)
    source_signals = source_bank.signal_array()
    pool_signals = pool_bank.signal_array()

    pairs: list[TracePair] = []
    for src_idx in _spread_indices(source_values, n_pairs):
        target = float(source_values[src_idx])
        pool_idx = nearest_along_feature(pool_vm, feature=feature, target_value=target)
        pairs.append(
            TracePair(
                left=np.asarray(source_signals[src_idx], dtype=np.float64).copy(),
                right=np.asarray(pool_signals[pool_idx], dtype=np.float64).copy(),
                annotation=f"{feature} {target:.3g} → {float(pool_values[pool_idx]):.3g}",
            )
        )

    return TracePairGallery(
        pairs=pairs,
        left_title=source_name,
        right_title=pool_name,
        left_fs_hz=source_bank.uniform_fs_hz(),
        right_fs_hz=pool_bank.uniform_fs_hz(),
    )


#: Default order of the IAFDB curation-summary fields. A figure may show a subset
#: / reordering via ``layout.fields`` (these keys); an absent key shows them all.
_DEFAULT_CURATION_FIELD_ORDER = (
    "source",
    "records",
    "patients",
    "segments",
    "sampling_rate",
    "window",
    "hop",
    "band",
    "calibration",
    "threshold",
)


def _curation_fields(record: NoiseBankRunRecord) -> dict[str, tuple[str, str]]:
    """``{field_key: (label, value)}`` for every curation field this record supports.

    Labels + value formatting are fixed here — the spec chooses *which* fields via
    ``layout.fields``, not how they read. ``patients`` / ``segments`` are present
    only when the record carries per-trace provenance.
    """
    cal = record.calibration
    calibration = (
        f"{cal.method} (target {cal.target_qrs_pp_mv:g} mV)"
        if cal.target_qrs_pp_mv is not None
        else str(cal.method)
    )
    sel = record.selection
    threshold = (
        f"percentile (bottom {sel.threshold_value:g}%)"
        if sel.threshold_mode.value == "percentile"
        else f"absolute (<= {sel.threshold_value:g} mV)"
    )
    win = record.windowing
    fields: dict[str, tuple[str, str]] = {
        "source": ("Source", str(record.source)),
        "records": ("Source records", f"{len(record.source_records):,}"),
        "sampling_rate": ("Sampling rate", f"{record.fs_hz:g} Hz"),
        "window": ("Window", f"{win.window_ms:g} ms ({win.window_samples} samples)"),
        "hop": ("Hop", f"{win.hop_ms:g} ms"),
        "band": ("Band-pass", f"{record.band_hz[0].root:g}-{record.band_hz[1].root:g} Hz"),
        "calibration": ("Calibration", calibration),
        "threshold": ("Threshold", threshold),
    }
    # Patient + segment counts need the optional per-trace provenance arrays.
    ptp = record.per_trace_provenance
    if ptp is not None:
        fields["patients"] = ("Patients", f"{len(set(ptp.patient_id)):,}")
        fields["segments"] = ("Segments (post-curation)", f"{len(ptp.patient_id):,}")
    return fields


def _curation_summary_table(record: NoiseBankRunRecord, requested_fields: object) -> TableData:
    """Curation TableData honoring a ``layout.fields`` override (default: all fields)."""
    fields = _curation_fields(record)
    default_order = [key for key in _DEFAULT_CURATION_FIELD_ORDER if key in fields]
    selected = select_from_available(requested_fields, default_order, what="layout.fields")
    rows = [list(fields[key]) for key in selected]
    return TableData(columns=["Field", "Value"], rows=rows, title="IAFDB curation summary")


@register_loader("summary-table")
def load_curation_summary_table(spec: FigureSpec, bank_paths: BankPaths) -> TableData:
    """Loader for ``summary-table`` (F-1.5.10): the IAFDB curation-provenance summary.

    Resolves exactly one ``inputs.groups`` entry — the noise-bank run record's id —
    to a path in ``bank_paths`` and reads the ``noise_bank_run_record`` JSON via
    egm-data's :func:`load_noise_bank_run_record`, then builds a key/value summary
    of the extraction provenance: source, record / patient / segment counts,
    sampling + windowing, filter band, calibration, and the selection threshold.

    Unlike the other loaders the resolved path is a run-record JSON sidecar, not a
    ClassifierBank, so this resolves the id itself rather than via
    :func:`load_group_banks`. Per-record / per-channel breakdowns aren't in the run
    record (no per-trace record or channel field), so the table is the aggregate
    summary — a finer breakdown would need a schema addition. The metrics-comparison
    instance (F-2.9) is a different table built from predictions banks; it lands as
    an internal dispatch on this loader when Phase 2 arrives.
    """
    groups = (spec.inputs.groups if spec.inputs else None) or []
    if len(groups) != 1:
        raise ValueError(
            "summary-table (IAFDB curation) needs exactly one inputs.groups entry — the "
            f"noise-bank run record's id; got {len(groups)}."
        )
    bank_id = groups[0].bank_id
    path = bank_paths.get(bank_id)
    if path is None:
        raise UnmappedBankIdError([bank_id], sorted(bank_paths))
    return _curation_summary_table(
        load_noise_bank_run_record(path), (spec.layout or {}).get("fields")
    )


#: Pretty y-axis labels for common selection metrics; others use the key as-is.
_METRIC_LABELS = {"auroc": "AUROC", "ece": "ECE", "f1": "F1"}


def _scalar(value: object) -> float:
    """A finite float, or NaN for None / non-numeric (so a curve gaps, not crashes)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return float("nan")
    return float(value)


def _training_curve(record: TrainingRunRecord, metric_key: str) -> TrainingCurve:
    """Per-epoch loss + selection-metric series from a training run record."""
    if not record.epochs:
        raise ValueError("training run record has no epochs.")
    epochs = np.array([e.epoch for e in record.epochs], dtype=np.int64)
    train_loss = np.array([_scalar(e.train_loss) for e in record.epochs], dtype=np.float64)
    val_loss = np.array([_scalar(e.val_loss) for e in record.epochs], dtype=np.float64)
    metric_vals = np.array(
        [_scalar(e.val_metrics.get(metric_key)) for e in record.epochs], dtype=np.float64
    )
    if bool(np.all(np.isnan(metric_vals))):
        available = sorted(
            {
                k
                for e in record.epochs
                for k, v in e.val_metrics.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
        )
        raise ValueError(
            f"styling.metric {metric_key!r} is not a scalar val metric in this run; "
            f"available: {available}."
        )
    return TrainingCurve(
        epochs=epochs,
        loss={"train": train_loss, "val": val_loss},
        metric={"val": metric_vals},
        metric_name=_METRIC_LABELS.get(metric_key, metric_key),
        best_epoch=int(record.best.epoch) if record.best.epoch is not None else None,
    )


@register_loader("training-curve")
def load_training_curve(spec: FigureSpec, bank_paths: BankPaths) -> TrainingCurve:
    """Loader for ``training-curve`` (F-1.5.11): one run's loss + metric curves.

    Resolves the single ``inputs.groups`` entry — the training run's id — to a
    ``run.json`` path in ``bank_paths`` and reads it via egm-data's
    :func:`load_training_run_record` (another run-record sidecar, like the
    curation summary, not a ClassifierBank). Pulls per-epoch ``train_loss`` /
    ``val_loss`` and the ``styling.metric`` validation metric (default
    ``"auroc"``), and marks ``record.best.epoch`` as the selected epoch; a null /
    non-scalar epoch value becomes a gap in its curve.
    """
    groups = (spec.inputs.groups if spec.inputs else None) or []
    if len(groups) != 1:
        raise ValueError(
            "training-curve needs exactly one inputs.groups entry — the training run's id; "
            f"got {len(groups)}."
        )
    run_id = groups[0].bank_id
    path = bank_paths.get(run_id)
    if path is None:
        raise UnmappedBankIdError([run_id], sorted(bank_paths))
    metric_key = str((spec.styling or {}).get("metric", "auroc"))
    return _training_curve(load_training_run_record(path), metric_key)


def training_curve_from_run(path: str | Path, *, metric_key: str = "auroc") -> TrainingCurve:
    """Direct adapter: a training-run ``run.json`` path -> :class:`TrainingCurve`.

    The Flow B / GUI path — reads the run-record sidecar via egm-data and pulls the
    per-epoch loss + ``metric_key`` validation metric, bypassing a FigureSpec (as
    :func:`prediction_group_from_bank` does for a predictions bank). Reused by the
    training-curves view; ``metric_key`` defaults to ``"auroc"``.
    """
    return _training_curve(load_training_run_record(str(path)), metric_key)
