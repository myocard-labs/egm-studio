"""Tests for save.producer — build a manifest entry from a loaded bank / run (B10h-2b)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from myocard_egm_contracts import noise_bank as noise_bank_models
from myocard_egm_data.banks import (
    ClassifierBank,
    ClassifierBankMetaData,
    write_classifier_bank,
    write_noise_bank,
)
from myocard_egm_data.phases import EgmBankEntry, NoiseBankEntry, TrainingRunEntry
from myocard_egm_data.records import TrainingRunRecord, write_training_run_record

from myocard_egm_studio.save import bank_entry, model_entry, noise_bank_entry, producer, run_entry
from myocard_egm_studio.save.producer import declared_companions


def test_bank_entry_for_an_egm_bank(tiny_classifier_bank: ClassifierBank, tmp_path: Path) -> None:
    bank = dataclasses.replace(tiny_classifier_bank, id="tbank_studio_fixture_2026-06-27")
    path = tmp_path / "bank.h5"
    write_classifier_bank(bank, path)
    entry = bank_entry(path)
    assert isinstance(entry, EgmBankEntry)
    assert entry.id == "tbank_studio_fixture_2026-06-27"
    assert entry.path == str(path)  # an absolute pointer at the producer's file
    assert entry.produced_by_package is None  # provenance omitted, not invented (B19)


def test_bank_entry_routes_an_nbank_id_to_the_noise_section(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``bank_entry`` sends an ``nbank_`` id to NoiseBankEntry rather than EgmBankEntry.

    The bank is built in memory and the loader patched, because egm-data v0.6.0's
    id-content check now refuses to *write* a ClassifierBank carrying an ``nbank_`` id —
    ``nbank_`` is not one of the four ClassifierBank roles. That check is right, and it
    makes this branch of ``bank_entry`` unreachable through any legal artifact; see the
    note in the S1 hand-off about removing it.
    """
    path = tmp_path / "noise.h5"
    write_classifier_bank(dataclasses.replace(tiny_classifier_bank, id=None), path)
    noise = dataclasses.replace(tiny_classifier_bank, id="nbank_studio_fixture_2026-06-15")
    monkeypatch.setattr(producer, "load_classifier_bank", lambda _path: noise)
    assert isinstance(bank_entry(path), NoiseBankEntry)


def test_bank_entry_needs_a_stable_id(tiny_classifier_bank: ClassifierBank, tmp_path: Path) -> None:
    path = tmp_path / "noid.h5"
    write_classifier_bank(dataclasses.replace(tiny_classifier_bank, id=None), path)
    with pytest.raises(ValueError, match="no stable id"):
        bank_entry(path)


