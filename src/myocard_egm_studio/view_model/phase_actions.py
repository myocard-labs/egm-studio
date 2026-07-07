"""Per-artifact context-menu actions for the Phase tree (Block 6).

The right-click menu on a phase artifact is *policy*, not Qt: which actions an
artifact offers depends only on its role (:func:`role_of`). This module owns that
policy as plain data — the tree turns it into a ``QMenu`` and the shell executes
the chosen action — keeping the widget dumb and the mapping unit-testable.

A menu has two groups, separated by a divider: role-specific **viewers**
(:func:`type_actions`) then the **info** actions (:func:`info_actions`) — Show
metadata (only for roles whose file egm-studio can summarize; see
:mod:`.artifact_metadata`), Reveal file, and Copy id. Viewers whose GUI has not
been built yet are ``available=False`` so the menu shows them greyed with a note
naming the block that delivers them — the full capability stays visible and
tracked rather than being dropped until it's implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from myocard_egm_contracts import Role


@dataclass(frozen=True)
class ArtifactAction:
    """One context-menu action. ``available=False`` -> shown disabled with ``note``."""

    id: str
    label: str
    available: bool = True
    note: str = ""  # tooltip: why it is disabled / which block delivers it


# Info actions every artifact ends with (Show metadata is added per-role below).
SHOW_METADATA = ArtifactAction("show_metadata", "Show metadata")
UNIVERSAL_ACTIONS: tuple[ArtifactAction, ...] = (
    ArtifactAction("reveal_file", "Reveal file"),
    ArtifactAction("copy_id", "Copy id"),
)

# Roles whose file egm-studio can summarize -> they get "Show metadata". Kept in
# sync with artifact_metadata._READERS by test_metadata_roles_match.
_METADATA_ROLES: frozenset[Role] = frozenset(
    {
        Role.training_bank,
        Role.pretraining_bank,
        Role.labeled_prediction_bank,
        Role.unlabeled_prediction_bank,
        Role.noise_bank,
        Role.training_run,
        Role.figure,
        Role.observation,
        Role.model,  # the model-metadata sidecar JSON is viewable
    }
)

# "Explore signal" + "View feature distributions" are wired now — the egm-bank
# roles are ClassifierBanks the Flow A view opens (to the Explore + Summary tabs
# respectively). Every other viewer is a placeholder.
_EXPLORE = ArtifactAction("explore_signal", "Explore signal")
_FEATURE_DIST = ArtifactAction("view_feature_distributions", "View feature distributions")

_INPUT_BANK = (_EXPLORE, _FEATURE_DIST)
_PREDICTION_BANK = (
    _EXPLORE,
    _FEATURE_DIST,
    ArtifactAction("view_ml_diagnostics", "View ML diagnostics"),  # wired in B8f (Flow B)
)


def figure_actions(*, output_exists: bool) -> tuple[ArtifactAction, ...]:
    """The figure viewers, tuned to whether the rendered image exists yet (B9).

    Always **Edit figure spec** (opens Flow C) + a generate action. **View figure** appears
    only once the image is on disk, and the generate action is labelled **Regenerate
    figure** then (it overwrites) rather than **Generate figure**.
    """
    actions = [ArtifactAction("edit_spec", "Edit figure spec")]
    if output_exists:
        actions.append(ArtifactAction("view_figure", "View figure"))
    actions.append(
        ArtifactAction(
            "generate_figure", "Regenerate figure" if output_exists else "Generate figure"
        )
    )
    return tuple(actions)


_VIEWERS_BY_ROLE: dict[Role, tuple[ArtifactAction, ...]] = {
    Role.training_bank: _INPUT_BANK,
    Role.pretraining_bank: _INPUT_BANK,
    Role.labeled_prediction_bank: _PREDICTION_BANK,
    Role.unlabeled_prediction_bank: _PREDICTION_BANK,
    Role.noise_bank: (
        ArtifactAction("view_noise", "View noise segments"),  # wired B10g — reads the .h5
        # ("View curation summary" removed until its run-record link is designed — B10g.)
    ),
    Role.training_run: (
        ArtifactAction("view_curves", "View training curves"),  # wired in B8f (Flow B Training)
    ),
    Role.model: (),  # no viewers wired; Show metadata + the universal info actions only.
    # (Dropped the never-built "Go to training run" + "View architecture" placeholders — a
    # model-architecture figure for the paper is an open question, likely a separate tool.)
    Role.observation: (
        ArtifactAction("open_observation", "Open observation"),  # reloads the captured view
        ArtifactAction("edit_observation", "Edit observation"),
    ),
    # Figures are dynamic: the tree calls figure_actions(output_exists=...) per artifact.
    # This default (image not generated yet) is the fallback for non-dynamic callers.
    Role.figure: figure_actions(output_exists=False),
    Role.paper: (),  # the universal "Reveal file" already opens the paper dir
}


#: Additive-when-loaded relabels (B7.8): once a bank is open, the viewers that
#: *append* say "Add" instead. "explore_signal" is deliberately absent — it always
#: replaces the loaded set, so it keeps its label.
_ADD_LABELS: dict[str, str] = {
    "view_feature_distributions": "Add feature distribution",
    "view_ml_diagnostics": "Add ML diagnostics",
}


def menu_label(action: ArtifactAction, *, add_mode: bool) -> str:
    """The action's menu label, in its ``Add`` form when ``add_mode`` (a bank is
    already loaded) and the action appends rather than replaces; else its label."""
    return _ADD_LABELS.get(action.id, action.label) if add_mode else action.label


#: The scratch-area actions, shown above the info group when the tree is a scratch tree
#: (Block 10h-2a): move the staged artifact into the loaded phase, or drop it from scratch.
_SCRATCH_ACTIONS: tuple[ArtifactAction, ...] = (
    ArtifactAction("promote_scratch", "Promote to phase"),
    ArtifactAction("delete_scratch", "Delete from scratch"),
)


def scratch_actions() -> tuple[ArtifactAction, ...]:
    """Promote to phase / Delete from scratch — the scratch tree's own actions."""
    return _SCRATCH_ACTIONS


