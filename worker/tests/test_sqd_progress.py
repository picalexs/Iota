"""Tests for the SQD progress and diagnostics boundary."""

from types import SimpleNamespace

import numpy as np

from worker.chemistry import sqd_solver
from worker.chemistry.algorithms.sqd import progress as sqd_progress


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
        symmetrize_spin=False,
        sampling=sampling,
        state=state,
        energy_value=-1.0,
        delta_energy=float("inf"),
        occupancy_delta=float("inf"),
    )

    assert entry["delta_energy"] is None
    assert entry["occupancy_delta"] is None
