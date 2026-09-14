"""Pure run configuration and execution-context normalization."""

from __future__ import annotations

import json
from typing import Any, NamedTuple, TypedDict
from uuid import UUID

_MIN_RELIABLE_SEED_CONFIDENCE = 0.65


class RunRowSnapshot(TypedDict, total=False):
    config_snapshot: object
    metadata: object
    latest_estimate: object
    initial_estimate: object
    credential_profile_id: object


class RunContext(NamedTuple):
    algorithm: str
    mode: str
    backend_target: str
    config_snapshot: dict[str, Any]


def _as_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _extract_run_context(run_row: RunRowSnapshot | None) -> RunContext:
    """Extract algorithm, mode, backend target, and config snapshot from a DB row."""
    if not run_row:
        return RunContext("vqe", "advanced", "statevector", {})

    base_config_snapshot = _as_dict(run_row.get("config_snapshot"))
    config_snapshot = base_config_snapshot
    metadata = _as_dict(run_row.get("metadata"))

    algorithm = str(config_snapshot.get("algorithm") or metadata.get("algorithm") or "vqe").lower()
    mode = str(config_snapshot.get("mode") or metadata.get("mode") or "advanced").lower()
    backend_target = _resolve_backend_target(
        config_snapshot,
        default=(
            str(
                config_snapshot.get("backend_target")
                or metadata.get("backend_target")
                or "statevector"
            )
        ),
    )
    easy_mode_config = (
        _expanded_easy_mode_config(base_config_snapshot, metadata) if mode == "easy" else None
    )
    if easy_mode_config is not None:
        config_snapshot = easy_mode_config

    return RunContext(algorithm, mode, backend_target, config_snapshot)


def _resolve_backend_target(config_snapshot: dict[str, Any], *, default: str) -> str:
    if "backend_target" in config_snapshot:
        return default
    legacy_backend = config_snapshot.get("backend")
    if not isinstance(legacy_backend, str):
        return default
    normalized_backend = legacy_backend.strip().lower()
    if normalized_backend == "aer_simulator":
        return "aer_simulator"
    if normalized_backend.startswith("ibm_"):
        return "ibm_runtime"
    if normalized_backend == "statevector":
        return "statevector"
    return default


def _config_override_value(value: object) -> object | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict) and value:
        return dict(value)
    return None


