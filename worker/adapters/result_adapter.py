"""Result normalization helpers."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from worker.chemistry.problem_manifest import validate_problem_manifest
from worker.chemistry.projected_subspace import projected_diagnostic_energy_is_reportable
from worker.chemistry.types import (
    AlgorithmResult,
    KQDResult,
    QFDResult,
    QSEResult,
    SKQDResult,
    SQDResult,
    VQEResult,
)


def _finite_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    return None


def _first_finite(*values: Any) -> float | None:
    """Return the first finite energy without treating zero as missing."""
    for value in values:
        finite_value = _finite_float(value)
        if finite_value is not None:
            return finite_value
    return None


def _energy_snapshot(
    final_energy: float | None,
    best_observed_energy: float | None,
    reported_energy: float | None,
    reported_energy_source: str,
) -> dict[str, Any]:
    return {
        "final_energy": final_energy if final_energy is not None else reported_energy,
        "best_observed_energy": (
            best_observed_energy if best_observed_energy is not None else reported_energy
        ),
        "reported_energy": reported_energy,
        "reported_energy_source": reported_energy_source,
    }


def _vqe_energy_provenance(result: VQEResult) -> dict[str, Any]:
    diagnostics = result.optimizer_diagnostics
    final_energy = _finite_float(diagnostics.get("final_energy"))
    if final_energy is None and result.convergence_trace:
        final_energy = _finite_float(result.convergence_trace[-1])

    best_observed_energy = _finite_float(diagnostics.get("best_observed_energy"))
    if best_observed_energy is None and result.convergence_trace:
        best_observed_energy = min(result.convergence_trace)

    reported_energy = _first_finite(result.primary_energy, best_observed_energy, final_energy)
    reported_energy_source = diagnostics.get("reported_energy_source")
    if not isinstance(reported_energy_source, str) or not reported_energy_source:
        if reported_energy is None:
            reported_energy_source = "unavailable"
        else:
            reported_energy_source = (
                "best_observed_optimizer_evaluation"
                if best_observed_energy is not None and reported_energy == best_observed_energy
                else "final_optimizer_objective"
            )
    return _energy_snapshot(
        final_energy=final_energy,
        best_observed_energy=best_observed_energy,
        reported_energy=reported_energy,
        reported_energy_source=reported_energy_source,
    )


def _sqd_energy_provenance(result: SQDResult) -> dict[str, Any]:
    final_energy = _finite_float(result.sci_result_package.get("final_energy"))
    best_observed_energy = _finite_float(result.sci_result_package.get("best_energy"))
    reported_energy = _first_finite(result.primary_energy, best_observed_energy, final_energy)
    reported_energy_source = result.sci_result_package.get(
        "reported_energy_source",
        "best_observed_sqd_iteration",
    )
    if reported_energy is None:
        reported_energy_source = "unavailable"
    return _energy_snapshot(
        final_energy=final_energy,
        best_observed_energy=best_observed_energy,
        reported_energy=reported_energy,
        reported_energy_source=reported_energy_source,
    )


def _primary_energy_provenance(
    result: AlgorithmResult,
    reported_energy_source: str,
) -> dict[str, Any]:
    return _energy_snapshot(
        final_energy=_finite_float(result.primary_energy),
        best_observed_energy=_finite_float(result.primary_energy),
        reported_energy=_finite_float(result.primary_energy),
        reported_energy_source=reported_energy_source,
    )


def _is_branch_estimator_result(result: AlgorithmResult) -> bool:
    summary = getattr(result, "matrix_element_summary", {})
    return (
        isinstance(summary, dict) and summary.get("matrix_element_strategy") == "branch_estimator"
    )


def _projected_energy_is_reportable(result: AlgorithmResult) -> bool:
    """Allow stable or reportable-diagnostic projected energies."""
    projected_result = isinstance(result, (KQDResult, QFDResult, QSEResult))
    branch_estimator = _is_branch_estimator_result(result)
    if not projected_result and not branch_estimator:
        return True

    diagnostics = _branch_stability_diagnostics(result)
    if not isinstance(diagnostics, dict) or "stability_state" not in diagnostics:
        return not branch_estimator
    return projected_diagnostic_energy_is_reportable(diagnostics)


def _branch_stability_diagnostics(result: AlgorithmResult) -> Any:
    """Return the stability diagnostics for a branch-estimator solve.

    KQD/QFD expose ``stability_summary``; QSE stores stabilized diagnostics in
    ``conditioning_summary``.
    """
    diagnostics = getattr(result, "stability_summary", None)
    if isinstance(diagnostics, dict) and diagnostics:
        return diagnostics
    return getattr(result, "conditioning_summary", {})


def _projected_energy_is_diagnostic(result: AlgorithmResult) -> bool:
    """Return whether a reportable projected energy is a rank-reduced diagnostic."""
    diagnostics = _branch_stability_diagnostics(result)
    if not isinstance(diagnostics, dict):
        return False
    if diagnostics.get("stability_state") != "stabilized":
        return False
    return int(diagnostics.get("dropped_rank", 0) or 0) > 0 or bool(
        diagnostics.get("psd_projected", False)
    )


def _skqd_energy_provenance(result: SKQDResult) -> dict[str, Any]:
    diagnostics = result.krylov_extension_diagnostics
    selected_solution = diagnostics.get("selected_solution")
    reported_energy_source = _skqd_solution_provenance(selected_solution, diagnostics)
    return _primary_energy_provenance(result, reported_energy_source)


def _skqd_solution_provenance(selected_solution: Any, diagnostics: dict[str, Any]) -> str:
    """Describe the execution source of the selected SKQD energy."""
    if selected_solution == "sqd_core":
        return "selected_sqd_core_backend_sampler"
    if selected_solution == "krylov_extension":
        return "selected_krylov_extension_classical_exact"
    if selected_solution == "skqd_sample_union":
        sampling_source = diagnostics.get("sampling_source")
        if sampling_source == "sampler_krylov_circuits":
            return "selected_skqd_sample_union_sampler"
        if sampling_source == "exact_statevector_oracle":
            return "selected_skqd_sample_union_local_exact"
    return "selected_skqd_solution_unknown"


def _energy_provenance(result: AlgorithmResult) -> dict[str, Any]:
    """Return final/best/reported energy provenance for normalized payloads."""
    if isinstance(result, VQEResult):
        return _vqe_energy_provenance(result)

    if isinstance(result, SQDResult):
        return _sqd_energy_provenance(result)

    if isinstance(result, KQDResult):
        if not _projected_energy_is_reportable(result):
            return _primary_energy_provenance(result, "unavailable_unstable_projected_solve") | {
                "final_energy": None,
                "best_observed_energy": None,
                "reported_energy": None,
            }
        if _projected_energy_is_diagnostic(result):
            return _primary_energy_provenance(result, "stabilized_projected_diagnostic")
        return _primary_energy_provenance(result, "lowest_krylov_ritz_value")

    if isinstance(result, QFDResult):
        if not _projected_energy_is_reportable(result):
            return _primary_energy_provenance(result, "unavailable_unstable_projected_solve") | {
                "final_energy": None,
                "best_observed_energy": None,
                "reported_energy": None,
            }
        if _projected_energy_is_diagnostic(result):
            return _primary_energy_provenance(result, "stabilized_projected_diagnostic")
        return _primary_energy_provenance(result, "lowest_filter_eigenvalue")

    if isinstance(result, QSEResult):
        if not _projected_energy_is_reportable(result):
            return _primary_energy_provenance(result, "unavailable_unstable_projected_solve") | {
                "final_energy": None,
                "best_observed_energy": None,
                "reported_energy": None,
            }
        if _projected_energy_is_diagnostic(result):
            return _primary_energy_provenance(result, "stabilized_projected_diagnostic")
        return _primary_energy_provenance(result, "lowest_qse_projected_eigenvalue")

    if isinstance(result, SKQDResult):
        return _skqd_energy_provenance(result)

    return _primary_energy_provenance(result, "algorithm_result.primary_energy")


def _energy_policy(result: AlgorithmResult) -> dict[str, Any]:
    """Describe why the normalized top-level energy was chosen."""
    policy: dict[str, Any] = {
        "reported_energy_field": "energy",
        "primary_energy_field": "primary_energy",
        "classical_references_are_context_only": True,
    }
    policy_builder = _resolve_energy_policy_builder(result)
    return policy_builder(policy, result)


def _resolve_energy_policy_builder(
    result: AlgorithmResult,
) -> Callable[[dict[str, Any], AlgorithmResult], dict[str, Any]]:
    if isinstance(result, VQEResult):
        return _vqe_energy_policy
    if isinstance(result, SQDResult):
        return _sqd_energy_policy
    if isinstance(result, KQDResult):
        return _kqd_energy_policy
    if isinstance(result, QFDResult):
        return _qfd_energy_policy
    if isinstance(result, QSEResult):
        return _qse_energy_policy
    if isinstance(result, SKQDResult):
        return _skqd_energy_policy
    return _default_energy_policy


def _vqe_energy_policy(policy: dict[str, Any], result: AlgorithmResult) -> dict[str, Any]:
    assert isinstance(result, VQEResult)
    source = result.optimizer_diagnostics.get(
        "reported_energy_source",
        "best_observed_optimizer_evaluation",
    )
    if source == "independent_final_reevaluation":
        selection_rule = (
            "Use the independent energy reevaluation at the optimizer's final parameter vector. "
            "Keep its uncertainty and optimizer success as separate diagnostics."
        )
    elif source == "final_noisy_objective_observation":
        selection_rule = (
            "Use the sole sampled objective evaluation for a parameterless ansatz. "
            "Keep its standard error separate from convergence status."
        )
    elif source in {
        "optimizer_final_noisy_observation",
        "best_observed_noisy_optimizer_evaluation",
    }:
        selection_rule = (
            "Use an observation at the optimizer's final parameter vector when an independent "
            "reevaluation is unavailable. Do not select the minimum finite-shot observation as "
            "an unbiased estimate. Keep optimizer success as a separate convergence signal."
        )
    else:
        selection_rule = (
            "Use the best observed VQE objective value for deterministic or exact objectives. "
            "Keep optimizer success or SPSA stability as the convergence signal."
        )
    return {
        **policy,
        "primary_energy_source": source,
        "selection_rule": selection_rule,
        "candidate_energy_fields": [
            "convergence_trace",
            "optimizer_diagnostics.best_observed_energy",
            "optimizer_diagnostics.final_energy",
            "optimizer_diagnostics.independent_final_energy",
            "optimizer_diagnostics.reported_energy",
        ],
    }


def _sqd_energy_policy(policy: dict[str, Any], result: AlgorithmResult) -> dict[str, Any]:
    assert isinstance(result, SQDResult)
    source = result.sci_result_package.get(
        "reported_energy_source",
        "best_observed_sqd_iteration",
    )
    sqd_policy = {
        **policy,
        "primary_energy_source": source,
        "selection_rule": "Use the best observed SQD recovery energy rather than the last recovery round.",
        "candidate_energy_fields": [
            "sci_energies",
            "sci_result_package.best_energy",
            "sci_result_package.final_energy",
        ],
    }
    best_iteration = result.sci_result_package.get("best_iteration")
    if best_iteration is not None:
        sqd_policy["best_iteration"] = best_iteration
    return sqd_policy


def _kqd_energy_policy(policy: dict[str, Any], result: AlgorithmResult) -> dict[str, Any]:
    assert isinstance(result, KQDResult)
    branch_estimator = _is_branch_estimator_result(result)
    reportable = _projected_energy_is_reportable(result)
    if not reportable:
        source = "unavailable_unstable_projected_solve"
        selection_rule = (
            "Do not promote a KQD energy when the noisy projected overlap metric "
            "required stabilization or rank reduction."
        )
    elif branch_estimator:
        source = "lowest_krylov_ritz_value"
        selection_rule = (
            "Use the lowest retained Ritz value from the stable noisy projected "
            "Krylov solve."
        )
    else:
        source = "lowest_krylov_ritz_value"
        selection_rule = "Use the lowest Ritz value from the projected Krylov solve."
    return {
        **policy,
        "primary_energy_source": source,
        "selection_rule": selection_rule,
        "candidate_energy_fields": [
            "ritz_values",
            "raw_ritz_values",
            "orthogonality_metrics.ritz_energy",
        ],
    }


def _qfd_energy_policy(policy: dict[str, Any], result: AlgorithmResult) -> dict[str, Any]:
    assert isinstance(result, QFDResult)
    branch_estimator = _is_branch_estimator_result(result)
    reportable = _projected_energy_is_reportable(result)
    if not reportable:
        source = "unavailable_unstable_projected_solve"
        selection_rule = (
            "Do not promote a QFD energy when the noisy projected overlap metric "
            "required stabilization or rank reduction."
        )
    elif branch_estimator:
        source = "lowest_filter_eigenvalue"
        selection_rule = (
            "Use the lowest retained eigenvalue from the stable noisy filtered "
            "projected solve."
        )
    else:
        source = "lowest_filter_eigenvalue"
        selection_rule = "Use the lowest eigenvalue from the filtered projected solve."
    return {
        **policy,
        "primary_energy_source": source,
        "selection_rule": selection_rule,
        "candidate_energy_fields": ["filter_eigenvalues", "raw_filter_eigenvalues"],
    }


def _qse_energy_policy(policy: dict[str, Any], result: AlgorithmResult) -> dict[str, Any]:
    assert isinstance(result, QSEResult)
    return {
        **policy,
        "primary_energy_source": "lowest_qse_projected_eigenvalue",
        "selection_rule": "Use the lowest projected QSE eigenvalue; the reference energy is diagnostic context.",
        "candidate_energy_fields": ["eigenvalues", "reference_state_energy"],
    }


def _skqd_energy_policy(policy: dict[str, Any], result: AlgorithmResult) -> dict[str, Any]:
    assert isinstance(result, SKQDResult)
    selected_solution = result.krylov_extension_diagnostics.get("selected_solution")
    selected_solution_provenance = _skqd_solution_provenance(
        selected_solution,
        result.krylov_extension_diagnostics,
    )
    selection_rule = (
        f"Use the selected SKQD solution path: {selected_solution}."
        if selected_solution
        else "Use the selected SQD core or Krylov-extension energy from SKQD diagnostics."
    )
    return {
        **policy,
        "primary_energy_source": "selected_sqd_or_krylov_solution",
        "selection_rule": selection_rule,
        "candidate_energy_fields": [
            "sqd_core.primary_energy",
            "krylov_extension_diagnostics.ritz_values",
            "krylov_extension_diagnostics.extension_energy",
        ],
        "selected_solution": selected_solution,
        "selected_solution_provenance": selected_solution_provenance,
    }


def _default_energy_policy(policy: dict[str, Any], result: AlgorithmResult) -> dict[str, Any]:
    del result
    return {
        **policy,
        "primary_energy_source": "algorithm_result.primary_energy",
        "selection_rule": "Use the worker algorithm result primary energy.",
        "candidate_energy_fields": ["primary_energy"],
    }


def _vqe_algorithm_metrics(result: VQEResult) -> dict[str, Any]:
    diagnostics = result.optimizer_diagnostics
    metrics = {
        "convergence_trace": result.convergence_trace,
        "optimizer_diagnostics": diagnostics,
        "objective_evaluations": diagnostics.get(
            "objective_evaluations",
            diagnostics.get("function_evaluations", len(result.convergence_trace)),
        ),
        "optimizer_iterations": diagnostics.get("optimizer_iterations"),
        "effective_max_iterations": diagnostics.get("effective_max_iterations"),
        "max_function_evaluations": diagnostics.get("max_function_evaluations"),
        "reported_iterations_unit": diagnostics.get("reported_iterations_unit"),
    }
    if result.bloch_vectors is not None:
        metrics["bloch_vectors"] = result.bloch_vectors
    if result.density_matrix_real is not None:
        metrics["density_matrix_real"] = result.density_matrix_real
    if result.density_matrix_imag is not None:
        metrics["density_matrix_imag"] = result.density_matrix_imag
    if result.circuit_artifacts:
        metrics["circuit_artifacts"] = result.circuit_artifacts
    return metrics


def _sqd_algorithm_metrics(result: SQDResult) -> dict[str, Any]:
    metrics = {
        "sci_energies": result.sci_energies,
        "configuration_recovery_trace": result.configuration_recovery_trace,
        "spin_diagnostics": result.spin_diagnostics,
        "postselection_summary": result.postselection_summary,
        "subsampling_summary": result.subsampling_summary,
        "sci_result_package": result.sci_result_package,
    }
    if result.circuit_artifacts:
        metrics["circuit_artifacts"] = result.circuit_artifacts
    if result.circuit_artifact_policy:
        metrics["circuit_artifact_policy"] = result.circuit_artifact_policy
    return metrics


def _kqd_algorithm_metrics(result: KQDResult) -> dict[str, Any]:
    metrics = {
        "ritz_values": result.ritz_values,
        "raw_ritz_values": result.raw_ritz_values,
        "krylov_rank": result.krylov_rank,
        "orthogonality_metrics": result.orthogonality_metrics,
        "stability_summary": result.stability_summary,
        "selected_level_index": 0 if result.ritz_values else None,
    }
    if result.matrix_element_summary:
        metrics["matrix_element_summary"] = result.matrix_element_summary
    if result.circuit_artifacts:
        metrics["circuit_artifacts"] = result.circuit_artifacts
    return metrics


def _qfd_algorithm_metrics(result: QFDResult) -> dict[str, Any]:
    metrics = {
        "filter_eigenvalues": result.filter_eigenvalues,
        "raw_filter_eigenvalues": result.raw_filter_eigenvalues,
        "conditioning_summary": result.conditioning_summary,
        "stability_summary": result.stability_summary,
        "selected_level_index": 0 if result.filter_eigenvalues else None,
    }
    if result.matrix_element_summary:
        metrics["matrix_element_summary"] = result.matrix_element_summary
    return metrics


def _qse_algorithm_metrics(result: QSEResult) -> dict[str, Any]:
    conditioning_summary = dict(result.conditioning_summary)
    matrix_element_summary = dict(result.matrix_element_summary)
    matrix_element_summary.setdefault("projected_dimension", result.primary_iterations)
    matrix_element_summary.setdefault(
        "projected_matrix_element_count", 2 * result.primary_iterations**2
    )
    matrix_element_summary.setdefault("basis_construction_rule", "fermionic_excitation_basis")
    metrics = {
        "eigenvalues": result.eigenvalues,
        "overlap_condition": result.overlap_condition,
        "conditioning_summary": conditioning_summary,
        "projected_solve_status": conditioning_summary.get("stability_state"),
        "requested_regularization": conditioning_summary.get(
            "requested_regularization", result.regularization
        ),
        "regularization_scope": conditioning_summary.get("regularization_scope"),
        "final_metric_diagonal_shift": conditioning_summary.get(
            "final_metric_diagonal_shift"
        ),
        "regularization_may_change_reported_energy": conditioning_summary.get(
            "regularization_may_change_reported_energy"
        ),
        "matrix_element_summary": matrix_element_summary,
        "excitation_level": result.excitation_level,
        "regularization": result.regularization,
        "reference_state_energy": result.reference_state_energy,
        "reference_method": result.reference_method,
        "reference_state": {
            "method": result.reference_method,
            "energy": result.reference_state_energy,
        },
        "reference_cost": _qse_reference_cost(result),
        "execution_mode": result.execution_mode,
    }
    if result.residual_norm is not None:
        metrics["residual_norm"] = result.residual_norm
    if result.relative_residual is not None:
        metrics["relative_residual"] = result.relative_residual
    if result.convergence_threshold is not None:
        metrics["convergence_threshold"] = result.convergence_threshold
    if result.reference_circuit_artifacts:
        metrics["circuit_artifacts"] = result.reference_circuit_artifacts
    return metrics


def _reference_energy(hamiltonian_metadata: dict[str, Any]) -> tuple[Any, float | None]:
    casci_energy = _finite_float(hamiltonian_metadata.get("casci_energy"))
    hf_energy = _finite_float(hamiltonian_metadata.get("hf_energy"))
    if casci_energy is not None:
        return hamiltonian_metadata.get("reference_method", "CASCI"), casci_energy
    if hf_energy is not None:
        return hamiltonian_metadata.get("reference_method", "Hartree-Fock"), hf_energy
    return hamiltonian_metadata.get("reference_method"), None


def _reference_active_space(hamiltonian_metadata: dict[str, Any]) -> list[int] | None:
    active_space = hamiltonian_metadata.get("reference_active_space")
    if active_space is None:
        active_space = hamiltonian_metadata.get("active_space")
    if not (
        isinstance(active_space, (list, tuple))
        and len(active_space) == 2
        and all(isinstance(value, int) and not isinstance(value, bool) for value in active_space)
    ):
        return None
    return list(active_space)


def _valid_hamiltonian_hash(hamiltonian_metadata: dict[str, Any]) -> str | None:
    hamiltonian_sha256 = hamiltonian_metadata.get("hamiltonian_sha256")
    if not (
        isinstance(hamiltonian_sha256, str)
        and len(hamiltonian_sha256) == 64
        and all(character in "0123456789abcdef" for character in hamiltonian_sha256)
    ):
        return None
    return hamiltonian_sha256


def _reference_provenance(hamiltonian_metadata: dict[str, Any]) -> dict[str, Any]:
    """Describe the classical reference independently from an algorithm result."""
    method, energy = _reference_energy(hamiltonian_metadata)
    normalized_method = method if isinstance(method, str) and method else None
    solver_path = hamiltonian_metadata.get("reference_solver_path") or hamiltonian_metadata.get(
        "pipeline"
    )
    solver_path = solver_path if isinstance(solver_path, str) and solver_path else None
    basis = hamiltonian_metadata.get("reference_basis")
    basis = basis if isinstance(basis, str) and basis else None
    normalized_active_space = _reference_active_space(hamiltonian_metadata)
    normalized_hash = _valid_hamiltonian_hash(hamiltonian_metadata)

    fields = {
        "reference_method": normalized_method,
        "reference_energy": energy,
        "reference_solver_path": solver_path,
        "reference_basis": basis,
        "reference_active_space": normalized_active_space,
        "hamiltonian_sha256": normalized_hash,
    }
    validity_reasons = [
        f"{field_name}_unavailable"
        for field_name, value in fields.items()
        if value is None
    ]

    return {
        "method": normalized_method,
        "backend_target": hamiltonian_metadata.get(
            "reference_backend_target", "local_classical"
        ),
        "solver_path": solver_path,
        "basis": basis,
        "active_space": normalized_active_space,
        "hamiltonian_sha256": normalized_hash,
        "energy": energy,
        "reference_precision": hamiltonian_metadata.get("reference_precision"),
        "reference_precision_policy": hamiltonian_metadata.get("reference_precision_policy"),
        "source_commit": hamiltonian_metadata.get("source_commit"),
        "validity_status": "valid" if not validity_reasons else "incomplete",
        "validity_reasons": validity_reasons,
    }


def _qse_reference_cost(result: QSEResult) -> dict[str, Any]:
    """Return QSE reference-state cost without mixing it into projected-solve cost."""
    artifacts = [
        artifact for artifact in result.reference_circuit_artifacts if isinstance(artifact, dict)
    ]
    for artifact in artifacts:
        cost = artifact.get("reference_cost")
        if isinstance(cost, dict):
            return {
                **cost,
                "reference_method": result.reference_method,
                "circuit_artifact_count": len(artifacts),
            }

    depths = [
        int(artifact["depth"])
        for artifact in artifacts
        if isinstance(artifact.get("depth"), int) and not isinstance(artifact.get("depth"), bool)
    ]
    if result.reference_method == "hf":
        return {
            "cost_type": "hf_reference_preparation",
            "cost_status": "measured" if artifacts else "partial",
            "reference_method": result.reference_method,
            "state_preparations": len(artifacts) if artifacts else None,
            "circuit_artifact_count": len(artifacts),
            "representative_circuit_depth": max(depths) if depths else None,
        }
    if result.reference_method in {"provided_state", "provided_sector"}:
        return {
            "cost_type": "caller_provided_reference",
            "cost_status": "not_applicable",
            "reference_method": result.reference_method,
            "state_preparations": 0,
            "circuit_artifact_count": 0,
            "not_applicable_reason": "reference_state_supplied_by_caller",
        }
    return {
        "cost_type": "reference_state_preparation",
        "cost_status": "unavailable",
        "reference_method": result.reference_method,
        "state_preparations": None,
        "circuit_artifact_count": len(artifacts),
        "not_measured_reason": "reference_cost_not_recorded",
    }


def _energy_consistency(
    *,
    reported_energy: float | None,
    reference: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute energy validity from one reported/reference Hamiltonian pair."""
    reference = reference if isinstance(reference, dict) else {}
    reference_energy = _finite_float(reference.get("energy"))
    signed_error = (
        reported_energy - reference_energy
        if reported_energy is not None and reference_energy is not None
        else None
    )
    reasons: list[str] = []
    if reported_energy is None:
        reasons.append("reported_energy_non_finite")
    if reference_energy is None:
        reasons.append("reference_energy_non_finite")
    if reference.get("validity_status") not in {None, "valid"}:
        reasons.append("reference_provenance_invalid")
    if not reasons:
        status = "valid"
    elif signed_error is None:
        status = "incomplete"
    else:
        status = "invalid"
    return {
        "status": status,
        "reported_energy": reported_energy,
        "reference_energy": reference_energy,
        "signed_error": signed_error,
        "absolute_error": abs(signed_error) if signed_error is not None else None,
        "tolerance_ha": 1e-12,
        "failure_reasons": reasons,
    }


