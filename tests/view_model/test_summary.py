"""Unit tests for the bank-summary view-model (view_model.summary)."""

from __future__ import annotations

import dataclasses

from myocard_egm_data.banks import ClassifierBank

from myocard_egm_studio.view_model import BankSummary, bank_summary, build_view_model


def test_summary_of_labeled_bank(tiny_classifier_bank: ClassifierBank) -> None:
    """A labeled bank reports its trace count, a class balance summing to the
    count, and single-bank provenance (id / type / amp_type)."""
    summary = bank_summary(build_view_model(tiny_classifier_bank, with_features=False))
    assert isinstance(summary, BankSummary)
    assert summary.n_traces == tiny_classifier_bank.n_traces
    assert len(summary.class_balance) == 2  # the fixture's two classes
    assert sum(count for _, count in summary.class_balance) == summary.n_traces
    assert all(name and count > 0 for name, count in summary.class_balance)
    assert summary.bank_ids == ("tbank_studio_fixture_2026-06-27",)
    assert summary.bank_types == ("synthetic",)
    assert summary.amp_type == "mv"


def test_class_balance_is_descending_by_count(tiny_classifier_bank: ClassifierBank) -> None:
    """Classes are ordered by descending count (largest class first)."""
    summary = bank_summary(build_view_model(tiny_classifier_bank, with_features=False))
    counts = [count for _, count in summary.class_balance]
    assert counts == sorted(counts, reverse=True)


def test_unlabeled_bank_collapses_to_one_class(tiny_unlabeled_bank: ClassifierBank) -> None:
    """A fully unlabeled bank (IAFDB shape) reports a single ``unlabeled`` class
    rather than raising on the null labels."""
    frame = build_view_model(tiny_unlabeled_bank, with_features=False)
    summary = bank_summary(frame)
    assert summary.class_balance == (("unlabeled", len(frame.index)),)


def test_empty_bank_summary_is_zeroed(tiny_classifier_bank: ClassifierBank) -> None:
    """An empty bank yields a zero-count summary with no provenance, not an error."""
    empty = dataclasses.replace(tiny_classifier_bank, traces=[])
    summary = bank_summary(build_view_model(empty, with_features=False))
    assert summary == BankSummary(
        n_traces=0, class_balance=(), bank_ids=(), bank_types=(), amp_type=None, splits=()
    )
