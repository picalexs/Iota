"""SQD configuration and Hamiltonian-input normalization for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from worker.chemistry.algorithms.sqd.selection import resolve_selected_ci_limits
from worker.chemistry.solver_utils import (
    bounded_int,
    nonnegative_float,
    positive_float,
    resolve_algorithm_config,
)

_DEFAULT_MIN_SELECTED_CONFIGURATIONS = 2
_DEFAULT_CARRYOVER_THRESHOLD = 1e-4
_MAX_RUNTIME_ITERATIONS = 5000
_MAX_NUMPY_SEED = 2**32 - 1


@dataclass(frozen=True)
class SQDOptions:
    """Resolved SQD configuration and Hamiltonian inputs."""

    max_iterations: int
    samples_per_batch: int
    num_batches: int
    symmetrize_spin: bool
    one_body: np.ndarray
    two_body: np.ndarray
    hamiltonian_constant: float
    norb: int
    num_elec_a: int
    num_elec_b: int
    target_spin_sq: float | None
    energy_tol: float
    occupancies_tol: float
    carryover_threshold: float
    total_samples: int
    min_selected_configurations: int
    seed: int
    selected_ci_limits: tuple[int, int]
    selected_ci_limit_summary: dict[str, Any]
    sci_solver_options: dict[str, Any]
    open_shell: bool
    selected_ci_requested_device: str = "CPU"
    selected_ci_actual_device: str = "CPU"
    selected_ci_provider: str = "qiskit_addon_sqd"
    selected_ci_fallback_reason: str | None = None


def resolve_sqd_hamiltonian_inputs(
    hamiltonian: object,
) -> tuple[np.ndarray, np.ndarray, float, int, int, int]:
    """Resolve tensors, constant, and electron counts from a Hamiltonian bundle."""
    required = (
        "one_body_tensor",
        "two_body_tensor",
        "num_spatial_orbitals",
        "num_electrons_alpha",
        "num_electrons_beta",
    )
    missing = [name for name in required if not hasattr(hamiltonian, name)]
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"SQD requires HamiltonianBundle tensors; missing: {missing_list}")

    one_body = np.asarray(cast(Any, getattr(hamiltonian, "one_body_tensor")), dtype=np.float64)
    two_body = np.asarray(cast(Any, getattr(hamiltonian, "two_body_tensor")), dtype=np.float64)
    constant = float(getattr(hamiltonian, "constant", 0.0))

    norb = int(getattr(hamiltonian, "num_spatial_orbitals"))
    num_elec_a = int(getattr(hamiltonian, "num_electrons_alpha"))
    num_elec_b = int(getattr(hamiltonian, "num_electrons_beta"))

    if one_body.shape != (norb, norb):
        raise ValueError("SQD one_body_tensor shape is incompatible with num_spatial_orbitals")
    if two_body.shape != (norb, norb, norb, norb):
        raise ValueError("SQD two_body_tensor shape is incompatible with num_spatial_orbitals")
    if num_elec_a < 0 or num_elec_b < 0 or num_elec_a > norb or num_elec_b > norb:
        raise ValueError("SQD electron counts must be between 0 and num_spatial_orbitals")

    return one_body, two_body, constant, norb, num_elec_a, num_elec_b


def resolve_sqd_options(
    config: dict[str, Any],
    hamiltonian: object,
    *,
    sample_budget: int | None = None,
) -> SQDOptions:
    """Resolve SQD runtime options from the request config and Hamiltonian bundle."""
    resolved = resolve_algorithm_config(config, "sqd")

    max_iterations = bounded_int(
        resolved.get("max_iterations"),
        default=20,
        low=1,
        high=_MAX_RUNTIME_ITERATIONS,
    )
    has_explicit_sample_budget = "samples_per_batch" in resolved or "num_batches" in resolved
    budget = (
        max(1, int(sample_budget))
        if isinstance(sample_budget, (int, float)) and not isinstance(sample_budget, bool)
        else None
    )
    samples_per_batch = bounded_int(
        resolved.get("samples_per_batch"),
        default=budget or 512,
        low=1,
        high=2000,
    )
    num_batches = bounded_int(
        resolved.get("num_batches"),
        default=1 if budget is not None and not has_explicit_sample_budget else 8,
        low=1,
        high=128,
    )
    symmetrize_spin = bool(resolved.get("symmetrize_spin") or False)

    one_body, two_body, hamiltonian_constant, norb, bundle_elec_a, bundle_elec_b = (
        resolve_sqd_hamiltonian_inputs(hamiltonian)
    )
    num_elec_a = bounded_int(resolved.get("num_elec_a"), default=bundle_elec_a, low=0, high=norb)
    num_elec_b = bounded_int(resolved.get("num_elec_b"), default=bundle_elec_b, low=0, high=norb)
    if symmetrize_spin and num_elec_a != num_elec_b:
        raise ValueError("SQD symmetrize_spin requires equal alpha and beta electron counts")

    total_samples = samples_per_batch * num_batches
    raw_max_dim = resolved.get("max_dim")
    if (
        symmetrize_spin
        and isinstance(raw_max_dim, (list, tuple))
        and len(raw_max_dim) == 2
        and int(raw_max_dim[0]) != int(raw_max_dim[1])
    ):
        raise ValueError("SQD symmetrize_spin requires identical alpha and beta max_dim limits")

    open_shell = num_elec_a != num_elec_b
    target_spin_sq = (
        None
        if open_shell and resolved.get("spin_sq_target") is None
        else nonnegative_float(
            resolved.get("spin_sq_target"),
            default=0.0,
            name="SQD spin_sq_target",
        )
    )
    energy_tol = positive_float(
        resolved.get("energy_tol"),
        default=1e-5,
        name="SQD energy_tol",
    )
    occupancies_tol = positive_float(
        resolved.get("occupancies_tol"),
        default=1e-5,
        name="SQD occupancies_tol",
    )
    carryover_threshold = nonnegative_float(
        resolved.get("carryover_threshold"),
        default=_DEFAULT_CARRYOVER_THRESHOLD,
        name="SQD carryover_threshold",
    )
    min_selected_configurations = bounded_int(
        resolved.get("min_selected_configurations"),
        default=_DEFAULT_MIN_SELECTED_CONFIGURATIONS,
        low=1,
        high=max(total_samples, 1),
    )
    seed = bounded_int(resolved.get("seed"), default=42, low=0, high=_MAX_NUMPY_SEED)
    selected_ci_limits, selected_ci_limit_summary = resolve_selected_ci_limits(
        raw_max_dim,
        norb=norb,
        num_elec_a=num_elec_a,
        num_elec_b=num_elec_b,
    )
    raw_solver_options = resolved.get("sci_solver_options")
    if raw_solver_options is not None and not isinstance(raw_solver_options, dict):
        raise ValueError("SQD sci_solver_options must be an object when provided")
    sci_solver_options = {"max_cycle": 50}
    if isinstance(raw_solver_options, dict):
        sci_solver_options.update(raw_solver_options)

    return SQDOptions(
        max_iterations=max_iterations,
        samples_per_batch=samples_per_batch,
        num_batches=num_batches,
        symmetrize_spin=symmetrize_spin,
        one_body=one_body,
        two_body=two_body,
        hamiltonian_constant=hamiltonian_constant,
        norb=norb,
        num_elec_a=num_elec_a,
        num_elec_b=num_elec_b,
        target_spin_sq=target_spin_sq,
        energy_tol=energy_tol,
        occupancies_tol=occupancies_tol,
        carryover_threshold=carryover_threshold,
        total_samples=total_samples,
        min_selected_configurations=min_selected_configurations,
        seed=seed,
        selected_ci_limits=selected_ci_limits,
        selected_ci_limit_summary=selected_ci_limit_summary,
        sci_solver_options=sci_solver_options,
        open_shell=open_shell,
    )
