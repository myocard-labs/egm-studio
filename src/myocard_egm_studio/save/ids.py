"""Stable ids for the artifacts egm-studio authors (Block 10, ADR-022).

egm-studio is the one consumer that *writes* artifacts — observations (Block 10) and
figure specs (Block 9) — so it composes their ids the way the producers compose theirs:
a lowercase role prefix + a descriptor + an ISO date, validated against the
single-source egm-contracts ``ArtifactId`` pattern (never re-implemented here).
"""

from __future__ import annotations

import datetime as _dt
import re

from myocard_egm_contracts import common as _common
from pydantic import ValidationError

__all__ = ["observation_id", "slugify", "today_utc", "validate_artifact_id"]

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def today_utc() -> str:
    """Today's date (UTC) as ``YYYY-MM-DD`` — the id's date segment."""
    return _dt.datetime.now(_dt.timezone.utc).date().isoformat()


def slugify(text: str) -> str:
    """Reduce ``text`` to a ``[a-z0-9_]+`` id descriptor; empty input -> ``"untitled"``."""
    slug = _NON_SLUG.sub("_", text.strip().lower()).strip("_")
    return slug or "untitled"


def validate_artifact_id(value: str) -> str:
    """Return ``value`` if it matches the egm-contracts ``ArtifactId`` pattern, else raise.

    Mirrors the producers' ``validate_artifact_id`` — the pattern is single-sourced in
    ``egm_contracts.common.ArtifactId``, so a composed id fails fast here rather than
    deep inside the writer / model validation.
    """
    try:
        _common.ArtifactId(value)
    except ValidationError as exc:
        raise ValueError(
            f"{value!r} is not a valid stable artifact id (egm-contracts ArtifactId "
            "pattern: a lowercase role prefix, a descriptor, and an ISO date)."
        ) from exc
    return value


def observation_id(title: str, *, today: str | None = None) -> str:
    """``obs_<slug(title)>_<date>`` — a valid ArtifactId for a saved observation."""
    return validate_artifact_id(f"obs_{slugify(title)}_{today or today_utc()}")
