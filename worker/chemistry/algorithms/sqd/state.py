"""Run-state construction and dependency loading for the SQD algorithm package."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.algorithms.sqd.recovery import SQDDependencies

logger = logging.getLogger(__name__)


@dataclass
class SQDRunState:
    """Accumulated SQD solver state across recovery iterations."""

    sci_energies: list[float] = field(default_factory=list)
    recovery_trace: list[dict[str, Any]] = field(default_factory=list)
    selected_fractions: list[float] = field(default_factory=list)
    sampled_sizes: list[int] = field(default_factory=list)
    last_sampled_distribution: list[dict[str, Any]] = field(default_factory=list)
    last_raw_distribution: list[dict[str, Any]] = field(default_factory=list)
    last_accepted_distribution: list[dict[str, Any]] = field(default_factory=list)
    last_invalid_distribution: list[dict[str, Any]] = field(default_factory=list)
    last_recovered_distribution: list[dict[str, Any]] = field(default_factory=list)
    last_selected_stage_distribution: list[dict[str, Any]] = field(default_factory=list)
    last_selected_distribution: list[dict[str, Any]] = field(default_factory=list)
    last_sampled_circuit: Any | None = None
    sampled_circuits: list[tuple[int, Any]] = field(default_factory=list)
    selected_ci_dimensions: list[int] = field(default_factory=list)
    selected_ci_fractions: list[float] = field(default_factory=list)
    last_selected_ci_summary: dict[str, Any] = field(default_factory=dict)
    last_batch_energies: list[float] = field(default_factory=list)
    best_observed_energy: float = float("inf")
    best_observed_iteration: int = 0
    best_observed_spin_sq: float = 0.0
    best_sci_state: Any | None = None
    best_observed_occupancies: np.ndarray | None = None
    best_sampled_distribution: list[dict[str, Any]] = field(default_factory=list)
    best_sampling_stages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    best_selected_distribution: list[dict[str, Any]] = field(default_factory=list)
    best_selected_ci_summary: dict[str, Any] = field(default_factory=dict)
    best_batch_energies: list[float] = field(default_factory=list)
    best_carryover_summary: dict[str, Any] = field(default_factory=dict)
    occupation_history: list[dict[str, Any]] = field(default_factory=list)
    previous_energy: float | None = None
    previous_occupancies: np.ndarray | None = None
    last_iteration_signature: tuple[Any, ...] | None = None
    last_spin_sq: float = 0.0
    converged: bool = False
    termination_reason: str | None = None
    avg_occupancies: tuple[np.ndarray, np.ndarray] | None = None
    carryover_ci_strings: tuple[np.ndarray, np.ndarray] = field(
        default_factory=lambda: (
            np.asarray([], dtype=np.int64),
            np.asarray([], dtype=np.int64),
        )
    )
    last_carryover_summary: dict[str, Any] = field(default_factory=dict)
    work_ledger: dict[str, int] = field(
        default_factory=lambda: {
            "ledger_version": 1,
            "counting_scope": "worker_observed",
            "sampler_run_attempts": 0,
            "sampler_successful_runs": 0,
            "sampler_retry_count": 0,
            "sampler_requested_shots_total": 0,
            "sampler_returned_raw_sample_rows": 0,
            "recovery_iterations": 0,
            "selected_ci_batch_solves": 0,
        }
    )


def import_sqd_dependencies() -> SQDDependencies:
    """Import qiskit-addon-sqd entrypoints used by SQD execution."""
    try:
        from qiskit_addon_sqd.configuration_recovery import recover_configurations
        from qiskit_addon_sqd.fermion import postselect_by_hamming_right_and_left, solve_fermion
        from qiskit_addon_sqd.subsampling import subsample
    except ImportError as exc:  # pragma: no cover - dependency is pinned in worker requirements
        raise RuntimeError("qiskit-addon-sqd must be installed to run SQD") from exc

    return SQDDependencies(
        recover_configurations=recover_configurations,
        postselect_by_hamming_right_and_left=postselect_by_hamming_right_and_left,
        solve_fermion=solve_fermion,
        subsample=subsample,
    )


def log_sqd_setup(options: SQDOptions) -> None:
    """Log the resolved SQD execution parameters."""
    logger.info(
        "SQD setup: norb=%d elec_a=%d elec_b=%d max_iterations=%d "
        "samples_per_batch=%d num_batches=%d total_samples=%d "
        "energy_tol=%.2e occupancies_tol=%.2e min_selected_configurations=%d "
        "selected_ci_limit=(%d,%d) symmetrize_spin=%s carryover_threshold=%.2e seed=%d",
        options.norb,
        options.num_elec_a,
        options.num_elec_b,
        options.max_iterations,
        options.samples_per_batch,
        options.num_batches,
        options.total_samples,
        options.energy_tol,
        options.occupancies_tol,
        options.min_selected_configurations,
        options.selected_ci_limits[0],
        options.selected_ci_limits[1],
        options.symmetrize_spin,
        options.carryover_threshold,
        options.seed,
    )


def initial_sqd_run_state(options: SQDOptions) -> SQDRunState:
    """Build the mutable SQD run state for the recovery loop."""
    return SQDRunState(
        # Occupations become available only after the first raw valid-sector
        # selected-CI solve. Do not hide a uniform initialization in recovery.
        avg_occupancies=None,
        last_carryover_summary={
            "carryover_threshold": round(options.carryover_threshold, 8),
            "carryover_strings_alpha": 0,
            "carryover_strings_beta": 0,
            "spin_symmetrized": not options.open_shell or options.symmetrize_spin,
            "selection_pool_mode": (
                "shared_spin_pool"
                if not options.open_shell or options.symmetrize_spin
                else "independent_spin_pools"
            ),
            "requested_spin_symmetrization": options.symmetrize_spin,
        },
    )
