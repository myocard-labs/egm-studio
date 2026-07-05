"""pytest-qt tests for the Flow C paper-figure-prep view (gui/views/paper_figure_prep, B9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from myocard_egm_data.phases import FigureSpec, load_figure_spec, write_figure_spec
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.views import PaperFigurePrepView
from myocard_egm_studio.gui.views.paper_figure_prep import _DEBOUNCE_MS
from myocard_egm_studio.gui.widgets import FigureForm, FigurePreview

_BANK_ID = "lpred_prep_test_2026-06-29"


def _edit_description(view: PaperFigurePrepView, text: str) -> None:
    """Simulate a user editing the description (setText alone won't fire textEdited)."""
    view._form._description_edit.setText(text)
    view._form._description_edit.textEdited.emit(text)


def _prepared(tmp_path: Path, bank: ClassifierBank) -> tuple[Path, dict[str, str]]:
    """Write a bank + a prediction-histogram spec referencing it; return (spec path, map)."""
    bank_path = tmp_path / "preds.h5"
    write_classifier_bank(bank, bank_path)
    spec = FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_prep_test",
            "description": "prep view test spec",
            "recipe": "prediction-histogram",
            "inputs": {"groups": [{"name": "Synthetic val", "bank_id": _BANK_ID}]},
            "output": {"format": "pdf", "path": str(tmp_path / "out.pdf")},
        }
    )
    spec_path = tmp_path / "spec.json"
    write_figure_spec(spec_path, spec)
    return spec_path, {_BANK_ID: str(bank_path)}


def test_assembles_form_preview_and_toolbar(qtbot: QtBot) -> None:
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    assert isinstance(view._form, FigureForm)
    assert isinstance(view._preview, FigurePreview)
    assert view._render_button.text().startswith("Render")


def test_load_spec_populates_form_and_previews(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """A loaded spec fills the form and — with its banks mapped — draws the preview."""
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)
    assert view._form._id_edit.text() == "fig_prep_test"
    qtbot.waitUntil(lambda: view._preview.has_image)  # resolve runs on a worker thread


