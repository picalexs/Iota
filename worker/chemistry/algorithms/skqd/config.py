"""Pure SKQD configuration normalization for the algorithm package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from worker.chemistry.solver_utils import bounded_int, positive_float

_MAX_NUMPY_SEED = 2**32 - 1
_MAX_SAMPLES_PER_STATE = 4096
_ANALYSIS_ONLY_SAMPLING_MODE = "sample_union_exact"
_LEGACY_SAMPLING_MODE = "legacy_statevector_extension"
_SUPPORTED_SAMPLING_MODES = {
    _ANALYSIS_ONLY_SAMPLING_MODE,
    _LEGACY_SAMPLING_MODE,
}


@dataclass(frozen=True)
class SKQDConfig:
    """Resolved SKQD options for sample-union or explicit legacy execution."""

    krylov_extension_dim: int
    residual_tolerance: float
    sampling_time_step: float | None
    time_step_policy: str
    sampling_mode: str
    samples_per_state: int
    seed: int
    trotter_steps: int
    trotter_order: int
    sqd_config: dict[str, Any]


def resolve_skqd_config(resolved: Mapping[str, Any]) -> SKQDConfig:
    """Resolve user SKQD options into bounded internal values."""
    base_sampling_options = resolved.get("base_sampling_options")
    if isinstance(base_sampling_options, dict):
        # The sampled-union path needs only sector and selected-CI options.
        # Supply inert SQD resolver defaults instead of exposing SQD recovery
        # controls that this workflow does not execute.
        sqd_config: dict[str, Any] = {
            "algorithm": "sqd",
            "samples_per_batch": 1,
            "num_batches": 1,
            "max_iterations": 1,
            "energy_tol": 1e-5,
            "occupancies_tol": 1e-5,
            "carryover_threshold": 0.0,
            **base_sampling_options,
        }
    else:
        sqd_config = {
            "algorithm": "sqd",
            "samples_per_batch": 1,
            "num_batches": 1,
            "max_iterations": 1,
        }
    # Historical configs omit this key. Preserve their established default.
    raw_sampling_mode = resolved.get("sampling_mode") or _ANALYSIS_ONLY_SAMPLING_MODE
    sampling_mode = str(raw_sampling_mode).strip().lower()
    if sampling_mode not in _SUPPORTED_SAMPLING_MODES:
        supported = ", ".join(sorted(_SUPPORTED_SAMPLING_MODES))
        raise ValueError(f"SKQD sampling_mode must be one of: {supported}")
    samples_per_state = bounded_int(
        resolved.get("samples_per_state"),
        default=512,
        low=1,
        high=_MAX_SAMPLES_PER_STATE,
    )
    base_seed = (
        base_sampling_options.get("seed") if isinstance(base_sampling_options, dict) else None
    )
    seed = bounded_int(
        resolved.get("seed"),
        default=bounded_int(base_seed, default=42, low=0, high=_MAX_NUMPY_SEED),
        low=0,
        high=_MAX_NUMPY_SEED,
    )
    # The SKQD convergence analysis fixes Delta t = pi / Delta E_{N-1}. Honor an
    # explicit user time step; otherwise defer to the spectral-width auto-scale
    # resolved against the Hamiltonian at execution time.
    raw_time_step = resolved.get("time_step")
    if raw_time_step is None:
        raw_time_step = resolved.get("krylov_time_step")
    if raw_time_step is not None:
        sampling_time_step: float | None = positive_float(
            raw_time_step,
            default=1.0,
            name="SKQD time_step",
        )
        time_step_policy = "explicit_user_time_step"
    else:
        sampling_time_step = None
        time_step_policy = "paper_spectral_width_pi_over_delta_e"
    return SKQDConfig(
        krylov_extension_dim=bounded_int(
            resolved.get("krylov_extension_dim"),
            default=2,
            low=1,
            high=32,
        ),
        residual_tolerance=positive_float(
            resolved.get("residual_tolerance"),
            default=1e-6,
            name="SKQD residual_tolerance",
        ),
        sampling_time_step=sampling_time_step,
        time_step_policy=time_step_policy,
        sampling_mode=sampling_mode,
        samples_per_state=samples_per_state,
        seed=seed,
        trotter_steps=bounded_int(resolved.get("trotter_steps"), default=1, low=1, high=32),
        trotter_order=bounded_int(resolved.get("trotter_order"), default=2, low=1, high=4),
        sqd_config=sqd_config,
    )


__all__ = ["SKQDConfig", "resolve_skqd_config"]
