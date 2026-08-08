"""Tests for view_model.theta — per-trace generation parameters from the paired bank.

Fixtures are hand-built rather than real banks: the artifacts are gitignored, so the
suite cannot depend on them, and a fixture can express the shapes that matter (an empty
θ-spec beside varying configs, a single-simulation bank, a mismatched pair) without
regenerating anything.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from myocard_egm_data.banks import ClassifierBank, ClassifierTrace

from myocard_egm_studio.view_model.theta import (
    declared_knob_paths,
    theta_frame,
)

# --- fixture doubles ------------------------------------------------------- #
# The join reads `.simulations`, `.bank_id` and `.generation_params` off the synthetic
# bank and `.trace_metadata['simulation_id']` off each trace, so these stand in for the
# contracts models without pulling a real HDF5 file in.


@dataclasses.dataclass(frozen=True)
class _Sim:
    """Stands in for egm-data's SimulationConfig row view."""

    simulation_id: int
    seed: int = 0
    geometry: Any = None
    cell_model: Any = None
    substrate: Any = None
    substrate_summary: Any = None
    activation: Any = None
    electrodes: Any = None
    backend: Any = None
    label_policy: Any = None
    label_names: dict[str, str] = dataclasses.field(default_factory=dict)


def _sim(sim_id: int, *, density: float, height_mm: float = 0.5) -> _Sim:
    """One simulation whose substrate density and electrode height are the varying knobs."""
    return _Sim(
        simulation_id=sim_id,
        substrate={"type": "uniform_random_fibrosis", "density": density},
        geometry={"type": "patch_2d", "size_mm": 40.0, "anisotropy_ratio": 3.0},
        cell_model={"type": "aliev_panfilov", "ap_time_unit_ms": 1.97},
        activation={"type": "planar_edge", "voltage": 1.0, "edges": ["left"]},
        # `pairs` is per-pair detail keyed by pair_index, not a per-simulation fact.
        electrodes={
            "type": "centered_grid_2d",
            "height_mm": height_mm,
            "n_rows": 5,
            "pairs": [{"pair_index": 0, "electrode_row": 0}],
        },
        backend={"type": "finitewave", "output_fs_hz": 1000.0},
        label_policy={"type": "global_density", "thresholds": [0.1]},
    )


class _SyntheticBank:
    """Minimal stand-in: what the join and the projection actually read."""

    def __init__(self, sims: list[_Sim], *, bank_id: str, knob_paths: tuple[str, ...] = ()) -> None:
        self.bank_id = bank_id
        self._sims = sims
        self.generation_params = type(
            "_GP",
            (),
            {"knobs": [type("_K", (), {"path": p})() for p in knob_paths], "regime": {}},
        )()

    @property
    def simulations(self) -> Any:  # column-oriented, like the contracts model
        sims = self._sims
        return type(
            "_Sims",
            (),
            {
                "simulation_id": [s.simulation_id for s in sims],
                "seed": [s.seed for s in sims],
                **{
                    name: [getattr(s, name) for s in sims]
                    for name in (
                        "geometry",
                        "cell_model",
                        "substrate",
                        "substrate_summary",
                        "activation",
                        "electrodes",
                        "backend",
                        "label_policy",
                        "label_names",
                    )
                },
            },
        )()


def _classifier_bank(sim_ids: list[int], *, bank_ids: list[str]) -> ClassifierBank:
    """A ClassifierBank whose traces point at ``sim_ids`` and whose sources are ``bank_ids``."""
    import numpy as np
    from myocard_egm_data.banks import ClassifierBankMetaData

    traces = [
        ClassifierTrace(
            bank_id=bank_ids[0],
            signal=np.zeros(8, dtype=np.float32),
            freq_hz=1000.0,
            amp_type="mv",
            split=None,
            label_truth=index % 2,
            prediction=None,
            trace_metadata={"simulation_id": sim_id, "pair_index": 0, "patient_id": str(sim_id)},
        )
        for index, sim_id in enumerate(sim_ids)
    ]
    return ClassifierBank(
        id=bank_ids[0],
        banks=[
            ClassifierBankMetaData(
                bank_id=bid,
                bank_type="synthetic_egm_pipeline",
                bank_path="<local>",
                bank_metadata={},
            )
            for bid in bank_ids
        ],
        traces=traces,
        labels={0: "healthy", 1: "fibrotic"},
    )


# --- the finding this module exists for ------------------------------------ #


