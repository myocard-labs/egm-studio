"""Tests for save.ids — stable ids for egm-studio-authored artifacts (B10a)."""

from __future__ import annotations

import datetime as dt

import pytest

from myocard_egm_studio.save.ids import (
    observation_id,
    slugify,
    today_utc,
    validate_artifact_id,
)


def test_today_utc_is_an_iso_date() -> None:
    assert dt.date.fromisoformat(today_utc()) <= dt.date.today() + dt.timedelta(days=1)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("My Cool Note", "my_cool_note"),
        ("  Spaces & Symbols!! ", "spaces_symbols"),
        ("AF near the ostium (LSPV)", "af_near_the_ostium_lspv"),
        ("", "untitled"),
        ("!!!", "untitled"),
    ],
)
def test_slugify(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_observation_id_composes_and_validates() -> None:
    assert observation_id("My Note", today="2026-07-04") == "obs_my_note_2026-07-04"


def test_observation_id_from_messy_title_is_still_valid() -> None:
    # symbols-only title -> 'untitled' descriptor, still a valid ArtifactId
    assert observation_id("???", today="2026-07-04") == "obs_untitled_2026-07-04"


def test_validate_artifact_id_rejects_malformed() -> None:
    with pytest.raises(ValueError, match="not a valid stable artifact id"):
        validate_artifact_id("Obs No Date")
