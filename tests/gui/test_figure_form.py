"""pytest-qt tests for the Flow C curated spec form (gui/widgets/figure_form, B9)."""

from __future__ import annotations

from myocard_egm_data.phases import FigureSpec
from PySide6 import QtCore, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import FigureForm
from myocard_egm_studio.gui.widgets.figure_form import RECIPE_FIELDS


def _spec(**overrides: object) -> FigureSpec:
    raw: dict[str, object] = {
        "schema_version": "1",
        "id": "fig_form_test",
        "description": "form test spec",
        "recipe": "feature-distribution-overlay",
        "inputs": {"groups": [{"name": "Synthetic", "bank_id": "lpred_a_2026-06-29"}]},
        "styling": {"kind": "kde", "annotate": "ks", "bins": 40},
        "output": {"format": "pdf", "path": "out/fig.pdf"},
    }
    raw.update(overrides)
    return FigureSpec.model_validate(raw)


def _form(qtbot: QtBot, spec: FigureSpec | None = None) -> FigureForm:
    form = FigureForm()
    qtbot.addWidget(form)
    form.set_spec(spec if spec is not None else _spec())
    return form


def test_populates_common_fields(qtbot: QtBot) -> None:
    form = _form(qtbot)
    assert form._id_edit.text() == "fig_form_test"
    assert form._recipe_combo.currentText() == "feature-distribution-overlay"
    assert form._format_combo.currentText() == "pdf"
    assert form._groups.rows() == [("Synthetic", "lpred_a_2026-06-29")]


def test_builds_the_curated_styling_fields_for_the_recipe(qtbot: QtBot) -> None:
    form = _form(qtbot)
    keys = {spec_field.key for spec_field, _ in form._field_widgets}
    assert keys == {"kind", "annotate", "bins"}  # exactly the feature-dist knobs


def test_set_spec_does_not_emit(qtbot: QtBot) -> None:
    form = FigureForm()
    qtbot.addWidget(form)
    seen: list[object] = []
    form.specChanged.connect(seen.append)
    form.set_spec(_spec())
    assert seen == []  # populating is silent; only user edits emit


def test_editing_a_field_emits_the_updated_spec(qtbot: QtBot) -> None:
    form = _form(qtbot)
    seen: list[FigureSpec] = []
    form.specChanged.connect(seen.append)
    form._description_edit.setText("new description")
    form._description_edit.textEdited.emit(
        "new description"
    )  # setText alone doesn't fire textEdited
    assert seen and seen[-1].description == "new description"


def test_editing_a_styling_knob_updates_the_spec(qtbot: QtBot) -> None:
    form = _form(qtbot)
    bins = next(w for f, w in form._field_widgets if f.key == "bins")
    assert isinstance(bins, QtWidgets.QSpinBox)
    bins.setValue(80)  # QSpinBox.setValue fires valueChanged -> _emit
    assert (form.spec().styling or {})["bins"] == 80


def test_build_spec_reproduces_the_loaded_spec(qtbot: QtBot) -> None:
    """Loading a spec then rebuilding it yields an equal spec (no drift, no drops)."""
    original = _spec()
    form = _form(qtbot, original)
    assert form._build_spec() == original


def test_round_trip_is_idempotent(qtbot: QtBot) -> None:
    """Rebuild, reload, rebuild again — the two rebuilds match (a stable fixed point)."""
    form = _form(qtbot)
    once = form._build_spec()
    form.set_spec(once)
    twice = form._build_spec()
    assert once == twice


def test_preserves_keys_the_form_does_not_expose(qtbot: QtBot) -> None:
    """A layout.features / extra styling key the form never shows survives a rebuild."""
    spec = _spec(layout={"features": ["peak_to_peak", "sample_entropy"]})
    form = _form(qtbot, spec)
    rebuilt = form.spec()
    assert rebuilt.layout == {"features": ["peak_to_peak", "sample_entropy"]}


def test_switching_recipe_swaps_the_styling_block(qtbot: QtBot) -> None:
    form = _form(qtbot)
    form._recipe_combo.setCurrentText("roc-curve-multi-line")
    keys = {spec_field.key for spec_field, _ in form._field_widgets}
    assert keys == {"positive_label"}  # roc's only knob (lives in inputs)
    assert form.spec().recipe == "roc-curve-multi-line"


def test_data_driven_recipe_has_no_styling_block(qtbot: QtBot) -> None:
    form = _form(qtbot)
    form._recipe_combo.setCurrentText("summary-table")
    assert form._field_widgets == []
    assert not form._styling_box.isVisible()


def test_registry_only_names_registered_recipes() -> None:
    """Every RECIPE_FIELDS key is a real recipe (guards against a typo'd registry)."""
    from myocard_egm_studio.charts.matplotlib import RECIPES

    assert set(RECIPE_FIELDS).issubset(set(RECIPES))


def _illustrated_ids(form: FigureForm) -> list[str]:
    return [obs.root for obs in (form.spec().illustrates_observations or [])]


def test_illustrates_observations_round_trips(qtbot: QtBot) -> None:
    """A spec's illustrated observation is checked on load and preserved on rebuild."""
    form = FigureForm()
    qtbot.addWidget(form)
    form.set_observations(["obs_saturation_iafdb_2026-06-26", "obs_other_2026-06-27"])
    form.set_spec(_spec(illustrates_observations=["obs_saturation_iafdb_2026-06-26"]))
    assert form._illustrates.checked() == ["obs_saturation_iafdb_2026-06-26"]
    assert _illustrated_ids(form) == ["obs_saturation_iafdb_2026-06-26"]


def test_checking_an_observation_adds_it_to_the_spec(qtbot: QtBot) -> None:
    form = _form(qtbot)  # a spec with no illustrates
    form.set_observations(["obs_a_2026-06-27", "obs_b_2026-06-27"])
    assert _illustrated_ids(form) == []
    item = form._illustrates.item(1)
    assert item is not None
    item.setCheckState(QtCore.Qt.CheckState.Checked)  # user picks a link -> _emit rebuilds
    assert _illustrated_ids(form) == ["obs_b_2026-06-27"]


def test_spec_only_link_survives_when_absent_from_phase(qtbot: QtBot) -> None:
    """A spec illustrating an observation not in the phase keeps it (checked, not dropped)."""
    form = FigureForm()
    qtbot.addWidget(form)
    form.set_observations([])  # phase has no observations offered
    form.set_spec(_spec(illustrates_observations=["obs_from_another_phase_2026-06-01"]))
    assert form._illustrates.checked() == ["obs_from_another_phase_2026-06-01"]
    assert _illustrated_ids(form) == ["obs_from_another_phase_2026-06-01"]
