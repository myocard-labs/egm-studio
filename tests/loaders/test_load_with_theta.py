"""Tests for loaders.synthetic_bank.load_with_theta — the view-model with θ joined on.

In ``tests/loaders/`` rather than ``tests/gui/`` on purpose: the function needs no Qt, and
everything under ``tests/gui/`` is auto-marked ``gui`` and so deselected from the fast
``-m 'not gui'`` run. The θ companion is stubbed rather than written as a real
``synthetic_bank`` file — those artifacts are gitignored, and the loading half is covered
in test_synthetic_bank.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank

from myocard_egm_studio.loaders import synthetic_bank as sources


def _write(bank: ClassifierBank, tmp_path: Path) -> Path:
    path = tmp_path / "bank.classifier.h5"
    write_classifier_bank(bank, path)
    return path


def test_a_bank_with_no_generation_side_loads_without_theta(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """`has_theta` is False, not an error — an IAFDB bank legitimately has no θ."""
    path = _write(tiny_classifier_bank, tmp_path)

    frame, has_theta = sources.load_with_theta(path)

    assert has_theta is False
    assert len(frame) == tiny_classifier_bank.n_traces
    assert not any("." in str(c) for c in frame.columns)  # no <function>.<field> columns


def test_theta_columns_join_onto_the_view_model(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """θ arrives as prefixed columns, one row per trace, alongside features and metadata."""
    path = _write(tiny_classifier_bank, tmp_path)
    n = tiny_classifier_bank.n_traces

    monkeypatch.setattr(sources, "load_theta_companion", lambda _b, **_k: object())
    monkeypatch.setattr(
        sources,
        "theta_frame",
        lambda _cb, _sb: __import__("pandas").DataFrame(
            {"substrate.density": [0.3] * n, "electrodes.height_mm": [0.5] * n}
        ),
    )

    frame, has_theta = sources.load_with_theta(path)

    assert has_theta is True
    assert len(frame) == n  # still one row per trace
    assert list(frame["substrate.density"]) == [0.3] * n
    assert "peak_to_peak" in frame.columns  # features survive the concat
    assert "patient_id" in frame.columns  # so does producer metadata


def test_a_declared_but_broken_companion_raises_rather_than_reporting_no_theta(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "θ failed to load" must not read as "this bank has no θ" — that hides a real fault."""
    path = _write(tiny_classifier_bank, tmp_path)

    def _boom(_bank: object, **_kwargs: object) -> object:
        raise FileNotFoundError("companion missing")

    monkeypatch.setattr(sources, "load_theta_companion", _boom)

    with pytest.raises(FileNotFoundError):
        sources.load_with_theta(path)


def test_the_synthetic_signal_source_needs_a_companion(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    """Asking for synthetic samples on a bank that has none is a mistake, not a fallback.

    Silently serving the ClassifierBank's samples instead would mean a comparison labelled
    "synthetic source" was computed over the other one.
    """
    path = _write(tiny_classifier_bank, tmp_path)

    with pytest.raises(ValueError, match="needs a θ companion"):
        sources.load_with_theta(path, signal_source="synthetic")


def test_the_signal_source_selects_which_samples_are_featured(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both sources yield the same rows and the same θ; only the samples differ."""
    import pandas as pd

    path = _write(tiny_classifier_bank, tmp_path)
    n = tiny_classifier_bank.n_traces
    seen: list[str] = []

    monkeypatch.setattr(sources, "load_theta_companion", lambda _b, **_k: object())
    monkeypatch.setattr(
        sources, "theta_frame", lambda _cb, _sb: pd.DataFrame({"substrate.density": [0.3] * n})
    )

    def _swap(bank: ClassifierBank, _companion: object) -> ClassifierBank:
        seen.append("swapped")
        return bank

    monkeypatch.setattr(sources, "swap_in_synthetic_signals", _swap)

    classifier_frame, _ = sources.load_with_theta(path, signal_source="classifier")
    assert seen == []  # the default never reaches for the companion's samples

    synthetic_frame, has_theta = sources.load_with_theta(path, signal_source="synthetic")
    assert seen == ["swapped"]
    assert has_theta is True
    assert len(synthetic_frame) == len(classifier_frame)
    assert list(synthetic_frame["substrate.density"]) == list(classifier_frame["substrate.density"])