def _expanded_easy_mode_config(
    base_config_snapshot: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    easy_mode = metadata.get("easy_mode")
    if not isinstance(easy_mode, dict):
        return None
    expanded_config = easy_mode.get("expanded_advanced_config")
    if not isinstance(expanded_config, dict):
        return None

    config_snapshot = dict(expanded_config)
    for key in (
        "backend_target",
        "backend_options",
        "noise_profile",
        "basis_set",
        "basis_set_override",
    ):
        if key in config_snapshot:
            continue
        override_value = _config_override_value(base_config_snapshot.get(key))
        if override_value is not None:
            config_snapshot[key] = override_value
    return config_snapshot


def _estimate_seed_from_snapshot(
    run_row: RunRowSnapshot | None,
) -> tuple[float | None, float | None]:
    if not run_row:
        return None, None

    for key in ("latest_estimate", "initial_estimate"):
        estimate = _as_dict(run_row.get(key))
        confidence_value = _estimate_confidence(estimate)
        if not _estimate_source_is_usable(key, estimate, confidence_value):
            continue

        seeded_seconds = _seconds_per_iteration_from_estimate(estimate)
        if seeded_seconds is not None:
            return seeded_seconds, confidence_value

    return None, None


def _estimate_confidence(estimate: dict[str, Any]) -> float | None:
    confidence = estimate.get("confidence")
    return float(confidence) if isinstance(confidence, (int, float)) else None


def _estimate_source_is_usable(
    key: str,
    estimate: dict[str, Any],
    confidence_value: float | None,
) -> bool:
    source = estimate.get("source")
    if key == "initial_estimate":
        return source == "history" and (
            confidence_value is not None and confidence_value >= _MIN_RELIABLE_SEED_CONFIDENCE
        )
    return source in {"telemetry", "history"}


def _seconds_per_iteration_from_estimate(estimate: dict[str, Any]) -> float | None:
    seconds_per_iteration = estimate.get("estimated_seconds_per_iteration")
    if isinstance(seconds_per_iteration, (int, float)) and seconds_per_iteration > 0:
        return float(seconds_per_iteration)

    total_seconds = estimate.get("estimated_total_seconds")
    total_iterations = estimate.get("estimated_total_iterations")
    if (
        isinstance(total_seconds, (int, float))
        and isinstance(total_iterations, (int, float))
        and total_seconds > 0
        and total_iterations > 0
    ):
        return float(total_seconds) / float(total_iterations)
    return None


def _resolve_basis_set(config_snapshot: dict[str, Any], molecule_basis_set: Any) -> str:
    """Resolve basis set with run-level override precedence."""
    for key in ("basis_set_override", "basis_set"):
        value = config_snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if isinstance(molecule_basis_set, str) and molecule_basis_set.strip():
        return molecule_basis_set.strip()

    return "sto-3g"


def _extract_active_space(active_space_raw: Any) -> tuple[int, int] | None:
    """Extract active-space tuple from molecule JSON payload."""
    active_space = _as_dict(active_space_raw)
    n_electrons = active_space.get("n_electrons")
    n_orbitals = active_space.get("n_orbitals")
    if isinstance(n_electrons, int) and isinstance(n_orbitals, int):
        return int(n_electrons), int(n_orbitals)
    return None


def _runtime_algorithm_config(config_snapshot: dict[str, Any], algorithm: str) -> dict[str, Any]:
    advanced_config = config_snapshot.get("advanced_config")
    if (
        isinstance(advanced_config, dict)
        and str(advanced_config.get("algorithm", "")).lower() == algorithm.lower()
    ):
        source = advanced_config
    else:
        source = config_snapshot

    algorithm_config = dict(source)
    for key in (
        "backend",
        "backend_target",
        "backend_options",
        "basis_set",
        "basis_set_override",
        "easy_options",
        "mode",
        "noise_profile",
        "selection_policy",
    ):
        algorithm_config.pop(key, None)
    return algorithm_config


def _normalize_credential_profile_id(value: object) -> str | None:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _backend_options_from_config(
    config_snapshot: dict[str, Any],
    *,
    credential_profile_id: object | None = None,
) -> dict[str, Any]:
    backend_options = config_snapshot.get("backend_options")
    if isinstance(backend_options, dict):
        resolved_backend_options = dict(backend_options)
    else:
        advanced_config = config_snapshot.get("advanced_config")
        if isinstance(advanced_config, dict) and isinstance(
            advanced_config.get("backend_options"), dict
        ):
            resolved_backend_options = dict(advanced_config["backend_options"])
        else:
            resolved_backend_options = {}

    if not resolved_backend_options.get("credential_profile_id"):
        persisted_profile_id = _normalize_credential_profile_id(credential_profile_id)
        if persisted_profile_id is not None:
            resolved_backend_options["credential_profile_id"] = persisted_profile_id

    return resolved_backend_options


def _noise_profile_from_config(config_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    noise_profile = config_snapshot.get("noise_profile")
    return dict(noise_profile) if isinstance(noise_profile, dict) else None


def _selection_policy_from_config(config_snapshot: dict[str, Any]) -> str:
    backend_options = config_snapshot.get("backend_options")
    if isinstance(backend_options, dict):
        value = backend_options.get("selection_policy")
        if isinstance(value, str) and value.strip():
            return value
    value = config_snapshot.get("selection_policy")
    return str(value) if isinstance(value, str) and value.strip() else "requested"
