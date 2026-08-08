"""Per-trace generation parameters (θ) from the paired ``synthetic_bank``.

The T4 views — feature-vs-θ scatter (STU1), the sim↔IAFDB comparison (STU5), the
parameter estimator (STU4) — all need the same thing: **one row per trace, carrying that
trace's generation parameters beside its features**. θ lives on the parallel
``synthetic_bank``, keyed by ``simulation_id``; this module turns that per-simulation
config into per-trace columns.

**Why the θ-spec is not the source.** ``generation_params`` describes which knobs a sweep
varied, as ``TunedParam`` entries. It is tempting to drive the projection from that list,
but it is a *declaration* and it can be empty while the configs genuinely differ — that is
the state SEP12 ships today (``"knobs": []``) with the sweep itself still to come in
SEP11. Driving from it would emit **zero θ columns for a bank whose simulations really do
vary in substrate density and electrode height**, which is exactly the variation STU1
exists to plot. The design doc settles the precedence: *config is authoritative; a per-sim
θ-matrix is a derived convenience*
(``cross_artifact_linkage_design.md`` P2). So:

- **Values** come from each simulation's typed per-function config.
- **``generation_params.knobs``**, when populated, only *marks* which of those columns the
  sweep declared as tuned — see :func:`declared_knob_paths`. It never limits what is
  projected.

**What becomes a column.** Each per-function object (``geometry`` / ``cell_model`` /
``substrate`` / ``activation`` / ``electrodes`` / ``backend``) contributes its **scalar**
leaves, named ``<function>.<field>`` — ``substrate.density``, ``electrodes.height_mm``,
``geometry.anisotropy_ratio``. Deliberately excluded:

- **Non-scalars** (lists, nested objects). ``electrodes.pairs`` is the motivating case: it
  is per-*pair* detail keyed by ``pair_index``, not a per-simulation fact, and a list is
  not a scatter axis. They stay reachable for provenance rendering.
- **The ``type`` discriminator** of each object, which names the variant rather than
  parameterising it. It is surfaced separately as ``<function>.type`` only when it varies
  across simulations, since a constant variant is regime-level context, not θ.

Qt-free and I/O-free: it takes an already-loaded ClassifierBank + ``SyntheticBank`` and
returns a frame (ADR-001; the loading is ``loaders/synthetic_bank.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from myocard_egm_contracts import synthetic_bank as _synthetic_bank_models
from myocard_egm_data.banks import ClassifierBank, join_traces_with_simulations

__all__ = [
    "LOCAL_SENTINEL",
    "SIMULATION_ID_KEY",
    "THETA_BANK_TYPE",
    "THETA_PREFIXES",
    "CompanionRef",
    "declared_knob_paths",
    "theta_companion_ref",
    "theta_frame",
    "unwrap_root",
]

#: The per-trace key that points back at a simulation. Mirrors egm-data's constant of the
#: same name so the two cannot drift apart (see CL-144 on hand-mirrored vocabularies).
SIMULATION_ID_KEY = "simulation_id"

#: ``ClassifierBankMetaData.bank_type`` marking the entry that points at the θ companion.
#: The producer writes this string; it is the only reliable discriminator, since the
#: companion's *id* is derived and its *path* is a bare filename.
THETA_BANK_TYPE = "synthetic_generation_params"

#: ``bank_path`` sentinel meaning "this entry is the bank you already have in hand", not a
#: resolvable path. Never treat it as a filename. Public because ``save.producer`` walks the
#: same ``banks[]`` source list when copying a bank into a phase, and the string must not be
#: hand-mirrored in two modules (CL-144).
LOCAL_SENTINEL = "<local>"


@dataclass(frozen=True)
class CompanionRef:
    """Where a ClassifierBank says its θ companion is, before any file is opened."""

    bank_id: str
    path: Path


def theta_companion_ref(bank: ClassifierBank, *, bank_path: Path | str) -> CompanionRef | None:
    """The θ companion this bank points at, or ``None`` if it has no generation side.

    ``None`` is the honest answer for an IAFDB bank, a hand-built bank, or any bank whose
    producer wrote no companion entry — those have no θ, as opposed to θ that failed to
    load. Callers that need θ should treat ``None`` as "this view does not apply here",
    not as an error.

    Parameters
    ----------
    bank
        The loaded ClassifierBank.
    bank_path
        Where *that* bank was read from. The companion path is normally a bare filename
        and is resolved beside it, so this must be the real on-disk location.
    """
    for entry in bank.banks:
        if entry.bank_type != THETA_BANK_TYPE:
            continue
        raw = (entry.bank_path or "").strip()
        if not raw or raw == LOCAL_SENTINEL:
            raise ValueError(
                f"ClassifierBank source entry {entry.bank_id!r} is marked "
                f"{THETA_BANK_TYPE!r} but records no usable path "
                f"({entry.bank_path!r}). The θ companion cannot be located; re-export "
                "the bank with a producer that records the companion's path."
            )
        return CompanionRef(bank_id=entry.bank_id, path=(Path(bank_path).parent / raw))
    return None


#: The per-function config objects that carry generation parameters, in a stable order so
#: columns are reproducible across runs.
#:
#: **This mirrors egm-contracts; it does not invent a vocabulary.** The generation
#: functions are specified there — ``simulation_config.schema.json``'s description and
#: ``generation_params.schema.json``'s ``regime`` both enumerate *geometry / cell_model /
#: substrate / activation / electrodes / backend / label_policy* — but only in **prose**,
#: with no machine-readable list to import (contrast ``roles.json``, which single-sources
#: the artifact-role vocabulary). Until one exists this tuple is a hand-kept mirror and can
#: drift silently; see CL-144.
#:
#: ``label_policy`` is deliberately subtracted: it defines the classification *target*, not
#: a generation knob, and already rides the ClassifierBank as a bank-level identity. That
#: subtraction is a consumer policy decision and belongs here even once the vocabulary
#: itself comes from contracts.
#:
#: Note ``regime`` is an **open** key set by design — "a future strategy axis becomes a
#: regime key without a schema bump" — so a new generation function will appear in
#: artifacts before it appears here.
THETA_PREFIXES: tuple[str, ...] = (
    "geometry",
    "cell_model",
    "substrate",
    "activation",
    "electrodes",
    "backend",
)

#: Scalar leaf types that become θ columns. `bool` is deliberately included (a flag is a
#: legitimate knob) and `None` deliberately is not — an absent value is not a coordinate.
_SCALAR = (int, float, str, bool)


def declared_knob_paths(bank: _synthetic_bank_models.SyntheticBank) -> tuple[str, ...]:
    """The ``path`` of every knob the θ-spec declares as swept, in declaration order.

    Empty when the producer wrote a trivial spec, which is the current state — treat it as
    "nothing is *declared* tuned", never as "nothing varies". Use it to highlight or
    pre-select columns in a view, not to decide which columns exist.
    """
    params = getattr(bank, "generation_params", None)
    knobs = getattr(params, "knobs", None) or ()
    return tuple(str(unwrap_root(knob.path)) for knob in knobs)


def theta_frame(
    classifier_bank: ClassifierBank,
    synthetic_bank: _synthetic_bank_models.SyntheticBank,
) -> pd.DataFrame:
    """One row per ClassifierBank trace, carrying that trace's θ columns.

    Row order matches ``classifier_bank.traces``, so the result concatenates directly onto
    a view-model frame built from the same bank.

    The join itself is egm-data's (``join_traces_with_simulations``): it refuses
    mismatched banks, a trace with no ``simulation_id``, and a trace pointing at a
    simulation the source bank lacks. Those raise rather than yielding partial rows,
    because simulation ids restart at 0 in every bank — a permissive join returns
    confident, wrong pairings and no error at all.

    A bank whose simulations share one config yields constant θ columns rather than no
    columns: "this knob did not vary here" is a fact a scatter should be able to show.
    """
    paired = join_traces_with_simulations(classifier_bank, synthetic_bank)
    rows = [_theta_row(pair.simulation) for pair in paired]
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    # A `type` discriminator is regime context when constant and a real axis when it
    # varies (e.g. a sweep across substrate models), so keep only the varying ones.
    constant_types = [
        column
        for column in frame.columns
        if column.endswith(".type") and frame[column].nunique(dropna=False) <= 1
    ]
    return frame.drop(columns=constant_types)


def _theta_row(simulation: Any) -> dict[str, Any]:
    """One simulation's config flattened to ``{"<function>.<field>": scalar}``."""
    row: dict[str, Any] = {}
    for prefix in THETA_PREFIXES:
        obj = getattr(simulation, prefix, None)
        if obj is None:
            continue
        for field, value in _fields_of(obj).items():
            scalar = unwrap_root(value)
            if isinstance(scalar, _SCALAR):
                row[f"{prefix}.{field}"] = scalar
    return row


def _fields_of(obj: Any) -> dict[str, Any]:
    """The field mapping of a typed contracts model, or a plain dict unchanged.

    ``SimulationConfig`` passes the per-function objects through as the contracts models
    they already are, so this normally walks a Pydantic model; the dict branch keeps the
    function usable against a hand-built fixture.
    """
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        result: dict[str, Any] = dump()
        return result
    return {}


def unwrap_root(value: Any) -> Any:
    """Unwrap a codegen constraint-root container (a ``.root`` accessor).

    egm-contracts' codegen wraps *constrained* fields in a ``RootModel``, so a value that
    carries a ``pattern`` or ``minimum`` arrives as the wrapper rather than the value.
    Reading it without unwrapping is what put ``"root='iaf1'"`` into a shipped artifact
    (CL-136), so unwrap unconditionally rather than only where a constraint exists today.
    """
    return getattr(value, "root", value)
