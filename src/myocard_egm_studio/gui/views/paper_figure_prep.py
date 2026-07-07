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
rather than a stale image or a crash.

The resolve (bank load + feature extraction) runs on a worker thread so a large bank
never freezes the window; requests coalesce to the latest and never stack, and a busy
dialog appears if one runs long. Only the resolve is off-thread — matplotlib draws back
on the main thread. Debouncing the eager form signal is B9d.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from myocard_egm_data.phases import FigureSpec, load_figure_spec, write_figure_spec
from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.figures import preview_png, render
from myocard_egm_studio.gui.widgets import FigureForm, FigurePreview
from myocard_egm_studio.loaders import BankPaths, UnmappedBankIdError, resolve_recipe_data
from myocard_egm_studio.view_model.figure_output import figure_output_path

#: Failures we expect while resolving + drawing a work-in-progress spec — shown in the
#: preview as text. Covers UnknownRecipe / LoaderNotRegistered (LookupError),
#: UnmappedBankId / bad-field (ValueError), missing bank files (OSError), and the
#: not-yet-loaded sentinel (NotImplementedError). An unexpected error still propagates.
_PREVIEW_ERRORS = (LookupError, ValueError, OSError, NotImplementedError)

#: Edits coalesce for this long before an auto-preview fires, so a burst of keystrokes /
#: spin-clicks re-renders once, not once each (ADR-019 debounce).
_DEBOUNCE_MS = 300

#: Recipes whose data resolution is heavy (per-trace egm-features extraction / raw-signal
#: loading over whole banks). Auto-preview is suppressed for these — the user drives them
#: with the explicit Refresh button (ADR-019 "manual Run for expensive operations").
_EXPENSIVE_RECIPES = frozenset({"feature-distribution-overlay", "trace-pair-gallery"})

#: Delay before a busy dialog appears, so a quick resolve doesn't flash one.
_BUSY_DELAY_MS = 250

__all__ = ["PaperFigurePrepView"]


class _ResolveSignals(QtCore.QObject):
    """Main-thread signals for :class:`_ResolveTask` (spec + result / exception)."""

    done = QtCore.Signal(object, object)  # (spec, data)
    failed = QtCore.Signal(object, object)  # (spec, exception)


class _ResolveTask(QtCore.QRunnable):
    """Resolve a spec's bank ids to recipe data off the UI thread.

    Only the *data* resolution runs here (bank load + egm-features extraction — pure
    numpy / scipy / h5py, thread-safe). Drawing stays on the main thread, so matplotlib
    is never touched off-thread. Keeping this off the UI thread is what stops a large
    bank from freezing the window (Block 9 review).
    """

    def __init__(self, spec: FigureSpec, bank_paths: BankPaths) -> None:
        super().__init__()
        self._spec = spec
        self._bank_paths = bank_paths
        self.signals = _ResolveSignals()

    def run(self) -> None:
        try:
            data = resolve_recipe_data(self._spec, self._bank_paths)
        except Exception as exc:  # thread boundary: report every failure, never crash the pool
            self.signals.failed.emit(self._spec, exc)
            return
        self.signals.done.emit(self._spec, data)


def _template_spec() -> FigureSpec:
    """A blank starting point for ``New spec`` — a cheap default recipe, no groups yet.

    The user fills in the groups (name + bank id) + tweaks; the preview prompts for a
    group until then.
    """
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_untitled",
            "description": "",
            "recipe": "prediction-histogram",
            "inputs": {"groups": []},
            "output": {"format": "pdf", "path": "out/fig_untitled.pdf"},
        }
    )