def _skqd_algorithm_metrics(result: SKQDResult) -> dict[str, Any]:
    diagnostics = result.krylov_extension_diagnostics
    metrics: dict[str, Any] = {
        "sqd_core": result.sqd_core,
        "krylov_extension_diagnostics": diagnostics,
    }
    work_ledger = diagnostics.get("work_ledger")
    if isinstance(work_ledger, dict):
        metrics["work_ledger"] = dict(work_ledger)
    if result.circuit_artifacts:
        metrics["circuit_artifacts"] = result.circuit_artifacts
    if result.circuit_artifact_policy:
        metrics["circuit_artifact_policy"] = result.circuit_artifact_policy
    return metrics


def _algorithm_metrics(result: AlgorithmResult) -> dict[str, Any]:
    if isinstance(result, VQEResult):
        return _vqe_algorithm_metrics(result)
    if isinstance(result, SQDResult):
        return _sqd_algorithm_metrics(result)
    if isinstance(result, KQDResult):
        return _kqd_algorithm_metrics(result)
    if isinstance(result, QFDResult):
        return _qfd_algorithm_metrics(result)
    if isinstance(result, QSEResult):
        return _qse_algorithm_metrics(result)
    if isinstance(result, SKQDResult):
        return _skqd_algorithm_metrics(result)
    return {}


