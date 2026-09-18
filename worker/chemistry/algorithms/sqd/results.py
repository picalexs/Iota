"""SQD circuit artifacts and final result-payload normalization."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import numpy as np

from worker.chemistry.algorithms.sqd.config import SQDOptions
from worker.chemistry.circuit_artifacts import (
    circuit_artifact_downsampling_policy,
    select_sqd_artifact_iterations,
    serialize_circuit_artifact,
    serialize_legacy_circuit_preview,
)
from worker.chemistry.reference_descriptor import ReferenceDescriptor, fingerprint_circuit_metadata
from worker.chemistry.types import SQDResult

logger = logging.getLogger(__name__)


class SQDRunState(Protocol):
    """State fields required to normalize an SQD result."""

    sci_energies: list[float]
    recovery_trace: list[dict[str, Any]]
    selected_fractions: list[float]
    sampled_sizes: list[int]
    last_sampled_distribution: list[dict[str, Any]]
    last_raw_distribution: list[dict[str, Any]]
    last_accepted_distribution: list[dict[str, Any]]
    last_invalid_distribution: list[dict[str, Any]]
    last_recovered_distribution: list[dict[str, Any]]
    last_selected_stage_distribution: list[dict[str, Any]]
    last_selected_distribution: list[dict[str, Any]]
    last_sampled_circuit: Any | None
    sampled_circuits: list[tuple[int, Any]]
    selected_ci_dimensions: list[int]
    selected_ci_fractions: list[float]
    last_selected_ci_summary: dict[str, Any]
    last_batch_energies: list[float]
    best_observed_energy: float
    best_observed_iteration: int
    best_observed_spin_sq: float
    best_observed_occupancies: np.ndarray | None
    best_sampled_distribution: list[dict[str, Any]]
    best_sampling_stages: dict[str, list[dict[str, Any]]]
    best_selected_distribution: list[dict[str, Any]]
    best_selected_ci_summary: dict[str, Any]
    best_batch_energies: list[float]
    best_carryover_summary: dict[str, Any]
    occupation_history: list[dict[str, Any]]
    last_spin_sq: float
    converged: bool
    termination_reason: str | None
    previous_occupancies: np.ndarray | None
    last_carryover_summary: dict[str, Any]
    work_ledger: dict[str, int]


def serialize_sqd_circuit_preview(circuit: Any) -> dict[str, Any]:
    """Serialize a persisted SQD circuit preview for the frontend."""
    return serialize_legacy_circuit_preview(circuit, style="iqp")


def _selected_ci_regime(summary: dict[str, Any]) -> dict[str, Any]:
    """Classify selected-CI work against the full fixed-particle sector."""
    full_dimension = summary.get("full_sci_dimension")
    selected_dimension = summary.get("selected_ci_dimension", summary.get("sci_dimension"))
    if not isinstance(full_dimension, int) or not isinstance(selected_dimension, int):
        return {
            "selected_ci_regime": "unavailable",
            "full_sector_dimension": None,
            "selected_determinant_count": None,
            "selected_fraction": None,
            "classical_diagonalization_dimension": None,
            "selected_space_equals_full_sector": None,
        }

    equals_full_sector = selected_dimension >= full_dimension
    return {
        "selected_ci_regime": "full_sector" if equals_full_sector else "partial_sector",
        "full_sector_dimension": full_dimension,
        "selected_determinant_count": selected_dimension,
        "selected_fraction": selected_dimension / max(1, full_dimension),
        "classical_diagonalization_dimension": selected_dimension,
        "selected_space_equals_full_sector": equals_full_sector,
    }


def build_sqd_circuit_artifacts(
    sampled_circuits: list[tuple[int, Any]],
    *,
    total_iterations: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build per-iteration SQD artifacts with bounded full preview storage."""
    available_iterations = sorted({int(iteration) for iteration, _circuit in sampled_circuits})
    selected_iterations = set(select_sqd_artifact_iterations(total_iterations))
    stored_iterations = [
        iteration for iteration in available_iterations if iteration in selected_iterations
    ]
    policy = circuit_artifact_downsampling_policy(
        total_iterations=total_iterations,
        stored_iterations=stored_iterations,
    )
    stored_iteration_set = set(stored_iterations)
    representative_iteration = available_iterations[-1] if available_iterations else None
    artifacts: list[dict[str, Any]] = []
    for iteration, circuit in sampled_circuits:
        if iteration not in stored_iteration_set:
            continue
        artifacts.append(
            serialize_circuit_artifact(
                circuit,
                artifact_id=f"sqd.iteration.{iteration}.sampler",
                algorithm="sqd",
                role="sqd_sampling",
                label=f"Recovery iter {iteration}",
                phase="recovery",
                representative=iteration == representative_iteration,
                source="backend_sampler",
                iteration=iteration,
                downsampling={
                    "policy": policy["name"],
                    "legacy_preview_path": "sci_result_package.circuit_preview",
                },
            )
        )
    return artifacts, policy


