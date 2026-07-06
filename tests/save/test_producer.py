"""Tests for save.producer — build a manifest entry from a loaded bank / run (B10h-2b)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from myocard_egm_data.phases import EgmBankEntry, NoiseBankEntry, TrainingRunEntry
from myocard_egm_data.records import TrainingRunRecord, write_training_run_record

from myocard_egm_studio.save import bank_entry, model_entry, noise_bank_entry, run_entry
from myocard_egm_studio.save.producer import UNKNOWN_PRODUCER


def test_bank_entry_for_an_egm_bank(tiny_classifier_bank: ClassifierBank, tmp_path: Path) -> None:
    bank = dataclasses.replace(tiny_classifier_bank, id="tbank_studio_fixture_2026-06-27")
    path = tmp_path / "bank.h5"
    write_classifier_bank(bank, path)
    entry = bank_entry(path)
    assert isinstance(entry, EgmBankEntry)
    assert entry.id == "tbank_studio_fixture_2026-06-27"
    assert entry.path == str(path)  # an absolute pointer at the producer's file
    assert entry.produced_by_package == UNKNOWN_PRODUCER  # sentinel provenance


def test_bank_entry_for_a_noise_bank(tiny_classifier_bank: ClassifierBank, tmp_path: Path) -> None:
    noise = dataclasses.replace(tiny_classifier_bank, id="nbank_studio_fixture_2026-06-15")
    path = tmp_path / "noise.h5"
    write_classifier_bank(noise, path)
    assert isinstance(bank_entry(path), NoiseBankEntry)  # nbank_ -> the noise section


def test_bank_entry_needs_a_stable_id(tiny_classifier_bank: ClassifierBank, tmp_path: Path) -> None:
    path = tmp_path / "noid.h5"
    write_classifier_bank(dataclasses.replace(tiny_classifier_bank, id=None), path)
    with pytest.raises(ValueError, match="no stable id"):
        bank_entry(path)


def _run_record() -> TrainingRunRecord:
    return TrainingRunRecord.model_validate(
        {
            "schema_version": "1.1",
            "created_utc": "2026-06-30T00:00:00Z",
            "run_id": "run_studio_fixture_2026-06-25",
            "trained_on_bank_id": "tbank_studio_fixture_2026-06-27",
            "produced_model_id": "model_studio_fixture_2026-06-26",
            "run": {},
            "config": {},
            "epochs": [
                {
                    "epoch": 1,
                    "lr": 0.001,
                    "train_loss": 0.5,
                    "val_loss": 0.55,
                    "epoch_seconds": 1.0,
                    "val_metrics": {"auroc": 0.9},
                    "val_reliability": [],
                }
            ],
            "best": {"epoch": 1, "metric": "auroc", "value": 0.9},
        }
    )


def test_run_entry_carries_its_dependency(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    write_training_run_record(path, _run_record())
    entry = run_entry(path)
    assert isinstance(entry, TrainingRunEntry)
    assert entry.id == "run_studio_fixture_2026-06-25"
    assert entry.trained_on_bank == "tbank_studio_fixture_2026-06-27"  # a real dependency edge
    assert entry.produced_model == "model_studio_fixture_2026-06-26"
    assert entry.produced_by_package == UNKNOWN_PRODUCER


def _write_json(path: Path, data: dict[str, object]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_model_entry_reads_id_and_run_from_raw_json(tmp_path: Path) -> None:
    # read straight from JSON (not the strict typed loader) so it tolerates schema-version drift
    path = _write_json(
        tmp_path / "best.model_metadata.json",
        {
            "schema_version": "1.1",  # an older version the typed loader would reject
            "model_id": "model_studio_fixture_2026-06-26",
            "training_provenance": {"run_id": "run_studio_2026-06-25"},
        },
    )
    entry = model_entry(path)
    assert entry.id == "model_studio_fixture_2026-06-26"
    assert entry.trained_from_run == "run_studio_2026-06-25"  # pulled from provenance
    assert entry.produced_by_package == UNKNOWN_PRODUCER  # sentinel provenance


def test_model_entry_without_a_run_id_leaves_it_unset(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "m.json", {"model_id": "model_studio_fixture_2026-06-26"}
    )  # no training_provenance at all
    assert model_entry(path).trained_from_run is None


def test_model_entry_needs_a_model_id(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "m.json", {"training_provenance": {}})  # id absent (old export)
    with pytest.raises(ValueError, match="no model_id"):
        model_entry(path)


def test_noise_bank_entry_reads_bank_id_from_the_record(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "noise_run.json", {"bank_id": "nbank_studio_fixture_2026-06-15"})
    entry = noise_bank_entry(path)
    assert isinstance(entry, NoiseBankEntry)
    assert entry.id == "nbank_studio_fixture_2026-06-15"  # the id is the record's bank_id
    assert entry.path == str(path)  # points at the record, not the .h5
    assert entry.produced_by_package == UNKNOWN_PRODUCER


def test_noise_bank_entry_needs_a_bank_id(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "noise_run.json", {"source": "x"})  # no bank_id
    with pytest.raises(ValueError, match="no bank_id"):
        noise_bank_entry(path)
