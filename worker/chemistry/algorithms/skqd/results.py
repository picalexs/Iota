"""SKQD result, diagnostic, and completion-payload helpers for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.algorithms.skqd.distributions import (
    statevector_bitstring_distribution,
    time_evolved_bitstring_distribution,
)
from worker.chemistry.circuit_artifacts import retag_circuit_artifact
from worker.chemistry.sector_basis import largest_sector_bitstring_distribution


@dataclass(frozen=True)
class SKQDCompletionPayload:
    """Completed SKQD progress values."""

    basis_rank: int
    primary_energy: float
    primary_iterations: int
    krylov_extension_dim: int
    sampling_time_step: float
    sqd_iterations: int
    seeded_from_sqd: bool
    seed_source: str
    execution_mode: str
    krylov_converged: bool
    sqd_converged: bool
    overall_converged: bool
    selected_solution: str
    selected_solution_converged: bool
    relative_residual: float
    residual_tolerance: float
    min_ritz: float | None
    max_ritz: float | None


def build_sqd_core_summary(sqd_result: Any) -> dict[str, Any]:
    """Build the persisted SQD core payload carried inside an SKQD result."""
    sqd_core = {
        "algorithm": sqd_result.algorithm,
        "primary_energy": sqd_result.primary_energy,
        "primary_iterations": sqd_result.primary_iterations,
        "converged": sqd_result.converged,
        "sci_result_package": sqd_result.sci_result_package,
    }
    if sqd_result.circuit_artifact_policy:
        sqd_core["circuit_artifact_policy"] = sqd_result.circuit_artifact_policy
    return sqd_core


def build_not_run_sqd_core_summary(*, reason: str) -> dict[str, Any]:
    """Build the explicit empty core record used by direct sample-union SKQD."""
    return {
        "algorithm": "sqd",
        "status": "not_run",
        "primary_energy": None,
        "primary_iterations": 0,
        "converged": None,
        "sci_result_package": {
            "status": "not_run",
            "reason": reason,
        },
    }


def build_skqd_circuit_artifacts(sqd_result: Any) -> list[dict[str, Any]]:
    """Retag one representative SQD seed artifact for SKQD result payloads."""
    representative_seed = next(
        (
            artifact
            for artifact in sqd_result.circuit_artifacts
            if bool(artifact.get("representative"))
        ),
        sqd_result.circuit_artifacts[-1] if sqd_result.circuit_artifacts else None,
    )
    if representative_seed is None:
        return []
    return [
        retag_circuit_artifact(
            representative_seed,
            algorithm="skqd",
            role="sqd_seed",
            source="sqd_seed",
            artifact_id_prefix="skqd",
            phase="seed",
            representative=True,
        )
    ]


def select_skqd_primary_solution(
    *,
    sqd_core_energy: float | None,
    extension_energy: float | None,
    extension_converged: bool,
) -> tuple[float | None, str]:
    """Choose the reported SKQD energy without degrading below the SQD core."""
    if sqd_core_energy is not None and (
        extension_energy is None or not extension_converged or sqd_core_energy <= extension_energy
    ):
        return sqd_core_energy, "sqd_core"
    if extension_energy is not None and extension_converged:
        return extension_energy, "krylov_extension"
    if sqd_core_energy is not None:
        return sqd_core_energy, "sqd_core"
    if extension_energy is not None:
        return extension_energy, "krylov_extension"
    return None, "none"


def build_skqd_extension_diagnostics(
    *,
    plan: Any,
    extension: Any,
    sqd_result: Any,
    ritz_values: list[float],
    krylov_extension_dim: int,
    sampling_time_step: float,
) -> dict[str, Any]:
    """Build SKQD extension diagnostics from the completed Krylov extension."""
    diagnostics = {
        "krylov_extension_dim": float(krylov_extension_dim),
        "time_step": sampling_time_step,
        "operator_dimension": float(plan.operator_dimension),
        "basis_rank": float(extension.basis_rank),
        "sqd_iterations": float(sqd_result.primary_iterations or 0),
        "seeded_from_sqd_occupancies": extension.seed_source == "sqd_occupancies",
        "seeded_from_sqd": extension.sqd_seed is not None,
        "seed_source": extension.seed_source,
        "sqd_converged": bool(sqd_result.converged),
        "execution_mode": plan.execution_mode,
        **extension.residual_diagnostics,
    }
    if plan.sector_action is not None:
        diagnostics["sector_dimension"] = float(plan.sector_action.dimension)
        diagnostics["num_spatial_orbitals"] = float(plan.sector_action.norb)
        diagnostics["num_electrons_alpha"] = float(plan.sector_action.nelec[0])
        diagnostics["num_electrons_beta"] = float(plan.sector_action.nelec[1])
    if ritz_values:
        diagnostics["min_ritz"] = float(min(ritz_values))
        diagnostics["max_ritz"] = float(max(ritz_values))
    return diagnostics


def add_skqd_solution_diagnostics(
    diagnostics: dict[str, Any],
    *,
    sqd_core_energy: float | None,
    extension_energy: float | None,
    selected_solution: str,
    selected_solution_converged: bool,
) -> None:
    """Attach selected-solution SKQD diagnostics."""
    diagnostics["selected_solution"] = selected_solution
    diagnostics["selected_solution_converged"] = selected_solution_converged
    if sqd_core_energy is not None:
        diagnostics["sqd_core_energy"] = sqd_core_energy
    diagnostics["extension_energy"] = extension_energy
    if extension_energy is None:
        diagnostics["extension_improved_sqd"] = None
        return
    diagnostics["extension_improved_sqd"] = bool(
        sqd_core_energy is None or extension_energy < sqd_core_energy
    )


def skqd_krylov_distribution(
    plan: Any,
    ground_state: np.ndarray | None,
) -> list[dict[str, Any]]:
    """Return the display distribution for the SKQD Krylov ground state."""
    if plan.sector_action is not None:
        return largest_sector_bitstring_distribution(
            ground_state,
            norb=plan.sector_action.norb,
            nelec=plan.sector_action.nelec,
        )
    return statevector_bitstring_distribution(ground_state)


def add_skqd_state_diagnostics(
    diagnostics: dict[str, Any],
    *,
    plan: Any,
    extension: Any,
    sampling_time_step: float,
) -> None:
    """Attach optional SKQD state-distribution diagnostics."""
    krylov_distribution = skqd_krylov_distribution(plan, extension.ground_state)
    if krylov_distribution:
        diagnostics["krylov_state_bitstring_distribution"] = krylov_distribution
    if plan.operator is None:
        return
    time_evolved_distribution = time_evolved_bitstring_distribution(
        plan.operator,
        extension.krylov_seed,
        num_steps=max(extension.basis_rank, 1),
        time_step=sampling_time_step,
    )
    if time_evolved_distribution:
        diagnostics["time_evolved_bitstring_distribution"] = time_evolved_distribution
        diagnostics["time_evolved_sampling_time_step"] = sampling_time_step


def build_skqd_completion_payload(
    *,
    extension: Any,
    sqd_result: Any,
    skqd_config: Any,
    primary_energy: float,
    primary_iterations: int,
    selected_solution: str,
    selected_solution_converged: bool,
    krylov_converged: bool,
    overall_converged: bool,
    ritz_values: list[float],
    execution_mode: str,
    sampling_time_step: float,
) -> SKQDCompletionPayload:
    """Build the SKQD completed progress payload object."""
    return SKQDCompletionPayload(
        basis_rank=extension.basis_rank,
        primary_energy=primary_energy,
        primary_iterations=primary_iterations,
        krylov_extension_dim=skqd_config.krylov_extension_dim,
        sampling_time_step=sampling_time_step,
        sqd_iterations=int(sqd_result.primary_iterations or 0),
        seeded_from_sqd=extension.sqd_seed is not None,
        seed_source=extension.seed_source,
        execution_mode=execution_mode,
        krylov_converged=krylov_converged,
        sqd_converged=bool(sqd_result.converged),
        overall_converged=overall_converged,
        selected_solution=selected_solution,
        selected_solution_converged=selected_solution_converged,
        relative_residual=extension.residual_diagnostics["relative_ritz_residual"],
        residual_tolerance=skqd_config.residual_tolerance,
        min_ritz=float(min(ritz_values)) if ritz_values else None,
        max_ritz=float(max(ritz_values)) if ritz_values else None,
    )


__all__ = [
    "SKQDCompletionPayload",
    "add_skqd_solution_diagnostics",
    "add_skqd_state_diagnostics",
    "build_sqd_core_summary",
    "build_skqd_circuit_artifacts",
    "build_skqd_completion_payload",
    "build_not_run_sqd_core_summary",
    "build_skqd_extension_diagnostics",
    "select_skqd_primary_solution",
    "skqd_krylov_distribution",
]
