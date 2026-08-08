"""Tests for save.phase_storage — copying artifacts into the phase folder (B17).

The point of the convention is that a phase folder can be moved, archived or handed over
whole. The movability test at the bottom is the one that would catch a regression to
absolute paths; the rest cover the mechanics that make it safe on large files.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from myocard_egm_studio.save import phase_storage
from myocard_egm_studio.save.phase_storage import CopyCancelled, copy_into_phase, phase_relative


def _file(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_producer_file_is_copied_under_the_role_subfolder(tmp_path: Path) -> None:
    source = _file(tmp_path / "producer" / "tbank_run.classifier.h5")
    phase = tmp_path / "phase_1_5"

    copy = copy_into_phase(source, phase, "training_bank")

    assert copy == phase / "banks" / "tbank_run.classifier.h5"
    assert copy.read_text(encoding="utf-8") == "x"
    assert source.exists()  # the producer's original is left alone


def test_the_recorded_path_is_relative_inside_the_phase_and_absolute_outside(
    tmp_path: Path,
) -> None:
    """The asymmetry is the convention: in-phase relative (movable), outside absolute."""
    phase = tmp_path / "phase_1_5"
    inside = _file(phase / "banks" / "b.h5")
    outside = _file(tmp_path / "elsewhere" / "b.h5")

    assert phase_relative(inside, phase) == str(Path("banks") / "b.h5")
    assert Path(phase_relative(outside, phase)).is_absolute()


def test_a_noise_bank_sidecar_travels_with_it(tmp_path: Path) -> None:
    """The .h5 carries no id of its own — copying it alone yields an unidentifiable bank."""
    source = _file(tmp_path / "producer" / "nbank_iafdb.h5")
    _file(tmp_path / "producer" / "nbank_iafdb_run_record.json", '{"bank_id": "nbank_iafdb"}')
    phase = tmp_path / "phase_1_5"

    copy = copy_into_phase(source, phase, "noise_bank")

    assert (copy.parent / "nbank_iafdb_run_record.json").exists()


def test_declared_companions_land_beside_the_copy(tmp_path: Path) -> None:
    """A bank resolves its θ / noise sources next to itself, so they must land next to it."""
    source = _file(tmp_path / "producer" / "run.classifier.h5")
    theta = _file(tmp_path / "producer" / "run_theta.synthetic.h5", "theta")
    phase = tmp_path / "phase_1_5"

    copy = copy_into_phase(source, phase, "training_bank", companions=[theta])

    assert (copy.parent / theta.name).read_text(encoding="utf-8") == "theta"


def test_a_declared_companion_that_is_missing_is_skipped(tmp_path: Path) -> None:
    """It is already unresolvable where it is; refusing to index the bank would be worse."""
    source = _file(tmp_path / "producer" / "run.classifier.h5")
    phase = tmp_path / "phase_1_5"

    copy = copy_into_phase(
        source, phase, "training_bank", companions=[tmp_path / "producer" / "absent.h5"]
    )

    assert copy.exists()
    assert not (copy.parent / "absent.h5").exists()


def test_a_companion_pointing_back_at_the_source_is_not_copied_onto_itself(
    tmp_path: Path,
) -> None:
    source = _file(tmp_path / "producer" / "run.classifier.h5", "payload")
    phase = tmp_path / "phase_1_5"

    copy = copy_into_phase(source, phase, "training_bank", companions=[source])

    assert copy.read_text(encoding="utf-8") == "payload"


def test_re_indexing_an_in_phase_file_does_not_copy_it_again(tmp_path: Path) -> None:
    """Idempotent — otherwise re-adding a 500 MB bank silently duplicates it."""
    phase = tmp_path / "phase_1_5"
    source = _file(tmp_path / "producer" / "b.h5")

    first = copy_into_phase(source, phase, "training_bank")
    first.write_text("edited", encoding="utf-8")
    second = copy_into_phase(first, phase, "training_bank")

    assert second == first
    assert first.read_text(encoding="utf-8") == "edited"  # not overwritten by a re-copy


def test_a_missing_source_raises_rather_than_indexing_nothing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        copy_into_phase(tmp_path / "absent.h5", tmp_path / "phase", "training_bank")


def test_an_unknown_role_raises_rather_than_inventing_a_subfolder(tmp_path: Path) -> None:
    source = _file(tmp_path / "b.h5")
    with pytest.raises(ValueError, match="no phase subfolder"):
        copy_into_phase(source, tmp_path / "phase", "not_a_role")


# --- large-artifact copy UX (S5c) ------------------------------------------- #
# Banks run 100-500 MB in practice. These shrink the block size instead so the chunked
# path, the cancel poll and the partial-file cleanup are all exercised on a few bytes.


@pytest.fixture
def tiny_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(phase_storage, "_CHUNK_BYTES", 4)


def test_progress_reports_cumulative_bytes_across_the_whole_set(
    tmp_path: Path, tiny_chunks: None
) -> None:
    """One scale for the bar: the bank and its sidecar are one transfer, not two."""
    source = _file(tmp_path / "producer" / "nbank.h5", "0123456789")  # 10 bytes
    _file(tmp_path / "producer" / "nbank_run_record.json", "ab")  # 2 bytes
    seen: list[tuple[int, int]] = []

    copy_into_phase(
        source, tmp_path / "phase", "noise_bank", progress=lambda d, t: seen.append((d, t))
    )

    assert {total for _done, total in seen} == {12}  # a single total, not one per file
    assert [done for done, _total in seen] == [4, 8, 10, 12]  # monotonic, ends at the total


def test_cancelling_leaves_no_partial_file_and_no_artifact(
    tmp_path: Path, tiny_chunks: None
) -> None:
    """A truncated bank under its real name is worse than no bank: nothing survives a cancel."""
    source = _file(tmp_path / "producer" / "bank.h5", "0123456789")
    phase = tmp_path / "phase"
    calls = iter([False, True])  # cancel arrives partway through the first file

    with pytest.raises(CopyCancelled):
        copy_into_phase(source, phase, "training_bank", cancelled=lambda: next(calls, True))

    assert list((phase / "banks").iterdir()) == []  # neither the file nor a .partial
    assert source.read_text(encoding="utf-8") == "0123456789"  # the original is untouched


def test_cancelling_during_a_companion_removes_the_artifact_already_copied(
    tmp_path: Path, tiny_chunks: None
) -> None:
    """Half a set is not a usable artifact — the bank goes back too, not just the sidecar."""
    source = _file(tmp_path / "producer" / "bank.h5", "0123")  # one block: completes
    companion = _file(tmp_path / "producer" / "bank_theta.h5", "456789")
    phase = tmp_path / "phase"
    calls = iter([False, False, True])

    with pytest.raises(CopyCancelled):
        copy_into_phase(
            source,
            phase,
            "training_bank",
            companions=[companion],
            cancelled=lambda: next(calls, True),
        )

    assert list((phase / "banks").iterdir()) == []


def test_a_volume_too_small_refuses_before_writing_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovering this 400 MB in is a wasted transfer; the size is knowable up front."""
    source = _file(tmp_path / "producer" / "bank.h5", "0123456789")
    phase = tmp_path / "phase"
    # Patched on shutil itself: phase_storage calls shutil.disk_usage through the module, and
    # reaching for it as phase_storage.shutil is a re-export mypy (rightly) refuses.
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda _p: SimpleNamespace(total=1024, used=0, free=1024),  # 1 KB free, well under
    )

    with pytest.raises(OSError, match="not enough free space"):
        copy_into_phase(source, phase, "training_bank")

    assert list((phase / "banks").iterdir()) == []