def _boolean_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _vqe_budget_exhausted(result: VQEResult) -> bool:
    """Detect optimizer caps even when SciPy reports a generic failure."""
    diagnostics = result.optimizer_diagnostics
    termination_reason = diagnostics.get("termination_reason")
    if termination_reason in {"max_function_evaluations", "max_iterations"}:
        return True

    objective_evaluations = diagnostics.get("objective_evaluations")
    max_function_evaluations = diagnostics.get("max_function_evaluations")
    if (
        isinstance(objective_evaluations, (int, float))
        and isinstance(max_function_evaluations, (int, float))
        and objective_evaluations >= max_function_evaluations
    ):
        return True

    message = diagnostics.get("message")
    if isinstance(message, str):
        normalized_message = message.lower()
        if "maxfun" in normalized_message or "maximum number of function evaluations" in normalized_message:
            return True

    optimizer_iterations = diagnostics.get("optimizer_iterations")
    effective_max_iterations = diagnostics.get("effective_max_iterations")
    return bool(
        not result.converged
        and isinstance(optimizer_iterations, (int, float))
        and isinstance(effective_max_iterations, (int, float))
        and optimizer_iterations >= effective_max_iterations
    )


def _projected_system_stability(metrics: dict[str, Any]) -> bool | None:
    for key in ("stability_summary", "orthogonality_metrics", "conditioning_summary"):
        diagnostics = metrics.get(key)
        if not isinstance(diagnostics, dict):
            continue
        stability_state = diagnostics.get("stability_state")
        if isinstance(stability_state, str):
            return stability_state == "stable"
        condition = _finite_float(
            diagnostics.get("overlap_condition", diagnostics.get("projected_overlap_condition"))
        )
        minimum = _finite_float(
            diagnostics.get(
                "overlap_min_eigenvalue",
                diagnostics.get("projected_overlap_min_eigenvalue"),
            )
        )
        if condition is not None and minimum is not None:
            return condition >= 0.0 and minimum > 0.0
    return None


