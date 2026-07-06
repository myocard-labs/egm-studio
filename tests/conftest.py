"""Pytest fixtures shared across the egm-studio test suite.

Conventions:
- Pure-Python fixtures live here.
- File-backed fixtures use ``tmp_path``; no real data files in the repo.

The fixtures build tiny in-memory :class:`ClassifierBank` objects (the egm-data
v0.4.0 stable-id API: bank ids are ``ArtifactId`` strings, not integer
indices). Sized small (12 traces, T=128) so the ~O(T^2) sample-entropy pass in
``bundle.extract_all`` stays fast in the view-model tests.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest
from myocard_egm_data.banks import (
    ClassifierBank,
    ClassifierBankMetaData,
    ClassifierPrediction,
    ClassifierTrace,
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-tag every test under ``tests/gui/`` with the ``gui`` marker, so the slow
    Qt-widget tests can be deselected for a fast run (``pytest -m 'not gui'``)."""
    for item in items:
        if item.path is not None and item.path.parent.name == "gui":
            item.add_marker("gui")


#: Stable id for the fixture's single source bank (egm-contracts ArtifactId).
_FIXTURE_BANK_ID = "tbank_studio_fixture_2026-06-27"


def _trace_signal(rng: np.random.Generator, n_samples: int, label: int) -> np.ndarray:
    """Deterministic per-label trace with enough variance for feature stats.

    Healthy (0) is a low-frequency sine; fibrotic (1) adds a high-frequency
    burst — separable in the spectral + complexity features so per-class
    distribution distances are non-zero. Per-trace noise gives within-class
    spread (KDE needs >= 2 distinct values).
    """
    t = np.arange(n_samples, dtype=np.float64) / n_samples
    base = np.sin(2.0 * np.pi * 5.0 * t)
    if label == 1:
        base = base + 0.3 * np.sin(2.0 * np.pi * 40.0 * t)
    noise = rng.standard_normal(n_samples) * 0.02
    return (base + noise).astype(np.float32)


@pytest.fixture
def tiny_classifier_bank() -> ClassifierBank:
    """A 12-trace, 2-class, 6-patient labeled ClassifierBank (T=128, 1 kHz)."""
    rng = np.random.default_rng(0)
    n_samples = 128
    n_patients = 6
    traces_per_patient = 2
    traces: list[ClassifierTrace] = []
    for p in range(n_patients):
        label = p % 2
        for k in range(traces_per_patient):
            traces.append(
                ClassifierTrace(
                    bank_id=_FIXTURE_BANK_ID,
                    signal=_trace_signal(rng, n_samples, label),
                    freq_hz=1000.0,
                    amp_type="mv",
                    split=None,
                    label_truth=label,
                    prediction=None,
                    trace_metadata={
                        "patient_id": f"P{p:02d}",
                        "sim_id": p,
                        "electrode_pair_id": k,
                    },
                )
            )
    bank_md = ClassifierBankMetaData(
        bank_id=_FIXTURE_BANK_ID,
        bank_type="synthetic",
        bank_path="<in-memory fixture>",
        bank_metadata={"fixture": "tiny_classifier_bank"},
    )
    return ClassifierBank(
        banks=[bank_md],
        traces=traces,
        labels={0: "healthy", 1: "fibrotic"},
    )


@pytest.fixture
def tiny_unlabeled_bank(tiny_classifier_bank: ClassifierBank) -> ClassifierBank:
    """The labeled fixture with every ``label_truth`` cleared (the IAFDB shape)."""
    traces = [
        dataclasses.replace(t, label_truth=None, prediction=None)
        for t in tiny_classifier_bank.traces
    ]
    return dataclasses.replace(tiny_classifier_bank, traces=traces, id=None)


@pytest.fixture
def tiny_predictions_bank(tiny_classifier_bank: ClassifierBank) -> ClassifierBank:
    """The labeled fixture with a deterministic prediction per trace (an lpred_ bank).

    Each trace gets a ``ClassifierPrediction`` whose logits are pushed toward the
    truth class (+/- 1.5 plus small noise), so P(fibrotic) separates — low for
    healthy, high for fibrotic. The bank carries a predictions-bank id so it
    round-trips through ``write_classifier_bank`` / ``load_classifier_bank``.
    """
    rng = np.random.default_rng(3)
    traces: list[ClassifierTrace] = []
    for t in tiny_classifier_bank.traces:
        logit_pos = (1.5 if t.label_truth == 1 else -1.5) + float(rng.normal(0.0, 0.4))
        logits = {0: -logit_pos, 1: logit_pos}
        z = np.array([logits[0], logits[1]], dtype=np.float64)
        soft = np.exp(z - z.max())
        soft /= soft.sum()
        label_pred = int(soft[1] >= soft[0])
        prediction = ClassifierPrediction(
            label_pred=label_pred,
            label_prob=float(soft[label_pred]),
            pred_logits={0: float(logits[0]), 1: float(logits[1])},
        )
        traces.append(dataclasses.replace(t, prediction=prediction))
    return dataclasses.replace(
        tiny_classifier_bank, traces=traces, id="lpred_studio_fixture_2026-06-28"
    )


@pytest.fixture
def tiny_unlabeled_predictions_bank(tiny_predictions_bank: ClassifierBank) -> ClassifierBank:
    """The predictions fixture with every ``label_truth`` cleared (a upred_ bank).

    The IAFDB shape: predictions present, no ground truth — the adapter yields a
    single distribution (``labels=None``), no per-class split.
    """
    traces = [dataclasses.replace(t, label_truth=None) for t in tiny_predictions_bank.traces]
    return dataclasses.replace(
        tiny_predictions_bank, traces=traces, id="upred_studio_fixture_2026-06-28"
    )


@pytest.fixture(autouse=True)
def _isolated_qsettings(tmp_path: Path) -> None:
    """Redirect Qt ``QSettings`` to a per-test temp dir.

    The GUI theme preference (tests/gui) persists via ``QSettings``; without this
    every such test would read / write the developer's real ~/.config store.
    Autouse so no GUI test can forget it, and a no-op for the non-GUI tests that
    never touch ``QSettings``. ``QtCore`` is imported lazily so the pure-data tests
    don't pull in Qt just to collect.
    """
    from PySide6 import QtCore

    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(tmp_path),
    )
