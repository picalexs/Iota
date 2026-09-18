"""SKQD seed selection and extension dispatch for the algorithm package."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.progress import ProgressCallback


@dataclass(frozen=True)
class SKQDExecutionPlan:
    """Resolved SKQD execution mode and operator resources."""

    sector_action: HamiltonianAction | None
    operator: np.ndarray | None
    operator_dimension: int
    execution_mode: str


@dataclass(frozen=True)
class SKQDExtensionOutcome:
    """Seed selection and Krylov extension outputs for SKQD."""

    sqd_seed: np.ndarray | None
    seed_source: str
    krylov_seed: np.ndarray
    ritz_values_raw: np.ndarray
    basis_rank: int
    residual_diagnostics: dict[str, float]
    ground_state: np.ndarray | None


def execute_skqd_extension(
    *,
    sqd_result: Any,
    plan: SKQDExecutionPlan,
    hamiltonian: object,
    krylov_extension_dim: int,
    sampling_time_step: float,
    residual_tolerance: float,
    progress_callback: ProgressCallback | None,
    resolve_sector_seed_fn: Callable[..., tuple[np.ndarray | None, str]],
    resolve_dense_seed_fn: Callable[..., tuple[np.ndarray | None, str]],
    build_sector_krylov_fn: Callable[
        ..., tuple[np.ndarray, int, dict[str, float], np.ndarray | None]
    ],
    build_dense_krylov_fn: Callable[
        ..., tuple[np.ndarray, int, dict[str, float], np.ndarray | None]
    ],
    build_sector_hf_reference_fn: Callable[..., np.ndarray],
    build_dense_hf_reference_fn: Callable[..., np.ndarray],
) -> SKQDExtensionOutcome:
    """Resolve an SQD seed and execute the selected SKQD extension path."""
    if plan.sector_action is not None:
        sqd_seed, seed_source = resolve_sector_seed_fn(
            sqd_result,
            action=plan.sector_action,
        )
        krylov_seed = (
            sqd_seed
            if sqd_seed is not None
            else build_sector_hf_reference_fn(
                plan.sector_action.norb,
                plan.sector_action.nelec,
            )
        )
        if sqd_seed is None:
            seed_source = "hf_sector_reference"
        ritz_values_raw, basis_rank, residual_diagnostics, ground_state = build_sector_krylov_fn(
            plan.sector_action,
            seed_state=krylov_seed,
            seeded_from_sqd=sqd_seed is not None,
            target_rank=krylov_extension_dim,
            time_step=sampling_time_step,
            residual_tolerance=residual_tolerance,
            progress_callback=progress_callback,
        )
    else:
        if plan.operator is None:
            raise ValueError("SKQD dense matrix operator was not initialized")
        sqd_seed, seed_source = resolve_dense_seed_fn(
            sqd_result,
            target_size=plan.operator.shape[0],
        )
        krylov_seed = (
            sqd_seed
            if sqd_seed is not None
            else build_dense_hf_reference_fn(
                hamiltonian,
                fallback_dim=plan.operator.shape[0],
            )
        )
        if sqd_seed is None:
            seed_source = "hf_reference"
        ritz_values_raw, basis_rank, residual_diagnostics, ground_state = build_dense_krylov_fn(
            plan.operator,
            seed_state=krylov_seed,
            seeded_from_sqd=sqd_seed is not None,
            target_rank=krylov_extension_dim,
            time_step=sampling_time_step,
            residual_tolerance=residual_tolerance,
            progress_callback=progress_callback,
        )

    return SKQDExtensionOutcome(
        sqd_seed=sqd_seed,
        seed_source=seed_source,
        krylov_seed=krylov_seed,
        ritz_values_raw=ritz_values_raw,
        basis_rank=basis_rank,
        residual_diagnostics=residual_diagnostics,
        ground_state=ground_state,
    )


__all__ = [
    "SKQDExtensionOutcome",
    "SKQDExecutionPlan",
    "execute_skqd_extension",
]
