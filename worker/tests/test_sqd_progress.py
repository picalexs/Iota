"""Tests for the SQD progress and diagnostics boundary."""

from types import SimpleNamespace

import numpy as np

from worker.chemistry.algorithms.sqd.config import resolve_sqd_options
from worker.chemistry.algorithms.sqd import progress as sqd_progress
from worker.chemistry.algorithms.sqd import recovery as sqd_recovery
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def test_solver_keeps_progress_helpers_as_compatibility_aliases() -> None:
    assert sqd_solver._emit_sqd_progress is sqd_progress.emit_sqd_progress
    assert sqd_solver._build_recovery_trace_entry is sqd_progress.build_recovery_trace_entry
    assert (
        sqd_solver._emit_configuration_recovery_progress
        is sqd_progress.emit_configuration_recovery_progress
    )


def test_first_recovery_trace_deltas_are_unavailable_not_zero() -> None:
    sampling = SimpleNamespace(
        selected_bits=np.zeros((2, 2), dtype=int),
        raw_bitstring_matrix=np.zeros((4, 2), dtype=int),
        bitstring_matrix=np.zeros((4, 2), dtype=int),
        postselection_weight=0.5,
    )
    state = SimpleNamespace(
        last_selected_ci_summary={"selected_ci_dimension": 2, "full_sci_dimension": 4},
        last_carryover_summary={},
        best_observed_energy=-1.0,
        best_observed_iteration=1,
    )

    entry = sqd_progress.build_recovery_trace_entry(
        iteration=1,
        num_batches=2,
        requested_samples_per_batch=8,
        effective_samples_per_batch=2,
        symmetrize_spin=False,
        sampling=sampling,
        state=state,
        energy_value=-1.0,
        delta_energy=float("inf"),
        occupancy_delta=float("inf"),
    )

    assert entry["delta_energy"] is None
    assert entry["occupancy_delta"] is None
    assert entry["requested_samples_per_batch"] == 8
    assert entry["effective_samples_per_batch"] == 2


def test_progress_reports_actual_shared_spin_pool_for_balanced_inputs() -> None:
    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )
    options = resolve_sqd_options(
        {"algorithm": "sqd", "symmetrize_spin": False},
        hamiltonian,
    )
    sampling = SimpleNamespace(
        selected_bits=np.zeros((2, 4), dtype=bool),
        raw_bitstring_matrix=np.zeros((2, 4), dtype=bool),
        bitstring_matrix=np.zeros((2, 4), dtype=bool),
        postselection_weight=1.0,
    )
    state = SimpleNamespace(
        last_selected_ci_summary={"selected_ci_dimension": 2, "full_sci_dimension": 4},
        last_carryover_summary={},
        best_observed_energy=-1.0,
        best_observed_iteration=1,
        last_batch_energies=[],
    )
    events: list[dict[str, object]] = []

    sqd_recovery._emit_selected_ci_progress(
        iteration=1,
        batch_index=1,
        options=options,
        ci_summary={
            "sci_dimension": 2,
            "cap_active_for_batch": False,
            "carryover_strings_alpha": 0,
            "carryover_strings_beta": 0,
        },
        progress_callback=events.append,
    )
    sqd_progress.emit_configuration_recovery_progress(
        iteration=1,
        options=options,
        sampling=sampling,
        state=state,
        energy_value=-1.0,
        delta_energy=float("inf"),
        occupancy_delta=float("inf"),
        iter_elapsed=0.1,
        progress_callback=events.append,
    )

    assert events[0]["selected_ci_spin_symmetrized"] is True
    assert events[1]["selected_ci_spin_symmetrized"] is True