#: The loaded-phase curation action, shown after the info group on a *phase* tree (not
#: scratch, which has Delete instead): unindex the artifact from the phase manifest. For an
#: egm-studio-authored artifact this also deletes its file; a producer pointer is unindexed
#: only, its file left in place (ADR-021). [B10g]
_MANAGEMENT_ACTIONS: tuple[ArtifactAction, ...] = (
    ArtifactAction("remove_artifact", "Remove from phase"),
)


def management_actions() -> tuple[ArtifactAction, ...]:
    """Remove from phase — the phase tree's own curation action (shown last)."""
    return _MANAGEMENT_ACTIONS


def type_actions(role: Role) -> tuple[ArtifactAction, ...]:
    """The role-specific viewer actions (may be empty); shown before the divider."""
    return _VIEWERS_BY_ROLE.get(role, ())


def info_actions(role: Role) -> tuple[ArtifactAction, ...]:
    """The info actions shown after the divider: Show metadata (readable roles only),
    then the universal Reveal file / Copy id."""
    metadata = (SHOW_METADATA,) if role in _METADATA_ROLES else ()
    return metadata + UNIVERSAL_ACTIONS


def actions_for(role: Role) -> tuple[ArtifactAction, ...]:
    """Every action a role offers, in menu order (viewers then info)."""
    return type_actions(role) + info_actions(role)


def reveal_target(base_dir: Path | str, path: str) -> Path:
    """The path to open for "Reveal file": the artifact if it is a directory, else
    its containing folder (so a file is revealed in its location)."""
    resolved = Path(base_dir) / path
    return resolved if resolved.is_dir() else resolved.parent
