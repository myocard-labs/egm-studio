"""Construct the unified per-trace view-model from an egm-data ClassifierBank.

``build_view_model(bank)`` returns one tidy ``pandas.DataFrame`` — one row per
trace — joining:

- **Identity** (:data:`IDENTITY_COLUMNS`): positional ``trace_idx``, the
  source bank's stable id + type, the integer ``label`` and its human-readable
  ``label_name``, amplitude unit, split tag.
- **Bank metadata**: every key in each trace's ``trace_metadata`` dict becomes
  a column. The exact keys vary by producer; a single bank is internally
  consistent. See *What a synthetic bank carries* below.
- **Features** (:data:`FEATURE_COLUMNS`): the 11 egm-features bundle columns
  via ``bundle.extract_all``.

**What a synthetic bank carries (``synthetic_bank`` 2.0).** The restructure made
the ClassifierBank a *source-agnostic ML compression* — signal, label, and the
keys to join back to where a trace came from. Generation parameters are the raw
material of the realism / parameter-estimation work, not of classification, so
they live on the parallel ``synthetic_bank`` and are reached through
``simulation_id``. Per trace you get:

- ``patient_id`` — the grouping key for a patient-aware split; one simulation is
  one "patient".
- ``simulation_id`` + ``pair_index`` — the **join key** back to the per-simulation
  config (egm-data's ``join_traces_with_simulations``).
- ``snr_db`` / ``noise_record`` / ``noise_channel`` — noise-mixing provenance.

**Gone, not relocated:** ``fibrosis_density``, ``fibrosis_density_realized``,
``electrode_row``, ``electrode_height_mm``, ``stim_edge``, ``seed``. Filtering or
plotting by one of those now means joining to the ``synthetic_bank``. Note the
older spellings too: ``sim_id`` became ``simulation_id`` so both writer paths and
the join agree on one name, and ``electrode_pair_id`` became ``pair_index``.

**The two writers do not agree yet, so don't assume either shape.** A synthetic
ClassifierBank can be written by egm-data's converter *or* directly by
synthetic-egm-pipeline, and as of egm-data v0.6.1 they differ:

- *Noise fields.* The direct writer **omits** ``snr_db`` / ``noise_record`` /
  ``noise_channel`` on a clean (unmixed) bank, so absence means the mixer never
  ran. The converter always writes them, NaN / ``""`` on a clean bank. Treat a
  **missing** noise column and a **NaN** one as the same fact; do not read NaN as
  "mixed, SNR unknown". Converging the two is deferred (FB-25).
- *Bank-level keys.* Only ``description``, ``trace_duration_ms`` and
  ``label_policy`` are common. The direct writer adds ``producer`` /
  ``producer_version``; the converter adds ``schema_version`` / ``created_utc`` /
  ``noise_bank_source``.

``label_policy`` is the one generation-derived bank-level key, and deliberately
just an identity string — it says what the classification task *is*. The label
*vocabulary* is already resolved for us: egm-data merges each simulation's
``label_names`` into ``ClassifierBank.labels`` and raises if two simulations
disagree about what class ``1`` means, so ``label_name`` below is a plain lookup.

Per ADR-001, this consumes an already-loaded typed ``ClassifierBank`` (the
GUI's ``loaders/`` layer, Block 7, does the file I/O) and returns a frame; it
does no I/O itself. For an *evaluated* bank (traces carry a ``prediction``) the
ML-outcome columns join here too (:mod:`.ml_outcomes`, Block 8); similarity
columns are computed on demand.

Unlabeled traces (the IAFDB shape) carry ``label = None`` / ``label_name =
None`` rather than raising — the view-model supports both scored and
label-free banks.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from myocard_egm_data.banks import ClassifierBank
from myocard_egm_features.bundle import extract_all

from myocard_egm_studio.view_model.ml_outcomes import ml_outcome_frame

#: A progress callback ``(traces_done, traces_total)``, called during feature
#: extraction. It may raise to abort the build — the GUI's Cancel path.
ProgressFn = Callable[[int, int], None]

#: Feature extraction runs in trace chunks so the caller can report progress and
#: cancel between them (the O(T^2) sample-entropy pass makes big banks slow).
_FEATURE_CHUNK = 8

__all__ = [
    "FEATURE_COLUMNS",
    "IDENTITY_COLUMNS",
    "ProgressFn",
    "build_view_model",
    "feature_units",
]

#: The 11 egm-features columns, in ``bundle.extract_all`` (docs/theory.md) order.
FEATURE_COLUMNS: tuple[str, ...] = (
    "peak_to_peak",
    "zero_crossings",
    "activation_position",
    "sec_peak_count",
    "spectral_centroid",
    "spectral_entropy",
    "dominant_frequency",
    "sample_entropy",
    "shannon_entropy",
    "lempel_ziv_complexity",
    "higuchi_fractal_dimension",
)

#: Per-trace identity columns this builder always emits (before bank metadata
#: keys and feature columns).
IDENTITY_COLUMNS: tuple[str, ...] = (
    "trace_idx",
    "source_bank_id",
    "source_bank_type",
    "label",
    "label_name",
    "amp_type",
    "split",
)

#: Units for the feature columns whose unit is *independent* of amplitude
#: calibration. Features absent here are unitless: counts (zero_crossings,
#: sec_peak_count), the entropies + Lempel-Ziv complexity + Higuchi fractal
#: dimension, and the [0, 1] fractional activation_position. The amplitude
#: feature peak_to_peak is unit-dependent and resolved by :func:`feature_units`.
#: Source of truth is egm-features' docs/theory.md; the labels live here because
#: this package owns the view-model column contract.
_STATIC_FEATURE_UNITS: dict[str, str] = {
    "spectral_centroid": "Hz",
    "dominant_frequency": "Hz",
}

#: ``amp_type`` -> the unit of an amplitude-derived feature (peak_to_peak). Only
#: raw millivolts carry a unit; a z-scored or otherwise-normalized bank makes
#: peak_to_peak unitless, so those amp_types are deliberately absent.
_AMPLITUDE_UNITS: dict[str, str] = {"mv": "mV"}


def feature_units(amp_type: str | None) -> dict[str, str]:
    """``{feature: unit}`` for the FEATURE_COLUMNS that carry a unit at ``amp_type``.

    Features not in the returned map are unitless. The only amplitude-dependent
    feature is ``peak_to_peak``: millivolts for a raw-mV bank
    (``amp_type="mv"``), unitless for a z-scored / normalized bank. The caller
    (the figure loader) passes the bank's ``amp_type``, so a z-scored bank is
    never mislabeled ``mV``.
    """
    units = dict(_STATIC_FEATURE_UNITS)
    amplitude_unit = _AMPLITUDE_UNITS.get(amp_type or "")
    if amplitude_unit is not None:
        units["peak_to_peak"] = amplitude_unit
    return units


def _empty_view_model(*, source: str | None, with_features: bool) -> pd.DataFrame:
    """Zero-row frame with the fixed columns (bank-metadata keys are unknown)."""
    cols = list(IDENTITY_COLUMNS)
    if source is not None:
        cols = ["source", *cols]
    if with_features:
        cols += list(FEATURE_COLUMNS)
    return pd.DataFrame({c: [] for c in cols})


def build_view_model(
    bank: ClassifierBank,
    *,
    source: str | None = None,
    with_features: bool = True,
    positive_label: int = 1,
    progress: ProgressFn | None = None,
) -> pd.DataFrame:
    """Build the per-trace view-model DataFrame for ``bank``.

    Parameters
    ----------
    bank
        A loaded :class:`~myocard_egm_data.banks.ClassifierBank`.
    source
        Optional group label (e.g. ``"Synthetic v1.5"`` / ``"IAFDB"``) added
        as a constant leading ``source`` column. Flow A / the figure recipes
        group + color by this when multiple banks are loaded.
    with_features
        When ``True`` (default), runs ``bundle.extract_all`` and appends the
        11 feature columns. Set ``False`` for a metadata-only frame (cheap;
        skips the ~O(T^2) sample-entropy pass).

    Returns
    -------
    pandas.DataFrame
        One row per trace; columns are ``[source?]`` + identity + bank-metadata
        keys + (optionally) the 11 feature columns. Default RangeIndex aligned
        with ``trace_idx``.
    """
    if bank.n_traces == 0:
        return _empty_view_model(source=source, with_features=with_features)

    bank_type_by_id = {meta.bank_id: meta.bank_type for meta in bank.banks}
    rows: list[dict[str, object]] = []
    for i, trace in enumerate(bank.traces):
        label = trace.label_truth
        row: dict[str, object] = {
            "trace_idx": i,
            "source_bank_id": trace.bank_id,
            "source_bank_type": bank_type_by_id.get(trace.bank_id),
            "label": label,
            "label_name": bank.labels.get(label) if label is not None else None,
            "amp_type": trace.amp_type,
            "split": trace.split,
        }
        # Flatten the producer's per-trace metadata. Reserved identity keys win
        # on the unlikely chance a producer reuses one of those names.
        for key, value in trace.trace_metadata.items():
            if key not in row:
                row[key] = value
        rows.append(row)

    meta_df = pd.DataFrame(rows)
    if source is not None:
        meta_df.insert(0, "source", source)

    if with_features:
        signals = bank.signal_array()
        feature_df = _extract_features(signals, bank.uniform_fs_hz(), progress)
        feature_df.index = meta_df.index
        result = pd.concat([meta_df, feature_df], axis=1)
    else:
        result = meta_df

    ml_df = ml_outcome_frame(bank, positive_label=positive_label)
    if ml_df is not None:  # an evaluated bank -> append the ML-outcome columns (Block 8)
        ml_df.index = result.index
        result = pd.concat([result, ml_df], axis=1)
    return result


def _extract_features(
    signals: np.ndarray,
    fs_hz: float,
    progress: ProgressFn | None,
    *,
    chunk: int = _FEATURE_CHUNK,
) -> pd.DataFrame:
    """Run ``extract_all`` in trace chunks, reporting progress between them.

    Chunking lets the caller show a progress bar and cancel a long extraction — a
    ``progress`` callback that raises aborts the build. The per-trace features are
    independent, so the chunked result equals one ``extract_all`` over all traces.
    """
    total = len(signals)
    if progress is not None:
        progress(0, total)
    if total <= chunk:
        frame = extract_all(signals, fs_hz=fs_hz)
        if progress is not None:
            progress(total, total)
        return frame
    frames: list[pd.DataFrame] = []
    for start in range(0, total, chunk):
        frames.append(extract_all(signals[start : start + chunk], fs_hz=fs_hz))
        if progress is not None:
            progress(min(start + chunk, total), total)
    return pd.concat(frames, ignore_index=True)
