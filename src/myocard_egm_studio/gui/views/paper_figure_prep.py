"""Flow C — paper-figure prep: edit a figure spec, preview it live, export it (Block 9).

The main-area content for figure-prep mode. A two-pane split — the curated
:class:`~gui.widgets.figure_form.FigureForm` on the left, the WYSIWYG
:class:`~gui.widgets.figure_preview.FigurePreview` on the right — over an Open / Save /
Render-full toolbar.

On every form edit (:attr:`FigureForm.specChanged`) the view resolves the spec's bank
ids to recipe data (:func:`loaders.resolve_recipe_data`, against the ``bank_paths`` the
shell supplies from the loaded phase manifest) and rasterizes it
(:func:`figures.preview_png`) into the preview — the *same* recipe the ``Render full``
export writes (:func:`figures.render`), so the preview is faithful (ADR-019). A
resolution / render failure (unmapped bank, bad field, …) shows as text in the preview
rather than a stale image or a crash. Debouncing the eager form signal is B9d.
"""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import FigureSpec, load_figure_spec, write_figure_spec
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.figures import preview_png, render
from myocard_egm_studio.gui.widgets import FigureForm, FigurePreview
from myocard_egm_studio.loaders import BankPaths, resolve_recipe_data

#: Failures we expect while resolving + drawing a work-in-progress spec — shown in the
#: preview as text. Covers UnknownRecipe / LoaderNotRegistered (LookupError),
#: UnmappedBankId / bad-field (ValueError), missing bank files (OSError), and the
#: not-yet-loaded sentinel (NotImplementedError). An unexpected error still propagates.
_PREVIEW_ERRORS = (LookupError, ValueError, OSError, NotImplementedError)

__all__ = ["PaperFigurePrepView"]


class PaperFigurePrepView(QtWidgets.QWidget):
    """Flow C main area: spec form + live preview + Open / Save / Render-full toolbar."""

    statusMessage = QtCore.Signal(str)  # to the shell status bar (export / error notices)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("paperFigurePrepView")
        self._bank_paths: BankPaths = {}
        self._spec_loaded = False  # guards preview refresh before the first spec is opened
        self._current_path: Path | None = None  # last opened / saved spec path (Save default)

        self._form = FigureForm()
        self._form.specChanged.connect(self._render_preview)
        self._preview = FigurePreview()

        self._open_button = QtWidgets.QPushButton("Open spec…")
        self._save_button = QtWidgets.QPushButton("Save spec…")
        self._render_button = QtWidgets.QPushButton("Render full…")
        self._open_button.clicked.connect(self._on_open_clicked)
        self._save_button.clicked.connect(self._on_save_clicked)
        self._render_button.clicked.connect(self._on_render_clicked)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 0)
        toolbar.addWidget(self._open_button)
        toolbar.addWidget(self._save_button)
        toolbar.addWidget(self._render_button)
        toolbar.addStretch(1)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        split.setObjectName("flowCSplitter")
        form_scroll = QtWidgets.QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(self._form)
        split.addWidget(form_scroll)
        split.addWidget(self._preview)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(split, 1)

    # ---- data source + spec I/O (testable core) -------------------------- #

    def set_bank_paths(self, bank_paths: BankPaths) -> None:
        """Set the ``{bank_id: path}`` map the preview + export resolve against.

        The shell supplies it from the loaded phase manifest
        (:func:`loaders.bank_paths_from_phase`); refreshing here re-previews a spec that
        was waiting on its banks.
        """
        self._bank_paths = dict(bank_paths)
        if self._spec_loaded:
            self._render_preview(self._form.spec())

    def load_spec(self, path: Path | str) -> None:
        """Open a figure spec, populate the form, and refresh the preview."""
        spec = load_figure_spec(path)
        self._current_path = Path(path)
        self._spec_loaded = True
        self._form.set_spec(spec)  # silent — populate emits nothing
        self._render_preview(spec)

    def save_spec(self, path: Path | str) -> Path:
        """Write the current form spec to ``path`` (round-trips via write_figure_spec)."""
        written = write_figure_spec(path, self._form.spec())
        self._current_path = Path(written)
        return written

    def render_full(self, output_path: Path | str | None = None) -> Path:
        """Export the current spec at full quality (vector PDF / PNG / SVG).

        Resolves the spec's data + calls the shared :func:`figures.render`, overwriting
        an existing output (the GUI's explicit action). Returns the written path.
        """
        spec = self._form.spec()
        data = resolve_recipe_data(spec, self._bank_paths)
        return render(spec, data=data, output_path=output_path, overwrite=True)

    # ---- preview --------------------------------------------------------- #

    def _render_preview(self, spec: FigureSpec) -> None:
        if not self._spec_loaded:
            return
        try:
            data = resolve_recipe_data(spec, self._bank_paths)
            png = preview_png(spec, data=data)
        except _PREVIEW_ERRORS as exc:
            self._preview.show_error(str(exc))
            return
        self._preview.show_png(png)

    # ---- toolbar handlers (dialogs -> core) ------------------------------ #

    def _on_open_clicked(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open figure spec", "", "Figure specs (*.json);;All files (*)"
        )
        if path:
            self.load_spec(path)

    def _on_save_clicked(self) -> None:
        if not self._spec_loaded:
            return
        start = str(self._current_path or f"{self._form.spec().id}.json")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save figure spec", start, "Figure specs (*.json)"
        )
        if path:
            self.save_spec(path)
            self.statusMessage.emit(f"Saved spec to {path}")

    def _on_render_clicked(self) -> None:
        if not self._spec_loaded:
            return
        start = str(self._current_path or self._form.spec().output.path)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Render figure", start, "Figure (*.pdf *.png *.svg)"
        )
        if not path:
            return
        try:
            written = self.render_full(path)
        except _PREVIEW_ERRORS as exc:
            self.statusMessage.emit(f"Render failed: {exc}")
            return
        self.statusMessage.emit(f"Rendered {written}")