def _vqe_convergence_metadata(result: VQEResult) -> dict[str, Any]:
    diagnostics = result.optimizer_diagnostics
    delta = _finite_float(diagnostics.get("final_delta_energy"))
    threshold = _finite_float(diagnostics.get("convergence_threshold"))
    reported_scientific_convergence = diagnostics.get("scientific_converged")
    optimizer_success = diagnostics.get("optimizer_success", diagnostics.get("success"))
    if isinstance(reported_scientific_convergence, bool):
        failure_reason = diagnostics.get("convergence_failure_reason")
        if reported_scientific_convergence and (
            optimizer_success is False
            or (result.converged is False and diagnostics.get("termination_reason") != "ansatz_has_no_parameters")
        ):
            reported_scientific_convergence = False
        if not reported_scientific_convergence and not isinstance(failure_reason, str):
            if optimizer_success is False or result.converged is False:
                failure_reason = "optimizer_reported_failure"
            elif diagnostics.get("numerical_stability") is False:
                failure_reason = "numerical_instability"
            elif delta is not None and threshold is not None and delta > threshold:
                failure_reason = "energy_delta_exceeded"
        return {
            "scientific_converged": reported_scientific_convergence,
            "convergence_criterion": diagnostics.get(
                "convergence_criterion", "absolute_energy_delta"
            ),
            "convergence_value": delta,
            "convergence_threshold": threshold,
            "convergence_failure_reason": failure_reason,
        }
    if diagnostics.get("termination_reason") == "ansatz_has_no_parameters":
        return {
            "scientific_converged": True,
            "convergence_criterion": "parameterless_objective_evaluation",
            "convergence_value": 0.0,
            "convergence_threshold": 0.0,
        }
    if optimizer_success is False or result.converged is False:
        return {
            "scientific_converged": False,
            "convergence_criterion": "optimizer_success_and_absolute_energy_delta",
            "convergence_value": delta,
            "convergence_threshold": threshold,
            "convergence_failure_reason": "optimizer_reported_failure",
        }
    if delta is not None and threshold is not None:
        return {
            "scientific_converged": bool(result.converged) and delta <= threshold,
            "convergence_criterion": "optimizer_success_and_absolute_energy_delta",
            "convergence_value": delta,
            "convergence_threshold": threshold,
            "convergence_failure_reason": (
                None
                if bool(result.converged) and delta <= threshold
                else "optimizer_reported_failure"
                if not result.converged
                else "energy_delta_exceeded"
            ),
        }
    return {
        "scientific_converged": None,
        "convergence_criterion": "energy_delta",
        "convergence_failure_reason": "energy_delta_threshold_unavailable",
    }


