"""pytest-qt tests for the Flow C paper-figure-prep view (gui/views/paper_figure_prep, B9)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from myocard_egm_data.phases import FigureSpec, load_figure_spec, write_figure_spec
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.views import PaperFigurePrepView
from myocard_egm_studio.gui.widgets import FigureForm, FigurePreview

_BANK_ID = "lpred_prep_test_2026-06-29"


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
    assert view._preview.has_image


def test_preview_shows_error_when_banks_unmapped(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """With no bank paths, resolution fails and the preview shows text, not a crash."""
    spec_path, _ = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.load_spec(spec_path)  # bank_paths still empty
    assert not view._preview.has_image
    assert _BANK_ID in view._preview._label.text()  # the unmapped id is named


def test_set_bank_paths_refreshes_a_waiting_preview(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    spec_path, bank_paths = _prepared(tmp_path, tiny_predictions_bank)
    view = PaperFigurePrepView()
    qtbot.addWidget(view)
    view.load_spec(spec_path)  # unmapped -> error
    assert not view._preview.has_image
    view.set_bank_paths(bank_paths)  # now resolvable -> image
    assert view._preview.has_image


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
