"""``summary-table`` recipe — render tabular data as a publication table figure.

F-1.5.10 (the IAFDB curation summary) and other tabular figures: takes a generic
:class:`..inputs.TableData` (column headers + pre-formatted string cells) and
lays it out as a matplotlib table on an axis-less figure, sized to the content,
with a bold shaded header row. Vector PDF output is paper-embeddable.

Output is an image (PDF / PNG / SVG) like every other recipe, because the
figure_spec ``output.format`` enum is ``pdf | png | svg``. True LaTeX / markdown
*text* export would need a ``tex`` / ``md`` format added to egm-contracts'
figure_spec plus a text branch in ``figures/render`` — tracked as a follow-up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.figure import Figure

from myocard_egm_studio.charts.matplotlib.inputs import TableData
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.style import paper_style

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

_COL_WIDTH_IN = 2.6
_ROW_HEIGHT_IN = 0.34
_FIG_PAD_IN = 0.7
_FONTSIZE = 9
_ROW_SCALE = 1.5  # vertical cell scaling — matplotlib's default rows are cramped
#: Header row shading (light grey).
_HEADER_BG = "0.88"


@register("summary-table")
def summary_table(data: TableData, spec: FigureSpec) -> Figure:
    """Render the ``summary-table`` figure. See the module docstring."""
    n_cols = len(data.columns)
    if n_cols == 0:
        raise ValueError("summary-table needs at least one column.")
    if not data.rows:
        raise ValueError("summary-table needs at least one row.")
    ragged = [i for i, row in enumerate(data.rows) if len(row) != n_cols]
    if ragged:
        raise ValueError(
            f"every row must have one cell per column ({n_cols}); rows {ragged} do not."
        )

    width = _COL_WIDTH_IN * n_cols + _FIG_PAD_IN
    height = _ROW_HEIGHT_IN * (len(data.rows) + 1) + _FIG_PAD_IN  # +1 for the header row

    with paper_style():
        figure = Figure(figsize=(width, height), layout="constrained")
        ax = figure.subplots()
        ax.axis("off")
        if data.title:
            ax.set_title(data.title)
        table = ax.table(
            cellText=data.rows,
            colLabels=data.columns,
            cellLoc="left",
            loc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(_FONTSIZE)
        table.scale(1.0, _ROW_SCALE)
        for col in range(n_cols):
            header = table[0, col]  # colLabels occupy table row 0; body rows are 1..n
            header.set_text_props(fontweight="bold")
            header.set_facecolor(_HEADER_BG)
    return figure