def _sqd_convergence_metadata(result: SQDResult, metrics: dict[str, Any]) -> dict[str, Any]:
    package = metrics.get("sci_result_package")
    package = package if isinstance(package, dict) else {}
    trace = metrics.get("configuration_recovery_trace")
    trace = trace if isinstance(trace, list) else []
    latest = trace[-1] if trace and isinstance(trace[-1], dict) else {}
    delta = _finite_float(latest.get("delta_energy"))
    occupancy_delta = _finite_float(latest.get("occupancy_delta"))
    selected = latest.get("accepted_samples")
    selected_count = int(selected) if isinstance(selected, (int, float)) else None
    selected_floor = package.get("min_selected_configurations")
    selected_floor = int(selected_floor) if isinstance(selected_floor, (int, float)) else None
    result_metadata = {
        "scientific_converged": _boolean_or_none(result.converged),
        "convergence_criterion": (
            "energy_delta_and_occupancy_delta_with_selected_configuration_floor"
        ),
        "convergence_value": {
            "energy_delta": delta,
            "occupancy_delta": occupancy_delta,
            "selected_configurations": selected_count,
        },
        "convergence_threshold": {
            "energy_delta": _finite_float(package.get("energy_tol")),
            "occupancy_delta": _finite_float(package.get("occupancies_tol")),
            "selected_configurations": selected_floor,
        },
    }
    if delta is None or occupancy_delta is None:
        result_metadata["convergence_failure_reason"] = "initial_iteration_delta_unavailable"
    return result_metadata


