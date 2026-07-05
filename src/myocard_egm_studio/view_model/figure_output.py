"""Where a figure spec's rendered image lands, and whether it's there yet (Block 9).

A figure artifact in a phase is a *spec* (``fig_*.json``); the image it renders to is a
separate file named by ``spec.output.path``. The Phase tree uses "has that image been
generated?" to decide the figure's menu — offer **View figure** only once it exists, and
label generation **Generate** vs **Regenerate**. Both the tree (existence) and the shell
(the path to open / write) resolve it through :func:`figure_output_path`, so they always
agree.

A relative ``output.path`` resolves against the spec file's own directory (not the process
CWD), so a phase's figures land predictably next to — or at a path relative to — their
specs. This matches how the GUI renders (it passes the resolved path to
:func:`figures.render`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from myocard_egm_data.phases import load_figure_spec

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec
    from myocard_egm_data.phases import PhaseManifest

__all__ = ["figure_output_exists_map", "figure_output_path"]


def figure_output_path(spec: FigureSpec, spec_path: Path | str | None = None) -> Path:
    """The file ``spec`` renders to — its ``output.path``, made absolute.

    A relative path resolves against ``spec_path``'s directory when given (the spec's own
    location); with no ``spec_path`` it is returned as-is (process-CWD-relative, the
    fallback for an unsaved spec).
    """
    out = Path(spec.output.path)
    if out.is_absolute() or spec_path is None:
        return out
    return Path(spec_path).parent / out


def figure_output_exists_map(manifest: PhaseManifest, phase_dir: Path | str) -> dict[str, bool]:
    """For each figure in ``manifest``: is its rendered image already on disk?

    Keyed by figure artifact id. A spec that can't be read counts as not-generated (its
    tree row already flags the missing / invalid spec separately).
    """
    base = Path(phase_dir)
    result: dict[str, bool] = {}
    for figure in manifest.figures or ():
        spec_path = base / figure.path
        try:
            spec = load_figure_spec(spec_path)
        except (OSError, ValueError):
            result[figure.id] = False
            continue
        result[figure.id] = figure_output_path(spec, spec_path).exists()
    return result