class PaperFigurePrepView(QtWidgets.QWidget):
    """Flow C main area: spec form + live preview + Open / Save / Render-full toolbar."""

    statusMessage = QtCore.Signal(str)  # to the shell status bar (export / error notices)
    figureGenerated = QtCore.Signal()  # a Render/Generate wrote the output (shell refreshes tree)
    saveRequested = QtCore.Signal(object, str)  # (FigureSpec, target) to write + index — B10h-2d

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("paperFigurePrepView")
        self._bank_paths: BankPaths = {}
        self._spec_loaded = False  # guards preview refresh before the first spec is opened
        self._current_path: Path | None = None  # last opened / saved spec path (Save default)
        self._export_path: Path | None = None  # resolved output path for the in-flight export
        self._rendering = False  # a preview resolve worker is in flight
        self._pending_preview: FigureSpec | None = None  # latest spec awaiting render (coalesced)
        self._active_tasks: list[_ResolveTask] = []  # keep workers alive until they signal
        self._busy: QtWidgets.QProgressDialog | None = None
        self._busy_pending = False
        self._busy_label = ""

        self._form = FigureForm()
        self._form.specChanged.connect(self._on_spec_changed)
        self._preview = FigurePreview()

        # Debounce the eager form signal: restart on each edit, render on settle.
        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._render_current)

        # Gate the busy dialog so a quick resolve doesn't flash one.
        self._busy_timer = QtCore.QTimer(self)
        self._busy_timer.setSingleShot(True)
        self._busy_timer.setInterval(_BUSY_DELAY_MS)
        self._busy_timer.timeout.connect(self._show_busy)

        self._new_button = QtWidgets.QPushButton("New spec")
        self._open_button = QtWidgets.QPushButton("Open spec…")
        self._save_button = QtWidgets.QPushButton("Save spec…")
        # Save into a phase folder: a menu button picks scratch vs the loaded phase (B10h-2d);
        # "Add to phase" is enabled by the shell only while a phase is open.
        self._save_target_button = QtWidgets.QPushButton("Save into…")
        self._save_target_button.setObjectName("saveFigureIntoPhase")
        self._save_menu = QtWidgets.QMenu(self._save_target_button)
        self._save_to_scratch_action = self._save_menu.addAction("Add to &scratch")
        self._save_to_scratch_action.setObjectName("saveFigureToScratch")
        self._save_to_scratch_action.triggered.connect(lambda: self._on_save_target("scratch"))
        self._save_to_phase_action = self._save_menu.addAction("Add to &phase")
        self._save_to_phase_action.setObjectName("saveFigureToPhase")
        self._save_to_phase_action.triggered.connect(lambda: self._on_save_target("phase"))
        self._save_target_button.setMenu(self._save_menu)
        self._render_button = QtWidgets.QPushButton("Render full…")
        self._auto_check = QtWidgets.QCheckBox("Auto-preview")
        self._auto_check.setChecked(True)
        self._refresh_button = QtWidgets.QPushButton("Refresh preview")
        self._new_button.clicked.connect(self.new_spec)
        self._open_button.clicked.connect(self._on_open_clicked)
        self._save_button.clicked.connect(self._on_save_clicked)
        self._render_button.clicked.connect(self.request_render)
        self._refresh_button.clicked.connect(self._render_current)
        self._auto_check.toggled.connect(self._on_auto_toggled)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 0)
        toolbar.addWidget(self._new_button)
        toolbar.addWidget(self._open_button)
        toolbar.addWidget(self._save_button)
        toolbar.addWidget(self._save_target_button)
        toolbar.addWidget(self._render_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._auto_check)  # preview controls sit at the right
        toolbar.addWidget(self._refresh_button)

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
        self._render_current()

    def set_observations(self, observation_ids: Sequence[str]) -> None:
        """Offer the loaded phase's observation ids to the form's Illustrates picker."""
        self._form.set_observations(observation_ids)

    def new_spec(self) -> None:
        """Start a blank spec from a template (the New spec button).

        Not tied to a file — the first Save prompts for a path. The preview prompts for
        a group until one is added.
        """
        spec = _template_spec()
        self._current_path = None
        self._spec_loaded = True
        self._form.set_spec(spec)
        self._render_preview(spec)

    def load_spec(self, path: Path | str, *, preview: bool = True) -> None:
        """Open a figure spec + populate the form; refresh the preview unless ``preview`` off.

        ``preview=False`` is for :meth:`generate_to_file`, which only needs the spec loaded
        so it can render — no need to also resolve + draw a preview.
        """
        spec = load_figure_spec(path)
        self._current_path = Path(path)
        self._spec_loaded = True
        self._form.set_spec(spec)  # silent — populate emits nothing
        if preview:
            self._render_preview(spec)

    def generate_to_file(self, path: Path | str) -> None:
        """Load a spec and render it to its output — the phase tree's Generate action.

        No preview (the point is the file); confirms before overwriting an existing image.
        """
        self.load_spec(path, preview=False)
        self.request_render()

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

    def _on_spec_changed(self, spec: FigureSpec) -> None:
        """A form edit: schedule a debounced auto-preview, unless suppressed.

        Auto-preview is off when the user unchecks it or when the recipe is expensive
        (:data:`_EXPENSIVE_RECIPES`) — in either case the Refresh button drives it.
        """
        if self._auto_check.isChecked() and spec.recipe not in _EXPENSIVE_RECIPES:
            self._debounce.start()  # coalesce a burst of edits into one render

    def _on_auto_toggled(self, checked: bool) -> None:
        if checked:
            self._render_current()  # catch up to edits made while auto was off

    def _render_current(self) -> None:
        """Render the form's current spec now (the Refresh button + debounce target)."""
        if self._spec_loaded:
            self._render_preview(self._form.spec())

    def _render_preview(self, spec: FigureSpec) -> None:
        """Request a preview of ``spec`` — resolved off-thread, coalesced.

        The heavy resolve (bank load + feature extraction) runs on a worker so the UI
        stays responsive; a burst of requests keeps only the latest, and a new one never
        starts while one is in flight (so renders can't stack up and freeze — Block 9
        review). Drawing happens back on the main thread in :meth:`_on_preview_resolved`.
        """
        if not self._spec_loaded:
            return
        self._pending_preview = spec
        if not self._rendering:
            self._start_preview()

    def _start_preview(self) -> None:
        assert self._pending_preview is not None
        spec = self._pending_preview
        self._pending_preview = None
        self._rendering = True
        self._begin_busy("Rendering preview…")
        self._resolve_async(spec, self._on_preview_resolved, self._on_preview_failed)

    def _on_preview_resolved(self, spec: FigureSpec, data: object) -> None:
        self._end_busy()
        try:
            png = preview_png(spec, data=data)  # matplotlib on the main thread
        except _PREVIEW_ERRORS as exc:
            self._preview.show_error(self._error_text(exc))
        else:
            self._preview.show_png(png)
        self._after_preview()

    def _on_preview_failed(self, _spec: FigureSpec, exc: Exception) -> None:
        self._end_busy()
        self._preview.show_error(self._error_text(exc))
        self._after_preview()

    def _after_preview(self) -> None:
        self._rendering = False
        if self._pending_preview is not None:  # a newer request arrived mid-render
            self._start_preview()

    def _resolve_async(
        self,
        spec: FigureSpec,
        on_done: Callable[[FigureSpec, object], None],
        on_fail: Callable[[FigureSpec, Exception], None],
    ) -> None:
        """Run ``resolve_recipe_data`` for ``spec`` on the global thread pool.

        The task is retained in ``_active_tasks`` until it signals — the pool holds only a
        C++ reference, so without a Python one the task + its signals object get GC'd and
        the cross-thread emit raises "Signal source has been deleted".
        """
        task = _ResolveTask(spec, dict(self._bank_paths))
        self._active_tasks.append(task)
        task.signals.done.connect(on_done)
        task.signals.failed.connect(on_fail)
        task.signals.done.connect(lambda *_: self._drop_task(task))
        task.signals.failed.connect(lambda *_: self._drop_task(task))
        QtCore.QThreadPool.globalInstance().start(task)

    def _drop_task(self, task: _ResolveTask) -> None:
        if task in self._active_tasks:
            self._active_tasks.remove(task)

    def _error_text(self, exc: Exception) -> str:
        if isinstance(exc, UnmappedBankIdError):
            # GUI-appropriate: bank ids resolve through the loaded phase manifest, so
            # point at Open phase rather than the CLI's --bank.
            ids = ", ".join(exc.missing)
            return (
                f"No path for bank id(s): {ids}.\n\n"
                "Bank ids resolve through the loaded phase manifest — open the phase "
                "that lists them (File ▸ Open phase), or add them to its manifest."
            )
        return str(exc)

    # ---- busy dialog (gated so a fast resolve doesn't flash one) ---------- #

    def _begin_busy(self, label: str) -> None:
        self._busy_pending = True
        self._busy_label = label
        self._busy_timer.start()

    def _show_busy(self) -> None:
        if self._busy_pending and self._busy is None:
            dialog = QtWidgets.QProgressDialog(self._busy_label, "", 0, 0, self)
            dialog.setWindowTitle("egm-studio")
            dialog.setCancelButton(None)  # resolve has no cancellation hook
            dialog.setMinimumDuration(0)
            dialog.show()
            self._busy = dialog

    def _end_busy(self) -> None:
        self._busy_pending = False
        self._busy_timer.stop()
        if self._busy is not None:
            self._busy.close()
            self._busy = None

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

    def _on_save_target(self, target: str) -> None:
        """Hand the current spec to the shell to write into ``target`` (scratch / phase) + index it."""
        if not self._spec_loaded:
            self.statusMessage.emit("New or open a figure spec first.")
            return
        self.saveRequested.emit(self._form.spec(), target)

    def save_menu(self) -> QtWidgets.QMenu:
        """The Save-into menu — the shell hooks ``aboutToShow`` to sync the phase target."""
        return self._save_menu

    def phase_save_action(self) -> QtGui.QAction:
        """The "Add to phase" action — the shell enables it only while a phase is open."""
        return self._save_to_phase_action

    def request_render(self) -> None:
        """Render full → write to the spec's own ``output.path`` (no save prompt).

        The spec already declares where the figure goes (edit the Output field to change
        it), so this renders there — resolved off-thread like the preview. Confirms first
        if that file already exists (a Regenerate that overwrites).
        """
        if not self._spec_loaded:
            return
        spec = self._form.spec()
        self._export_path = figure_output_path(spec, self._current_path)
        if self._export_path.exists() and not self._confirm_overwrite(self._export_path):
            return
        self._begin_busy("Rendering figure…")
        self._resolve_async(spec, self._on_export_resolved, self._on_export_failed)

    def _on_export_resolved(self, spec: FigureSpec, data: object) -> None:
        self._end_busy()
        try:
            written = render(spec, data=data, output_path=self._export_path, overwrite=True)
        except _PREVIEW_ERRORS as exc:
            self.statusMessage.emit(f"Render failed: {self._error_text(exc)}")
        else:
            self.statusMessage.emit(f"Rendered {written}")
            self.figureGenerated.emit()  # the tree can now offer View figure / Regenerate

    def _on_export_failed(self, _spec: FigureSpec, exc: Exception) -> None:
        self._end_busy()
        self.statusMessage.emit(f"Render failed: {self._error_text(exc)}")

    def _confirm_overwrite(self, path: Path) -> bool:
        answer = QtWidgets.QMessageBox.question(
            self,
            "Overwrite figure?",
            f"{path.name} already exists. Overwrite it?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        return answer == QtWidgets.QMessageBox.StandardButton.Yes
