"""Find and load the ``synthetic_bank`` that a ClassifierBank was generated alongside.

θ and the per-simulation generation config deliberately do **not** live on the
ClassifierBank — that artifact is a source-agnostic ML compression (signal, label, and
the ``simulation_id`` join key). The generation side lives on a **parallel**
``synthetic_bank``, and the two are joined on ``simulation_id``
(``cross_artifact_linkage_design.md`` P2; ``synthetic_bank_source_of_truth.md`` §12).

This module answers the question that leaves open for a consumer: *given a loaded
ClassifierBank, where is its θ companion?* The answer is recorded in the artifact rather
than inferred from a filename — the producer writes an extra entry into ``banks``:

===========================  ==================================  =========================
``bank_type``                ``bank_path``                       what it is
===========================  ==================================  =========================
``synthetic_egm_pipeline``   ``<local>``                         the bank itself
``synthetic_generation_params``  e.g. ``run_theta.synthetic.h5`` the **θ companion**
``mixer``                    e.g. ``iafdb_noise.h5``             the noise bank, when mixed
===========================  ==================================  =========================

So discovery is a lookup by ``bank_type``, and the path is normally a bare filename
resolved beside the ClassifierBank — move the directory and the reference still resolves.

Per ADR-001 the actual file read goes through egm-data
(``read_synthetic_bank_hdf5``); this module only locates the file and hands back the
typed model.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from myocard_egm_contracts import synthetic_bank as _synthetic_bank_models
from myocard_egm_data.banks import (
    ClassifierBank,
    ClassifierTrace,
    load_classifier_bank,
    read_synthetic_bank_hdf5,
)

from myocard_egm_studio.view_model import ProgressFn, build_view_model, theta_frame
from myocard_egm_studio.view_model.theta import (
    SIMULATION_ID_KEY,
    theta_companion_ref,
    unwrap_root,
)

__all__ = [
    "SignalSource",
    "load_theta_companion",
    "load_with_theta",
    "swap_in_synthetic_signals",
]

#: Which bank's samples the features are computed from. ``"classifier"`` is the default
#: because T4 matches synthetic to IAFDB *as the pipeline delivers it* — calibrating on
#: generation-output samples would optimise a distribution nothing downstream consumes.
#: ``"synthetic"`` exposes the pre-post-processing waveform; the delta between the two is
#: itself a measurement of what post-processing does to the feature distribution.
SignalSource = Literal["classifier", "synthetic"]


def load_theta_companion(
    bank: ClassifierBank, *, bank_path: Path | str
) -> _synthetic_bank_models.SyntheticBank | None:
    """Load the θ companion of ``bank``, or ``None`` when it has none.

    Raises rather than returning ``None`` when a companion is *declared* but unusable —
    a missing file, or a file whose stable id is not the one the ClassifierBank named.
    The distinction matters: ``None`` means "no generation side exists", while a raise
    means "it exists and something is wrong", and silently collapsing the second into the
    first would present an empty θ table as a legitimate result.

    The id check here is deliberately **not** a duplicate of egm-data's join check. This
    one compares the companion against *the id this bank named*, catching a companion
    swapped underneath a correct-looking path; egm-data's compares against the whole
    ``banks`` list at join time. Both are cheap and they fail on different mistakes.
    """
    ref = theta_companion_ref(bank, bank_path=bank_path)
    if ref is None:
        return None
    if not ref.path.exists():
        raise FileNotFoundError(
            f"ClassifierBank names a θ companion {ref.bank_id!r} at {ref.path}, but no "
            "file is there. The companion is expected beside the bank; if the bank was "
            "moved without it, restore the pair or re-export."
        )
    companion = read_synthetic_bank_hdf5(ref.path)
    if companion.bank_id is not None and companion.bank_id != ref.bank_id:
        raise ValueError(
            f"θ companion at {ref.path} carries bank_id {companion.bank_id!r}, but the "
            f"ClassifierBank names {ref.bank_id!r}. Joining these would pair traces with "
            "another run's generation config — simulation ids restart at 0 in every "
            "bank, so the result would look plausible and be wrong."
        )
    return companion


def swap_in_synthetic_signals(
    bank: ClassifierBank, companion: _synthetic_bank_models.SyntheticBank
) -> ClassifierBank:
    """``bank`` with each trace's signal replaced by its ``synthetic_bank`` counterpart.

    Identity, labels and metadata stay the ClassifierBank's; **only the samples change**.
    That is what makes the two signal sources comparable: same rows, same θ, same labels,
    different waveform — so a distance computed over one and then the other differs solely
    by the post-processing that separates them.

    Traces are matched on ``(simulation_id, pair_index)`` rather than by position. The two
    banks *are* written in the same order today, so position would work and would break
    silently the first time it stopped being true. The key is verified unique on both
    sides before use, because a non-unique key would pair traces confidently and wrongly.

    Raises
    ------
    ValueError
        If either side's ``(simulation_id, pair_index)`` is non-unique, if a trace has no
        counterpart, or if the two banks disagree on sampling rate — features computed
        across a rate mismatch are quietly wrong rather than obviously so.
    """
    fs_classifier = {float(t.freq_hz) for t in bank.traces}
    fs_synthetic = float(unwrap_root(companion.fs_hz))
    if fs_classifier and not all(abs(f - fs_synthetic) < 1e-9 for f in fs_classifier):
        raise ValueError(
            f"the ClassifierBank samples at {sorted(fs_classifier)} Hz but its θ companion "
            f"at {fs_synthetic} Hz. Swapping signals across a rate mismatch would silently "
            "change every sample-indexed feature; re-export the pair at one rate."
        )

    traces = companion.traces
    synthetic_by_key: dict[tuple[int, int], int] = {}
    for index, (sim_id, pair) in enumerate(
        zip(traces.simulation_id, traces.pair_index, strict=True)
    ):
        key = (int(unwrap_root(sim_id)), int(unwrap_root(pair)))
        if key in synthetic_by_key:
            raise ValueError(
                f"θ companion has two traces keyed {key} (simulation_id, pair_index). "
                "The signal swap needs that pair to identify a trace; a duplicate would "
                "pair waveforms with the wrong row."
            )
        synthetic_by_key[key] = index

    swapped: list[ClassifierTrace] = []
    seen: set[tuple[int, int]] = set()
    for position, trace in enumerate(bank.traces):
        meta = trace.trace_metadata or {}
        if SIMULATION_ID_KEY not in meta or "pair_index" not in meta:
            raise ValueError(
                f"trace {position} carries no {SIMULATION_ID_KEY!r}/'pair_index', so it "
                "cannot be matched to a synthetic trace. The synthetic signal source is "
                "only available for synthetic banks."
            )
        key = (int(meta[SIMULATION_ID_KEY]), int(meta["pair_index"]))
        if key in seen:
            raise ValueError(
                f"ClassifierBank has two traces keyed {key} (simulation_id, pair_index); "
                "the swap would be ambiguous."
            )
        seen.add(key)
        source_index = synthetic_by_key.get(key)
        if source_index is None:
            raise ValueError(
                f"trace {position} is keyed {key} but the θ companion has no such trace. "
                "The two banks do not describe the same run."
            )
        signal = np.asarray(traces.signal[source_index], dtype=np.float32)
        swapped.append(dataclasses.replace(trace, signal=signal))

    return dataclasses.replace(bank, traces=swapped)


def load_with_theta(
    path: Path | str,
    *,
    source: str | None = None,
    signal_source: SignalSource = "classifier",
    progress: ProgressFn | None = None,
) -> tuple[pd.DataFrame, bool]:
    """The view-model with this bank's θ columns joined on, and whether θ was found.

    The T4 entry point (STU1 / STU4 / STU5). Returns ``(frame, has_theta)`` rather than
    raising when a bank has no generation side: an IAFDB bank legitimately has none, and
    the caller needs to distinguish *no θ here* — hide the θ axes — from *θ failed to
    load*, which does raise, out of :func:`load_theta_companion`.

    θ columns are prefixed ``<function>.<field>``, so they cannot collide with the
    features or the producer's metadata keys, and the frame stays one row per trace.

    It lives here rather than in ``gui/sources.py`` beside the other load entries because
    it needs no Qt: keeping it in ``loaders/`` means its tests run in the fast set, and
    everything under ``tests/gui/`` is auto-marked ``gui`` and deselected there.

    Deliberately **not** memoized in the tiered cache. That cache keys on the bank id
    alone (:func:`view_model_key`), so the plain and θ-joined frames would share a key and
    one would be served where the other was asked for. Threading θ into the key is a cache
    change, not a loader change, so it waits for a step that owns the cache.
    """
    bank = load_classifier_bank(path)
    label = source or bank.id or Path(path).stem
    companion = load_theta_companion(bank, bank_path=Path(path))
    if companion is None:
        if signal_source == "synthetic":
            raise ValueError(
                "the synthetic signal source needs a θ companion, and this bank has none. "
                "Only a synthetic bank carries one."
            )
        return build_view_model(bank, source=label, progress=progress), False

    featured = bank if signal_source == "classifier" else swap_in_synthetic_signals(bank, companion)
    frame = build_view_model(featured, source=label, progress=progress)
    theta = theta_frame(bank, companion)
    if theta.empty:
        return frame, False
    theta.index = frame.index
    return pd.concat([frame, theta], axis=1), True
