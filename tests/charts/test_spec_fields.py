"""Tests for the shared FigureSpec field accessors (charts/matplotlib/spec_fields)."""

from __future__ import annotations

from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib.spec_fields import positive_label


def _spec(inputs: dict[str, object] | None = None) -> FigureSpec:
    payload: dict[str, object] = {
        "schema_version": "1",
        "id": "fig_spec_fields_test",
        "description": "spec field accessor test",
        "recipe": "roc-curve-multi-line",
        "output": {"format": "png", "path": "out.png"},
    }
    if inputs is not None:
        payload["inputs"] = inputs
    return FigureSpec.model_validate(payload)


def test_positive_label_default_no_inputs() -> None:
    """No inputs block at all -> default 1."""
    assert positive_label(_spec()) == 1


def test_positive_label_default_inputs_without_key() -> None:
    """inputs present but no positive_label -> default 1."""
    assert positive_label(_spec({})) == 1


def test_positive_label_override() -> None:
    """inputs.positive_label is read (from model_extra) and coerced to int."""
    assert positive_label(_spec({"positive_label": 2})) == 2