def _build_subsampling_summary(
    options: SQDOptions,
    state: SQDRunState,
    backend: object,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    selected_ci = dict(state.last_selected_ci_summary or options.selected_ci_limit_summary)
    best_selected_ci = dict(state.best_selected_ci_summary or selected_ci)
    selected_ci.update(_selected_ci_regime(selected_ci))
    best_selected_ci.update(_selected_ci_regime(best_selected_ci))
    summary: dict[str, Any] = {
        "samples_per_batch": options.samples_per_batch,
        "num_batches": options.num_batches,
        "subsampled_batches": options.num_batches,
        "backend": backend.__class__.__name__,
        "seed": options.seed,
        "symmetrize_spin": options.symmetrize_spin,
        "carryover_threshold": round(options.carryover_threshold, 8),
    }
    if state.selected_ci_dimensions:
        summary["selected_ci"] = {
            **options.selected_ci_limit_summary,
            "mean_sci_dimension": round(float(np.mean(state.selected_ci_dimensions)), 4),
            "max_sci_dimension": int(max(state.selected_ci_dimensions)),
            "mean_selected_ci_fraction": round(float(np.mean(state.selected_ci_fractions)), 6),
        }
    if "selected_ci" in summary:
        summary["selected_ci"].update(state.last_carryover_summary)
        summary["selected_ci"].update(_selected_ci_regime(best_selected_ci))
    return summary, selected_ci, best_selected_ci


def _build_sci_result_package(
    *,
    options: SQDOptions,
    state: SQDRunState,
    iterations_executed: int,
    reported_energy: float,
    reported_iteration: int,
    sampling_source: str,
    sampling_provider: dict[str, Any] | None,
    selected_ci: dict[str, Any],
    best_selected_ci: dict[str, Any],
    circuit_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    package: dict[str, Any] = {
        "final_energy": state.sci_energies[-1],
        "best_energy": reported_energy,
        "best_iteration": reported_iteration,
        "reported_energy_source": "best_observed_sqd_iteration",
        "energy_window": [min(state.sci_energies), max(state.sci_energies)],
        "iterations": iterations_executed,
        "termination_reason": state.termination_reason,
        "energy_tol": options.energy_tol,
        "occupancies_tol": options.occupancies_tol,
        "norb": options.norb,
        "nelec": [options.num_elec_a, options.num_elec_b],
        "sampling_source": sampling_source,
        "sampling_provider": dict(sampling_provider or {}),
        "seed": options.seed,
        "min_selected_configurations": options.min_selected_configurations,
        "final_occupancies": (
            state.previous_occupancies.tolist() if state.previous_occupancies is not None else []
        ),
        "best_occupancies": (
            state.best_observed_occupancies.tolist()
            if state.best_observed_occupancies is not None
            else []
        ),
        "final_sampled_bitstring_distribution": state.last_sampled_distribution,
        "best_sampled_bitstring_distribution": state.best_sampled_distribution,
        "final_bitstring_probabilities": state.last_selected_distribution,
        "best_bitstring_probabilities": state.best_selected_distribution,
        "final_sampling_stages": {
            "raw": state.last_raw_distribution,
            "accepted": state.last_accepted_distribution,
            "invalid": state.last_invalid_distribution,
            "recovered": state.last_recovered_distribution,
            "selected": state.last_selected_stage_distribution,
        },
        "best_sampling_stages": dict(state.best_sampling_stages),
        "selected_ci": selected_ci,
        "best_selected_ci": best_selected_ci,
        "final_batch_energies": state.last_batch_energies,
        "best_batch_energies": state.best_batch_energies,
        "occupation_history": list(state.occupation_history),
        "symmetrize_spin": options.symmetrize_spin,
        "carryover_threshold": round(options.carryover_threshold, 8),
        "best_carryover": state.best_carryover_summary or state.last_carryover_summary,
        "work_ledger": dict(state.work_ledger),
    }
    if state.last_sampled_circuit is not None:
        package["circuit_preview"] = serialize_sqd_circuit_preview(state.last_sampled_circuit)
    package["reference_descriptor"] = ReferenceDescriptor(
        reference_source=(
            "hartree_fock" if sampling_source == "hf_single_determinant" else sampling_source
        ),
        preparation_path=(
            "hf_reference_circuit"
            if sampling_source == "hf_single_determinant"
            else "provided_sampling_circuit"
        ),
        execution_mode="sampler_measurement",
        target_sector={"alpha": options.num_elec_a, "beta": options.num_elec_b},
        reference_energy=None,
        circuit_fingerprint=fingerprint_circuit_metadata(circuit_artifacts)
        if circuit_artifacts
        else None,
        ansatz_name="hartree_fock" if sampling_source == "hf_single_determinant" else None,
        metadata={
            "sampling_source": sampling_source,
            "sampling_provider": dict(sampling_provider or {}),
            "state_fingerprint_status": "not_claimed_from_measurements",
        },
    ).to_metadata()
    return package


def build_sqd_result(
    *,
    backend: object,
    options: SQDOptions,
    state: SQDRunState,
    sqd_total_elapsed: float,
    sampling_source: str = "hf_single_determinant",
    sampling_provider: dict[str, Any] | None = None,
) -> SQDResult:
    """Normalize accumulated SQD state into the persisted worker result."""
    iterations_executed = len(state.sci_energies)
    if iterations_executed == 0:
        raise ValueError("SQD failed to produce any SCI energies")

    reported_energy = (
        round(float(state.best_observed_energy), 8)
        if np.isfinite(state.best_observed_energy)
        else state.sci_energies[-1]
    )
    reported_iteration = state.best_observed_iteration or iterations_executed

    logger.info(
        "SQD finished: energy=%.8f final_energy=%.8f converged=%s iterations=%d "
        "best_iteration=%d total_elapsed=%.3fs",
        reported_energy,
        state.sci_energies[-1],
        state.converged,
        iterations_executed,
        reported_iteration,
        sqd_total_elapsed,
    )

    selected_fraction = (
        float(np.mean(state.selected_fractions)) if state.selected_fractions else 0.0
    )
    mean_sampled = (
        int(round(float(np.mean(state.sampled_sizes))))
        if state.sampled_sizes
        else options.total_samples
    )
    selected_samples_estimate = int(round(selected_fraction * mean_sampled))
    latest_selected_configurations = (
        int(state.recovery_trace[-1]["accepted_samples"]) if state.recovery_trace else 0
    )
    postselection_summary: dict[str, Any] = {
        "selected_fraction": round(selected_fraction, 4),
        "selected_samples": latest_selected_configurations,
        "selected_configurations": latest_selected_configurations,
        "selected_sample_shots_estimate": selected_samples_estimate,
        "total_samples": mean_sampled,
        "min_selected_configurations": options.min_selected_configurations,
    }
    postselection_summary["electron_constraints"] = {
        "num_elec_a": options.num_elec_a,
        "num_elec_b": options.num_elec_b,
        "total": options.num_elec_a + options.num_elec_b,
    }

    subsampling_summary, selected_ci, best_selected_ci = _build_subsampling_summary(
        options, state, backend
    )
    circuit_artifacts, circuit_artifact_policy = build_sqd_circuit_artifacts(
        state.sampled_circuits,
        total_iterations=iterations_executed,
    )
    sci_result_package = _build_sci_result_package(
        options=options,
        state=state,
        iterations_executed=iterations_executed,
        reported_energy=reported_energy,
        reported_iteration=reported_iteration,
        sampling_source=sampling_source,
        sampling_provider=sampling_provider,
        selected_ci=selected_ci,
        best_selected_ci=best_selected_ci,
        circuit_artifacts=circuit_artifacts,
    )

    return SQDResult(
        algorithm="sqd",
        primary_energy=reported_energy,
        primary_iterations=iterations_executed,
        converged=state.converged,
        sci_energies=state.sci_energies,
        configuration_recovery_trace=state.recovery_trace,
        spin_diagnostics={
            "spin_sq": state.best_observed_spin_sq,
            "final_spin_sq": state.last_spin_sq,
            "spin_sq_target": options.target_spin_sq,
        },
        postselection_summary=postselection_summary,
        subsampling_summary=subsampling_summary,
        sci_result_package=sci_result_package,
        circuit_artifacts=circuit_artifacts,
        circuit_artifact_policy=circuit_artifact_policy,
        best_sci_state=state.best_sci_state,
    )