def test_a_completed_copy_leaves_no_partial_behind(tmp_path: Path, tiny_chunks: None) -> None:
    """The destination name only ever appears once every byte is there."""
    source = _file(tmp_path / "producer" / "bank.h5", "0123456789")
    phase = tmp_path / "phase"

    copy = copy_into_phase(source, phase, "training_bank")

    assert [path.name for path in copy.parent.iterdir()] == ["bank.h5"]
    assert copy.read_text(encoding="utf-8") == "0123456789"


def test_a_phase_folder_still_resolves_after_being_moved(tmp_path: Path) -> None:
    """The whole point of B17: relative paths survive relocation, absolute ones would not.

    Copy an artifact in, record it the way the manifest would, move the entire phase folder
    somewhere else, and resolve again. This is the test that fails if anyone reintroduces an
    absolute path for an in-phase artifact.
    """
    phase = tmp_path / "original" / "phase_1_5"
    source = _file(tmp_path / "producer" / "tbank_run.h5", "payload")

    copy = copy_into_phase(source, phase, "training_bank")
    recorded = phase_relative(copy, phase)
    assert not Path(recorded).is_absolute()

    moved = tmp_path / "somewhere_else" / "phase_1_5"
    moved.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(phase), str(moved))

    resolved = moved / recorded  # exactly how the readers resolve a manifest path
    assert resolved.exists()
    assert resolved.read_text(encoding="utf-8") == "payload"