def _projected_convergence_metadata(
    result: KQDResult | QFDResult,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    stable = _projected_system_stability(metrics)
    diagnostics_key = "orthogonality_metrics" if isinstance(result, KQDResult) else "conditioning_summary"
    diagnostics = metrics.get(diagnostics_key)
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    residual = _finite_float(diagnostics.get("relative_ritz_residual"))
    threshold = _finite_float(diagnostics.get("residual_convergence_threshold"))
    metadata = {
        "projected_system_stable": stable,
        "convergence_criterion": "projected_overlap_condition_and_generalized_residual",
        "convergence_value": residual,
        "convergence_threshold": threshold,
    }
    if residual is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="projected_residual_unavailable",
        )
    elif threshold is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="projected_residual_threshold_unavailable",
        )
    elif stable is False:
        metadata.update(
            scientific_converged=False,
            convergence_failure_reason=(
                "projected_metric_rank_reduced"
                if _finite_float(diagnostics.get("dropped_rank")) not in (None, 0.0)
                else "projected_system_unstable"
            ),
        )
    elif stable is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="projected_system_stability_unavailable",
        )
    else:
        if _is_branch_estimator_result(result):
            summary = getattr(result, "matrix_element_summary", {})
            projected_converged = summary.get("projected_solver_converged")
            if not isinstance(projected_converged, bool):
                projected_converged = bool(result.converged) and residual <= threshold
            metadata.update(
                scientific_converged=None,
                projected_solver_converged=projected_converged,
                convergence_criterion=(
                    "projected_overlap_stability_and_residual; "
                    "full_space_ritz_residual_unavailable"
                ),
                convergence_failure_reason="full_space_residual_unavailable",
            )
        else:
            scientific_converged = bool(result.converged) and residual <= threshold
            metadata["scientific_converged"] = scientific_converged
            if not scientific_converged:
                metadata["convergence_failure_reason"] = "solver_reported_not_converged"
    return metadata