def _run_record() -> TrainingRunRecord:
    return TrainingRunRecord.model_validate(
        {
            "schema_version": "1.2",
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
    assert entry.produced_by_package is None


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
    assert entry.produced_by_package is None  # provenance omitted, not invented (B19)


def test_model_entry_without_a_run_id_leaves_it_unset(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "m.json", {"model_id": "model_studio_fixture_2026-06-26"}
    )  # no training_provenance at all
    assert model_entry(path).trained_from_run is None


def test_model_entry_needs_a_model_id(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "m.json", {"training_provenance": {}})  # id absent (old export)
    with pytest.raises(ValueError, match="no model_id"):
        model_entry(path)


def _write_noise_bank(path: Path, *, bank_id: str) -> Path:
    """A real (tiny) noise-bank ``.h5`` through egm-data's writer.

    Real rather than a dummy byte-string because B20 makes the ``.h5`` the *primary* id source,
    so ``noise_bank_entry`` now opens it. egm-data's writer refuses to write without a
    ``bank_id``, which is why the id-less cases below stub the reader instead — a pre-B20 bank
    cannot be produced through the current API, and that file-format concern is egm-data's to
    cover anyway. What this suite owns is the **precedence** between the two id sources.
    """
    bank = noise_bank_models.NoiseBank.model_validate(
        {
            "schema_version": "1.1",
            "created_utc": "2026-08-08T00:00:00Z",
            "bank_id": bank_id,
            "source": "iafdb v1.0.0",
            "fs_hz": 1000.0,
            "traces": {
                "signal": [[0.0] * 8, [0.1] * 8],
                "source_record": ["r1", "r1"],
                "source_channel": ["c1", "c2"],
            },
        }
    )
    write_noise_bank(bank, path)
    return path


def _sidecar(h5: Path, bank_id: object) -> Path:
    """The ``<stem>_run_record.json`` beside ``h5`` (the iafdb export convention)."""
    return _write_json(
        h5.with_name(h5.stem + "_run_record.json"),
        {} if bank_id is None else {"bank_id": bank_id},
    )


def _stub_bank_id(monkeypatch: pytest.MonkeyPatch, bank_id: str | None) -> None:
    """Make the ``.h5`` read report ``bank_id`` — stands in for a bank written before B20."""
    monkeypatch.setattr(
        producer, "read_noise_bank_hdf5", lambda _p: SimpleNamespace(bank_id=bank_id)
    )


def test_noise_bank_entry_takes_the_id_from_the_bank_itself(tmp_path: Path) -> None:
    """B20: the artifact carries its own identity; no sidecar is needed to index it."""
    h5 = _write_noise_bank(tmp_path / "nbank_iafdb.h5", bank_id="nbank_studio_fixture_2026-06-15")

    entry = noise_bank_entry(h5)

    assert isinstance(entry, NoiseBankEntry)
    assert entry.id == "nbank_studio_fixture_2026-06-15"
    assert entry.path == str(h5)  # the entry points at the .h5 (where the segments live)
    assert entry.produced_by_package is None


def test_a_sidecar_without_an_id_no_longer_blocks_a_bank_that_has_one(tmp_path: Path) -> None:
    """The sidecar is a fallback now, so its silence says nothing about the bank."""
    h5 = _write_noise_bank(tmp_path / "nbank_iafdb.h5", bank_id="nbank_studio_fixture_2026-06-15")
    _sidecar(h5, None)

    assert noise_bank_entry(h5).id == "nbank_studio_fixture_2026-06-15"


def test_a_pre_b20_bank_still_takes_its_id_from_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Banks written before the root attr existed are still indexable, not orphaned."""
    h5 = _write_noise_bank(tmp_path / "nbank_iafdb.h5", bank_id="nbank_studio_fixture_2026-06-15")
    _sidecar(h5, "nbank_legacy_fixture_2026-06-15")
    _stub_bank_id(monkeypatch, None)

    assert noise_bank_entry(h5).id == "nbank_legacy_fixture_2026-06-15"


def test_a_bank_and_sidecar_naming_different_banks_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mis-paired provenance is worse than none: it reads as present while describing other data."""
    h5 = _write_noise_bank(tmp_path / "nbank_iafdb.h5", bank_id="nbank_studio_fixture_2026-06-15")
    _sidecar(h5, "nbank_someone_else_2026-06-15")
    _stub_bank_id(monkeypatch, "nbank_studio_fixture_2026-06-15")

    with pytest.raises(ValueError, match="does not match its run record"):
        noise_bank_entry(h5)


def test_noise_bank_entry_needs_an_id_from_one_side_or_the_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h5 = _write_noise_bank(tmp_path / "nbank_iafdb.h5", bank_id="nbank_studio_fixture_2026-06-15")
    _stub_bank_id(monkeypatch, None)  # no root attr, and no sidecar beside it

    with pytest.raises(ValueError, match="carries no bank_id"):
        noise_bank_entry(h5)


def test_a_file_that_is_not_a_run_record_says_so_instead_of_dumping_validation_errors(
    tmp_path: Path,
) -> None:
    """The mis-pick this exists for: a noise sidecar is *also* named ..._run_record.json (FB-26).

    Letting the schema's complaints through produced fifteen pydantic errors about a file that
    was never a training run, under advice to re-generate it.
    """
    sidecar = _write_json(
        tmp_path / "nbank_iafdb_run_record.json",
        {"bank_id": "nbank_studio_fixture_2026-06-15", "fs_hz": 1000.0},
    )

    with pytest.raises(ValueError, match="could not be read as a training-run record") as caught:
        run_entry(sidecar)

    assert "index the noise bank's .h5 instead" in str(caught.value)
    assert caught.value.__cause__ is not None  # the underlying detail is chained, not discarded


def test_indexing_into_a_phase_copies_the_file_and_records_it_relatively(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """B17: the phase takes its own copy, so the folder is self-contained and movable."""
    source = tmp_path / "producer" / "bank.h5"
    source.parent.mkdir(parents=True)
    write_classifier_bank(
        dataclasses.replace(tiny_classifier_bank, id="tbank_studio_fixture_2026-06-27"), source
    )
    phase = tmp_path / "phase_1_5"

    entry = bank_entry(source, phase_dir=phase)

    assert not Path(entry.path).is_absolute()
    assert (phase / entry.path).exists()
    assert source.exists()  # the producer's original is untouched


def _source(bank_id: str, bank_type: str, bank_path: str) -> ClassifierBankMetaData:
    return ClassifierBankMetaData(
        bank_id=bank_id, bank_type=bank_type, bank_path=bank_path, bank_metadata={}
    )


def test_declared_companions_resolve_beside_the_bank(tiny_classifier_bank: ClassifierBank) -> None:
    """Only *relative* source paths are companions: they resolve nowhere else.

    ``<local>`` means "the bank you already have in hand", and an absolute path names
    something that deliberately lives elsewhere and resolves from anywhere already.
    """
    bank = dataclasses.replace(
        tiny_classifier_bank,
        banks=[
            _source("tbank_src_2026-08-08", "synthetic_egm_pipeline", "<local>"),
            _source("tbank_theta_2026-08-08", "synthetic_generation_params", "run_theta.h5"),
            _source("nbank_noise_2026-08-08", "mixer", "/elsewhere/noise.h5"),
        ],
    )

    assert declared_companions(bank, Path("/data/banks/run.classifier.h5")) == (
        Path("/data/banks/run_theta.h5"),
    )


def test_indexing_into_a_phase_brings_the_theta_companion(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """Otherwise the phase holds a bank whose θ cannot be found — caught on a real index.

    B17's promise is a self-contained phase folder, and a synthetic bank is only half an
    artifact: it points at its θ companion by a bare filename resolved beside the ``.h5``.
    """
    source = tmp_path / "producer" / "run.classifier.h5"
    source.parent.mkdir(parents=True)
    (source.parent / "run_theta.synthetic.h5").write_bytes(b"theta")
    bank = dataclasses.replace(
        tiny_classifier_bank,
        id="tbank_studio_fixture_2026-06-27",
        banks=[
            *tiny_classifier_bank.banks,
            _source(
                "tbank_studio_theta_2026-06-27",
                "synthetic_generation_params",
                "run_theta.synthetic.h5",
            ),
        ],
    )
    write_classifier_bank(bank, source)
    phase = tmp_path / "phase_1_5"

    entry = bank_entry(source, phase_dir=phase)

    assert (phase / entry.path).exists()
    assert (phase / "banks" / "run_theta.synthetic.h5").read_bytes() == b"theta"


def test_indexing_without_a_phase_keeps_an_absolute_pointer(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """Scratch is a working area, not an archive — nothing is copied into it."""
    path = tmp_path / "bank.h5"
    write_classifier_bank(
        dataclasses.replace(tiny_classifier_bank, id="tbank_studio_fixture_2026-06-27"), path
    )

    entry = bank_entry(path)

    assert Path(entry.path).is_absolute()
