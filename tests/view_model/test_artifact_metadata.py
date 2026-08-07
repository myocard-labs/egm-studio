"""Tests for file-level artifact metadata (view_model.artifact_metadata)."""

from __future__ import annotations

import types
from pathlib import Path

import numpy as np
import pytest
from myocard_egm_contracts import Role
from myocard_egm_data.banks import (
    ClassifierBank,
    ClassifierBankMetaData,
    ClassifierTrace,
    write_classifier_bank,
)

from myocard_egm_studio.view_model import artifact_metadata
from myocard_egm_studio.view_model.artifact_metadata import (
    artifact_metadata_text,
    has_metadata_view,
)

_BANK_ID = "tbank_demo_2026-01-01"

_METADATA_ROLES = {
    Role.training_bank,
    Role.pretraining_bank,
    Role.labeled_prediction_bank,
    Role.unlabeled_prediction_bank,
    Role.noise_bank,
    Role.training_run,
    Role.figure,
    Role.observation,
    Role.model,
}


def _trace(split: str, label: int) -> ClassifierTrace:
    return ClassifierTrace(
        bank_id=_BANK_ID,
        signal=np.zeros(64, dtype=np.float32),
        freq_hz=1000.0,
        amp_type="mv",
        split=split,
        label_truth=label,
        prediction=None,
        trace_metadata={"patient_id": f"P{label}"},
    )


def _write_bank(path: Path) -> None:
    bank = ClassifierBank(
        id=_BANK_ID,
        banks=[
            ClassifierBankMetaData(
                bank_id=_BANK_ID,
                bank_type="synthetic",
                bank_path="src.h5",
                # The bank-level keyset a synthetic ClassifierBank carries under
                # synthetic_bank 2.0 (CL-109): five keys, where v1.1 had 23. The
                # generation physics moved to the parallel synthetic_bank; what stays
                # is provenance (which code wrote this) plus the label policy's
                # identity, because that defines what the classification task *is*.
                bank_metadata={
                    "producer": "synthetic-egm-pipeline",
                    "producer_version": "0.4.0",
                    "description": "artifact-metadata fixture",
                    "trace_duration_ms": 64.0,  # matches the 64-sample signals at 1 kHz
                    "label_policy": "global_density",
                },
            )
        ],
        traces=[_trace("train", 1), _trace("val", 0)],
        labels={0: "healthy", 1: "fibrotic"},
    )
    write_classifier_bank(bank, path)


def test_classifier_bank_summary_reads_the_file(tmp_path: Path) -> None:
    path = tmp_path / "demo.classifier.h5"
    _write_bank(path)
    text = artifact_metadata_text(Role.training_bank, path)
    assert "traces: 2" in text
    assert "1000 Hz" in text  # sample rate
    assert "fibrotic" in text  # label name from the labels map
    assert "[synthetic]" in text  # source bank type
    # Source-specific bank_metadata still reaches the summary. label_policy is the key
    # that distinguishes a synthetic bank now: both producers keep producer /
    # producer_version (CL-109), but only synthetic carries a label policy.
    assert "label_policy" in text


def test_has_metadata_view_matches_roles() -> None:
    for role in Role:
        assert has_metadata_view(role) is (role in _METADATA_ROLES)


def test_model_metadata_shows_the_raw_json(tmp_path: Path) -> None:
    path = tmp_path / "best.model_metadata.json"
    path.write_text('{"schema_version": "1.1", "model_id": "model_demo_2026-06-26"}')
    text = artifact_metadata_text(Role.model, path)  # read directly, tolerates old versions
    assert "model_demo_2026-06-26" in text
    assert '"schema_version": "1.1"' in text  # pretty-printed as-is


def test_role_without_a_view_raises() -> None:
    with pytest.raises(ValueError):
        artifact_metadata_text(Role.paper, "anything")  # papers (dirs) have no file view


def test_noise_summary_reports_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = types.SimpleNamespace(
        schema_version="1.0",
        created_utc="2026-01-01T00:00:00Z",
        source="iafdb",
        fs_hz=1000.0,
        traces=types.SimpleNamespace(
            signal=[[0.0] * 32, [0.0] * 32],
            source_record=["rec1", "rec1"],
            source_channel=["c1", "c2"],
        ),
    )
    monkeypatch.setattr(artifact_metadata, "read_noise_bank_hdf5", lambda _path: stub)
    text = artifact_metadata_text(Role.noise_bank, tmp_path / "n.h5")
    assert "source: iafdb" in text
    assert "segments: 2" in text
    assert "1000 Hz" in text


def test_json_roles_pretty_print_the_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Stub:
        def model_dump(self, **_: object) -> dict[str, str]:
            return {"recipe": "roc-curve-multi-line", "id": "fig_demo"}

    monkeypatch.setattr(artifact_metadata, "load_figure_spec", lambda _path: _Stub())
    text = artifact_metadata_text(Role.figure, tmp_path / "f.json")
    assert '"recipe": "roc-curve-multi-line"' in text  # pretty JSON of the record
