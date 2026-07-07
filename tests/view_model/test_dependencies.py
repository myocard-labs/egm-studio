"""Tests for dependency-id extraction (view_model.dependencies)."""

from __future__ import annotations

from myocard_egm_data.phases import (
    EgmBankEntry,
    FigureEntry,
    ModelEntry,
    NoiseBankEntry,
    Observation,
    ObservationEntry,
    PaperEntry,
    PhaseManifest,
    TrainingRunEntry,
)

from myocard_egm_studio.view_model.dependencies import (
    dependency_closure,
    dependency_ids,
    entry_dependency_ids,
    manifest_ids,
    observation_dependency_ids,
)


def _base(entry_id: str) -> dict[str, str]:
    return {
        "id": entry_id,
        "path": f"x/{entry_id}",
        "produced_by_package": "p",
        "produced_by_version": "v0",
    }


def test_derived_bank_depends_on_source_and_model() -> None:
    entry = EgmBankEntry.model_validate(
        {
            **_base("lpred_a_2026-06-27"),
            "source_bank": "lbank_src_2026-06-01",
            "model": "model_m_2026-06-10",
        }
    )
    assert entry_dependency_ids(entry) == ["lbank_src_2026-06-01", "model_m_2026-06-10"]


def test_run_depends_on_its_bank_not_its_output_model() -> None:
    entry = TrainingRunEntry.model_validate(
        {
            **_base("run_r_2026-06-20"),
            "trained_on_bank": "lpred_a_2026-06-27",
            "produced_model": "model_m_2026-06-10",  # forward output, NOT a dependency
        }
    )
    assert entry_dependency_ids(entry) == ["lpred_a_2026-06-27"]


def test_model_depends_on_its_run() -> None:
    entry = ModelEntry.model_validate(
        {**_base("model_m_2026-06-10"), "trained_from_run": "run_r_2026-06-20"}
    )
    assert entry_dependency_ids(entry) == ["run_r_2026-06-20"]


def test_figure_depends_on_all_it_consumes() -> None:
    entry = FigureEntry.model_validate(
        {
            **_base("fig_hist_2026-07-05"),
            "consumes_banks": ["lpred_a_2026-06-27"],
            "consumes_models": ["model_m_2026-06-10"],
            "consumes_observations": ["obs_note_2026-07-01"],
        }
    )
    assert entry_dependency_ids(entry) == [
        "lpred_a_2026-06-27",
        "model_m_2026-06-10",
        "obs_note_2026-07-01",
    ]


def test_paper_depends_on_its_figures() -> None:
    entry = PaperEntry.model_validate(
        {**_base("paper_methods_v1"), "figures": ["fig_hist_2026-07-05"]}
    )
    assert entry_dependency_ids(entry) == ["fig_hist_2026-07-05"]


def test_noise_bank_and_observation_entry_have_no_entry_level_deps() -> None:
    noise = NoiseBankEntry.model_validate(_base("noise_n_2026-06-15"))
    obs_entry = ObservationEntry.model_validate(
        {**_base("obs_note_2026-07-05"), "usage_tag": "exploratory"}
    )
    assert entry_dependency_ids(noise) == []
    assert entry_dependency_ids(obs_entry) == []  # deps live in the file, not the entry


def _observation() -> Observation:
    return Observation.model_validate(
        {
            "schema_version": "1",
            "id": "obs_note_2026-07-05",
            "date": "2026-07-05",
            "title": "t",
            "description": "d",
            "references": {
                "models": ["model_m_2026-06-10"],
                "observations": ["obs_parent_2026-07-01"],
            },
            "traces": [{"bank": "lpred_a_2026-06-27", "index": 0}],
            "view_state": {"banks_loaded": ["lpred_a_2026-06-27", "lpred_b_2026-06-27"]},
        }
    )


def test_observation_deps_span_banks_models_and_parents() -> None:
    deps = observation_dependency_ids(_observation())
    # banks from view_state + traces (deduped), then models + parents
    assert deps == [
        "lpred_a_2026-06-27",
        "lpred_b_2026-06-27",
        "model_m_2026-06-10",
        "obs_parent_2026-07-01",
    ]


def test_dependency_ids_dispatches_on_entry_kind() -> None:
    obs_entry = ObservationEntry.model_validate(
        {**_base("obs_note_2026-07-05"), "usage_tag": "exploratory"}
    )
    # without the file it can't know; with it, it reads the observation's deps
    assert dependency_ids(obs_entry) == []
    assert dependency_ids(obs_entry, observation=_observation())[0] == "lpred_a_2026-06-27"


def test_dependency_closure_gathers_present_transitive_deps() -> None:
    graph = {"fig_a": ["lpred_b_2026-06-27"], "lpred_b_2026-06-27": ["lbank_c_2026-06-01"]}
    result = dependency_closure(
        graph["fig_a"],
        direct_deps=lambda i: graph.get(i, []),
        present={"lpred_b_2026-06-27", "lbank_c_2026-06-01"},
    )
    assert result == ["lpred_b_2026-06-27", "lbank_c_2026-06-01"]  # the derived bank + its source


def test_dependency_closure_keeps_only_present_ids() -> None:
    # a figure's two banks: one staged in scratch, one nowhere -> only the present one is pulled
    result = dependency_closure(
        ["lpred_here_2026-06-27", "lpred_ghost_2026-06-27"],
        direct_deps=lambda _i: [],
        present={"lpred_here_2026-06-27"},
    )
    assert result == ["lpred_here_2026-06-27"]


def test_dependency_closure_is_cycle_safe() -> None:
    graph = {"a": ["b"], "b": ["a"]}  # a pathological cycle must not loop forever
    result = dependency_closure(["a"], direct_deps=lambda i: graph.get(i, []), present={"a", "b"})
    assert sorted(result) == ["a", "b"]


def test_manifest_ids_gathers_every_section() -> None:
    manifest = PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.0,
            "status": "in_progress",
            "egm_banks": [_base("lpred_a_2026-06-27")],
            "observations": [{**_base("obs_note_2026-07-05"), "usage_tag": "exploratory"}],
        }
    )
    assert manifest_ids(manifest) == {"lpred_a_2026-06-27", "obs_note_2026-07-05"}