def test_preview_shows_error_when_banks_unmapped(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """With no bank paths, the preview shows a GUI-appropriate message (not the CLI's)."""
    spec_path, _ = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.load_spec(spec_path)  # bank_paths still empty
    qtbot.waitUntil(lambda: _BANK_ID in view._preview._label.text())
    message = view._preview._label.text()
    assert not view._preview.has_image
    assert "phase" in message.lower()  # points at Open phase
    assert "--bank" not in message  # not the CLI hint


def test_new_spec_loads_a_blank_template(qtbot: QtBot) -> None:
    """New spec populates the form with a template; the preview prompts for a group."""
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.new_spec()
    assert view._form._id_edit.text() == "fig_untitled"
    assert view._form._recipe_combo.currentText() == "prediction-histogram"
    assert view._form._groups.rows() == []
    assert not view._preview.has_image  # no groups yet


def test_set_bank_paths_refreshes_a_waiting_preview(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.load_spec(spec_path)  # unmapped -> error
    qtbot.waitUntil(lambda: _BANK_ID in view._preview._label.text())
    assert not view._preview.has_image
    view.set_bank_paths(bank_paths)  # now resolvable -> image
    qtbot.waitUntil(lambda: view._preview.has_image)


def test_save_spec_round_trips(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    spec_path, _ = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.load_spec(spec_path)
    out = tmp_path / "saved.json"
    view.save_spec(out)
    assert load_figure_spec(out) == load_figure_spec(spec_path)


def test_render_full_writes_the_output(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)
    out = tmp_path / "figure.pdf"
    written = view.render_full(out)
    assert written == out
    assert out.exists()


# --- interactivity (B9d) --------------------------------------------------- #


def test_auto_preview_debounces_then_renders(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """A form edit doesn't render immediately, but does after the debounce settles."""
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)
    qtbot.waitUntil(lambda: view._preview.has_image)  # let the initial render settle
    view._preview.clear()  # prove the edit is what re-renders

    _edit_description(view, "edited")
    assert not view._preview.has_image  # debounced — nothing yet
    qtbot.waitUntil(lambda: view._preview.has_image)  # debounce fires + worker resolves


def test_expensive_recipe_suppresses_auto_preview(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """An expensive recipe never auto-renders — the Refresh button drives it."""
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)
    qtbot.waitUntil(lambda: view._preview.has_image)  # let the initial render settle
    view._form._recipe_combo.setCurrentText("feature-distribution-overlay")
    view._preview.clear()

    _edit_description(view, "edited")
    qtbot.wait(_DEBOUNCE_MS + 200)
    assert not view._debounce.isActive()
    assert not view._preview.has_image  # auto-preview stayed off for the heavy recipe


def test_auto_off_requires_manual_refresh(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)
    qtbot.waitUntil(lambda: view._preview.has_image)  # let the initial render settle
    view._auto_check.setChecked(False)
    view._preview.clear()

    _edit_description(view, "edited")
    qtbot.wait(_DEBOUNCE_MS + 200)
    assert not view._preview.has_image  # auto off -> no render on edit
    view._refresh_button.click()
    qtbot.waitUntil(lambda: view._preview.has_image)  # manual refresh renders


def test_edit_save_reopen_reflects_the_edit(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """The roadmap round-trip: edit a field, save, reopen -> the edit is there."""
    spec_path, _ = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.load_spec(spec_path)
    _edit_description(view, "edited description")
    out = tmp_path / "edited.json"
    view.save_spec(out)
    assert load_figure_spec(out).description == "edited description"


def test_render_button_writes_to_the_spec_output_path(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """Render full writes straight to the spec's own output.path — no save prompt."""
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    out = tmp_path / "out.pdf"  # the _prepared spec's declared output.path
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)
    view._render_button.click()  # no dialog
    qtbot.waitUntil(out.exists)


def test_render_confirms_before_overwriting(
    qtbot: QtBot,
    tiny_predictions_bank: ClassifierBank,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Render/Regenerate over an existing image asks first; No leaves it untouched."""
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    out = tmp_path / "out.pdf"  # the _prepared spec's (absolute) output.path
    out.write_bytes(b"old")
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)

    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question", lambda *a, **k: QtWidgets.QMessageBox.StandardButton.No
    )
    view.request_render()
    assert out.read_bytes() == b"old"  # declined -> untouched

    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question", lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes
    )
    view.request_render()
    qtbot.waitUntil(lambda: out.read_bytes() != b"old")  # accepted -> overwritten


def test_generate_to_file_renders_without_previewing(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """The phase-tree Generate path writes the file and skips the preview."""
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    out = tmp_path / "out.pdf"
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    with qtbot.waitSignal(view.figureGenerated):
        view.generate_to_file(spec_path)  # no confirm (output absent), no preview
    assert out.exists()
    assert not view._preview.has_image


def test_overlapping_preview_requests_coalesce(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """A second request during a render is held as pending, not stacked into a new worker."""
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.set_bank_paths(bank_paths)
    view.load_spec(spec_path)  # kicks a worker; _rendering is now True
    view._render_preview(view._form.spec())  # arrives mid-render
    assert view._rendering
    assert view._pending_preview is not None  # coalesced onto the in-flight render
    qtbot.waitUntil(lambda: view._preview.has_image and not view._rendering)


def test_save_menu_emits_the_current_spec_with_its_target(qtbot: QtBot) -> None:
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.new_spec()  # a template spec is loaded
    assert view.findChild(QtWidgets.QPushButton, "saveFigureIntoPhase") is not None
    with qtbot.waitSignal(view.saveRequested) as blocker:
        view._save_to_scratch_action.trigger()
    assert isinstance(blocker.args[0], FigureSpec)  # the shell receives the spec...
    assert blocker.args[1] == "scratch"  # ...and the chosen target
    with qtbot.waitSignal(view.saveRequested) as blocker:
        view._save_to_phase_action.trigger()
    assert blocker.args[1] == "phase"


def test_save_menu_needs_a_spec_first(qtbot: QtBot) -> None:
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    seen: list[str] = []
    view.statusMessage.connect(seen.append)
    view._save_to_scratch_action.trigger()  # nothing loaded yet -> no emit, just a nudge
    assert seen and "figure spec first" in seen[-1]