def _qse_convergence_metadata(metrics: dict[str, Any], result: QSEResult) -> dict[str, Any]:
    stable = _projected_system_stability(metrics)
    if stable is None:
        overlap_condition = _finite_float(metrics.get("overlap_condition"))
        stable = overlap_condition is not None and overlap_condition >= 0.0
    residual = _finite_float(metrics.get("relative_residual"))
    threshold = _finite_float(metrics.get("convergence_threshold"))
    metadata = {
        "projected_system_stable": stable,
        "convergence_criterion": "projected_ritz_residual",
        "convergence_value": residual,
        "convergence_threshold": threshold,
    }
    if residual is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="projected_residual_unavailable",
        )
    elif threshold is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="projected_residual_threshold_unavailable",
        )
    elif stable is False:
        metadata.update(
            scientific_converged=False,
            convergence_failure_reason="projected_system_unstable",
        )
    elif stable is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="projected_system_stability_unavailable",
        )
    else:
        scientific_converged = bool(result.converged) and residual <= threshold
        metadata["scientific_converged"] = scientific_converged
        if not scientific_converged:
            metadata["convergence_failure_reason"] = "solver_reported_not_converged"
    return metadata


def _skqd_convergence_metadata(result: SKQDResult, metrics: dict[str, Any]) -> dict[str, Any]:
    diagnostics = metrics.get("krylov_extension_diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    if diagnostics.get("selected_solution") == "skqd_sample_union":
        verdict = diagnostics.get("convergence_verdict")
        verdict = verdict if isinstance(verdict, dict) else {}
        complete_selected_ci_solve = verdict.get("complete_selected_ci_solve") is True
        full_sector_recovered = verdict.get("full_sector_recovered") is True
        scientific_converged = complete_selected_ci_solve and full_sector_recovered
        convergence_failure_reason = None
        if not full_sector_recovered:
            convergence_failure_reason = "full_sector_recovery_not_established"
        elif not complete_selected_ci_solve:
            convergence_failure_reason = "complete_selected_ci_solve_not_established"
        metadata: dict[str, Any] = {
            "scientific_converged": scientific_converged,
            "convergence_criterion": (
                "full_ci_sector_recovery_and_complete_selected_ci_solve"
            ),
            "convergence_value": {
                "subspace_saturated": verdict.get("subspace_saturated"),
                "complete_selected_ci_solve": verdict.get("complete_selected_ci_solve"),
                "full_sector_recovered": verdict.get("full_sector_recovered"),
                "selected_ci_fraction": verdict.get("selected_ci_fraction"),
                "final_prefix_growth_delta": verdict.get("final_prefix_growth_delta"),
            },
            "convergence_threshold": {
                "final_prefix_growth_delta": 0,
                "selected_ci_fraction": 1.0,
            },
        }
        if convergence_failure_reason is not None:
            metadata["convergence_failure_reason"] = convergence_failure_reason
        return metadata
    if diagnostics.get("selected_solution") == "sqd_core":
        sqd_core = metrics.get("sqd_core")
        sqd_core = sqd_core if isinstance(sqd_core, dict) else {}
        sqd_converged = _boolean_or_none(
            diagnostics.get("sqd_converged", sqd_core.get("converged"))
        )
        return {
            "scientific_converged": (
                sqd_converged if sqd_converged is not None else _boolean_or_none(result.converged)
            ),
            "convergence_criterion": "selected_sqd_core_sqd_convergence",
            "convergence_value": {"sqd_converged": sqd_converged},
            "convergence_threshold": None,
        }
    residual = _finite_float(diagnostics.get("relative_residual"))
    threshold = _finite_float(diagnostics.get("residual_tolerance"))
    metadata = {
        "scientific_converged": _boolean_or_none(result.converged),
        "convergence_criterion": "selected_krylov_extension_residual_and_sqd_convergence",
        "convergence_value": residual,
        "convergence_threshold": threshold,
    }
    if residual is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="selected_solution_residual_unavailable",
        )
    elif threshold is None:
        metadata.update(
            scientific_converged=None,
            convergence_failure_reason="selected_solution_residual_threshold_unavailable",
        )
    return metadata


