"""Tests for the curated, per-bank-type field config."""

from __future__ import annotations

from myocard_egm_studio.gui.field_config import fields_for


def test_synthetic_curates_and_drops_provenance() -> None:
    specs = fields_for("synthetic_egm_pipeline", {"sim_id", "pair_index", "snr_db", "class"})
    assert [s.key for s in specs] == ["sim_id", "pair_index", "class"]  # snr_db dropped


def test_iafdb_curates_patient_channel() -> None:
    specs = fields_for("iafdb", {"patient_id", "source_channel", "start_sample", "class"})
    assert [s.key for s in specs] == [
        "patient_id",
        "source_channel",
        "class",
    ]  # start_sample dropped


def test_unknown_bank_type_falls_back_to_allowlist() -> None:
    keys = [s.key for s in fields_for("mystery", {"patient_id", "junk_field", "class"})]
    assert "patient_id" in keys
    assert "class" in keys
    assert "junk_field" not in keys  # not in the allowlist
