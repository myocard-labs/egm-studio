"""Tests for the ``summary-table`` matplotlib recipe.

A snapshot (a small key/value table) plus logic over an in-memory TableData. The
curation-summary data build lives in the loader (tested in
tests/figures/test_loaders.py); here we check the recipe renders the grid +
header + title and guards empty / ragged input.
"""

from __future__ import annotations

import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib.inputs import TableData
from myocard_egm_studio.charts.matplotlib.summary_table import summary_table

_TOL = 20.0


def _spec() -> FigureSpec:
    """Minimal valid summary-table FigureSpec (the recipe is data-driven)."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_summary_table_test",
            "description": "summary-table recipe test spec",
            "recipe": "summary-table",
            "output": {"format": "png", "path": "out.png"},
        }
    )


def _table() -> TableData:
    return TableData(
        columns=["Field", "Value"],
        rows=[
            ["Source", "iafdb v1.0.0"],
            ["Patients", "8"],
            ["Segments", "66,355"],
            ["Threshold", "percentile (bottom 20%)"],
        ],
        title="IAFDB curation summary",
    )


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_key_value_table() -> Figure:
    """A small key/value summary table — the F-1.5.10 shape."""
    return summary_table(_table(), _spec())


# --------------------------------------------------------------------------- #
# Logic
# --------------------------------------------------------------------------- #


def test_header_and_body_cells_rendered() -> None:
    """Every header + body cell string is present in the rendered table."""
    fig = summary_table(_table(), _spec())
    cells = {c.get_text().get_text() for c in fig.axes[0].tables[0].get_celld().values()}
    assert {"Field", "Value", "Source", "iafdb v1.0.0", "66,355"} <= cells


def test_title_present() -> None:
    """The table title is drawn."""
    fig = summary_table(_table(), _spec())
    assert fig.axes[0].get_title() == "IAFDB curation summary"


def test_no_columns_raises() -> None:
    with pytest.raises(ValueError, match="at least one column"):
        summary_table(TableData(columns=[], rows=[]), _spec())


def test_no_rows_raises() -> None:
    with pytest.raises(ValueError, match="at least one row"):
        summary_table(TableData(columns=["A"], rows=[]), _spec())


def test_ragged_rows_raise() -> None:
    """Every row must have one cell per column."""
    with pytest.raises(ValueError, match="one cell per column"):
        summary_table(TableData(columns=["A", "B"], rows=[["x"]]), _spec())