def _convergence_metadata(result: AlgorithmResult, metrics: dict[str, Any]) -> dict[str, Any]:
    """Build explicit convergence categories without replacing legacy fields."""
    energy_finite = _finite_float(result.primary_energy) is not None
    metadata: dict[str, Any] = {
        "optimizer_converged": _boolean_or_none(result.converged),
        "scientific_converged": _boolean_or_none(result.converged),
        "budget_exhausted": None,
        "projected_system_stable": None,
        "energy_finite": energy_finite,
        "energy_sane": None,
        "convergence_criterion": None,
        "convergence_value": None,
        "convergence_threshold": None,
        "convergence_failure_reason": None,
    }
    if isinstance(result, VQEResult):
        metadata["budget_exhausted"] = _vqe_budget_exhausted(result)
        metadata.update(_vqe_convergence_metadata(result))
    elif isinstance(result, SQDResult):
        metadata.update(_sqd_convergence_metadata(result, metrics))
    elif isinstance(result, (KQDResult, QFDResult)):
        metadata.update(_projected_convergence_metadata(result, metrics))
    elif isinstance(result, QSEResult):
        metadata.update(_qse_convergence_metadata(metrics, result))
    elif isinstance(result, SKQDResult):
        metadata.update(_skqd_convergence_metadata(result, metrics))

    if metadata["budget_exhausted"] is True and metadata["scientific_converged"] is False:
        metadata["convergence_failure_reason"] = "budget_exhausted"
    if not energy_finite:
        metadata["energy_sane"] = False
        metadata["convergence_failure_reason"] = "reported_energy_non_finite"
    return metadata


def _classical_references(hamiltonian_metadata: dict[str, Any] | None) -> dict[str, float]:
    if not hamiltonian_metadata:
        return {}
    references: dict[str, float] = {}
    hf = hamiltonian_metadata.get("hf_energy")
    if hf is not None:
        references["hf"] = float(hf)
    casci = hamiltonian_metadata.get("casci_energy")
    if casci is not None:
        references["fci"] = float(casci)
    return references


def _validated_problem_manifest(
    hamiltonian_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    manifest = hamiltonian_metadata.get("problem_manifest") if hamiltonian_metadata else None
    if not isinstance(manifest, dict):
        return None
    if not validate_problem_manifest(manifest):
        raise ValueError("Hamiltonian problem manifest hash is invalid")
    return manifest


def _attach_problem_manifest(
    payload: dict[str, Any],
    manifest: dict[str, Any] | None,
) -> None:
    if manifest is None:
        return
    payload["problem_manifest"] = manifest
    payload["algorithm_metrics"]["problem_manifest"] = manifest


def _apply_energy_consistency(
    payload: dict[str, Any],
    *,
    energy_provenance: dict[str, Any],
    reference_record: dict[str, Any] | None,
) -> None:
    consistency = _energy_consistency(
        reported_energy=energy_provenance["reported_energy"],
        reference=reference_record,
    )
    payload["algorithm_metrics"]["energy_consistency"] = consistency
    payload["algorithm_metrics"]["convergence"]["energy_sane"] = (
        consistency["status"] == "valid" if reference_record else None
    )
    convergence = payload["algorithm_metrics"]["convergence"]
    if reference_record and consistency["status"] != "valid" and convergence.get(
        "scientific_converged"
    ) is True:
        convergence["scientific_converged"] = False
        convergence["convergence_failure_reason"] = "energy_consistency_invalid"


def normalize_result(
    raw_result: AlgorithmResult,
    hamiltonian_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert algorithm-native result dataclasses into persistence payloads."""
    energy_provenance = _energy_provenance(raw_result)
    payload: dict[str, Any] = {
        "algorithm": raw_result.algorithm,
        "primary_energy": raw_result.primary_energy,
        "primary_iterations": raw_result.primary_iterations,
        "converged": raw_result.converged,
        # Keep legacy fields for transition consumers.
        "energy": energy_provenance["reported_energy"],
        "iterations": raw_result.primary_iterations,
        "optimal_parameters": [],
        **energy_provenance,
    }

    if isinstance(raw_result, VQEResult):
        payload["optimal_parameters"] = raw_result.optimal_parameters

    energy_policy = _energy_policy(raw_result)
    payload["energy_policy"] = energy_policy
    payload["algorithm_metrics"] = _algorithm_metrics(raw_result)
    payload["algorithm_metrics"]["energy_policy"] = energy_policy
    payload["algorithm_metrics"]["convergence"] = _convergence_metadata(
        raw_result,
        payload["algorithm_metrics"],
    )

    classical_refs = _classical_references(hamiltonian_metadata)
    problem_manifest = _validated_problem_manifest(hamiltonian_metadata)
    _attach_problem_manifest(payload, problem_manifest)

    if classical_refs:
        payload["algorithm_metrics"]["classical_references"] = classical_refs
    if hamiltonian_metadata:
        payload["algorithm_metrics"]["reference_provenance"] = _reference_provenance(
            hamiltonian_metadata
        )
    reference_record = payload["algorithm_metrics"].get("reference_provenance")
    _apply_energy_consistency(
        payload,
        energy_provenance=energy_provenance,
        reference_record=reference_record,
    )
    if (
        isinstance(raw_result, SKQDResult)
        and raw_result.krylov_extension_diagnostics.get("selected_solution")
        == "skqd_sample_union"
    ):
        payload["converged"] = (
            payload["algorithm_metrics"]["convergence"]["scientific_converged"] is True
        )

    payload["raw_result"] = {
        "algorithm": raw_result.algorithm,
        **energy_provenance,
        "algorithm_metrics": payload["algorithm_metrics"],
        "energy_policy": energy_policy,
        "classical_references": classical_refs,
    }
    if isinstance(problem_manifest, dict):
        payload["raw_result"]["problem_manifest"] = problem_manifest
    return payload