def test_theta_columns_come_from_the_config_not_the_declared_knobs() -> None:
    """An empty θ-spec must not mean zero θ columns — the configs are authoritative.

    This is the shipped state today: SEP12 writes ``"knobs": []`` because the sweep is
    still to come, while the per-simulation configs genuinely differ. A projection driven
    off ``generation_params.knobs`` would emit nothing here, which is precisely the
    variation the feature-vs-θ scatter exists to plot.
    """
    sims = [_sim(0, density=0.1), _sim(1, density=0.4)]
    synth: Any = _SyntheticBank(sims, bank_id="tbank_x_theta", knob_paths=())
    bank = _classifier_bank([0, 1, 0], bank_ids=["tbank_x", "tbank_x_theta"])

    frame = theta_frame(bank, synth)

    assert declared_knob_paths(synth) == ()  # nothing declared...
    assert list(frame["substrate.density"]) == [0.1, 0.4, 0.1]  # ...but the values are there
    assert len(frame) == 3  # one row per trace, in bank order


def test_declared_knobs_are_reported_but_do_not_limit_the_columns() -> None:
    """When the θ-spec is populated it annotates; it never narrows what is projected."""
    sims = [_sim(0, density=0.1), _sim(1, density=0.4)]
    synth: Any = _SyntheticBank(sims, bank_id="tbank_x_theta", knob_paths=("substrate.density",))
    bank = _classifier_bank([0, 1], bank_ids=["tbank_x", "tbank_x_theta"])

    frame = theta_frame(bank, synth)

    assert declared_knob_paths(synth) == ("substrate.density",)
    assert "substrate.density" in frame.columns
    assert "geometry.size_mm" in frame.columns  # undeclared, still projected


# --- what becomes a column -------------------------------------------------- #


def test_scalars_become_columns_and_structures_do_not() -> None:
    """Scalar leaves are scatter axes; lists and nested objects are not."""
    synth: Any = _SyntheticBank([_sim(0, density=0.3)], bank_id="tbank_x_theta")
    bank = _classifier_bank([0], bank_ids=["tbank_x", "tbank_x_theta"])

    columns = set(theta_frame(bank, synth).columns)

    assert {"substrate.density", "electrodes.height_mm", "geometry.anisotropy_ratio"} <= columns
    assert "electrodes.pairs" not in columns  # per-pair detail, keyed by pair_index
    assert "activation.edges" not in columns  # a list is not an axis
    assert not any(c.startswith("label_policy") for c in columns)  # the target, not a knob


def test_a_constant_variant_discriminator_is_dropped_but_a_varying_one_is_kept() -> None:
    """`type` names the variant: regime context when constant, a real axis when swept."""
    same: Any = _SyntheticBank(
        [_sim(0, density=0.1), _sim(1, density=0.4)], bank_id="tbank_x_theta"
    )
    bank = _classifier_bank([0, 1], bank_ids=["tbank_x", "tbank_x_theta"])
    assert "substrate.type" not in theta_frame(bank, same).columns

    swept = [_sim(0, density=0.1), _sim(1, density=0.4)]
    swept[1] = dataclasses.replace(swept[1], substrate={"type": "patchy_fibrosis", "density": 0.4})
    varied: Any = _SyntheticBank(swept, bank_id="tbank_x_theta")
    assert "substrate.type" in theta_frame(bank, varied).columns


def test_a_single_simulation_bank_yields_constant_theta_not_no_theta() -> None:
    """ "This knob did not vary here" is a fact a scatter should be able to show."""
    synth: Any = _SyntheticBank([_sim(0, density=0.25)], bank_id="tbank_x_theta")
    bank = _classifier_bank([0, 0, 0], bank_ids=["tbank_x", "tbank_x_theta"])

    frame = theta_frame(bank, synth)

    assert list(frame["substrate.density"]) == [0.25, 0.25, 0.25]


# --- the join's refusals ---------------------------------------------------- #


def test_a_mismatched_pair_is_refused_rather_than_silently_joined() -> None:
    """Simulation ids restart at 0 in every bank, so a permissive join is confidently wrong."""
    synth: Any = _SyntheticBank([_sim(0, density=0.3)], bank_id="tbank_other_theta")
    bank = _classifier_bank([0], bank_ids=["tbank_x", "tbank_x_theta"])

    with pytest.raises(ValueError, match="not among"):
        theta_frame(bank, synth)


def test_a_trace_pointing_at_an_absent_simulation_is_refused() -> None:
    synth: Any = _SyntheticBank([_sim(0, density=0.3)], bank_id="tbank_x_theta")
    bank = _classifier_bank([0, 7], bank_ids=["tbank_x", "tbank_x_theta"])

    with pytest.raises(ValueError):
        theta_frame(bank, synth)
