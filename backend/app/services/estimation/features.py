"""Pure feature extraction and similarity helpers for run estimates."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.models.enums import BackendTarget, RunMode
from app.models.molecule import Molecule

_VOLATILE_CONFIG_KEYS = frozenset(
    {
        "client_request_id",
        "credential_profile_id",
        "ibm_runtime_confirmed",
        "seed_simulator",
        "seed_transpiler",
        "token",
        "instance",
        "channel",
        "url",
    }
)


def as_dict(value: Any) -> dict[str, Any]:
    """Return mappings in the JSON snapshots as ordinary dictionaries."""
    return value if isinstance(value, dict) else {}


def molecule_num_qubits(molecule: Molecule | None) -> int:
    """Estimate qubit count from molecule active-space metadata."""
    if molecule is None or not isinstance(molecule.active_space, dict):
        return 4

    n_orbitals = molecule.active_space.get("n_orbitals")
    if isinstance(n_orbitals, int) and n_orbitals > 0:
        return max(1, 2 * n_orbitals)
    return 4


def normalize_basis_set(value: str | None) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return "sto-3g"


def coerce_positive_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0.0:
        return None
    return numeric


def coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = int(value)
    if numeric < 0:
        return None
    return numeric


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def molecule_features(molecule: Molecule | None) -> dict[str, float]:
    features: dict[str, float] = {
        "atom_count": (
            float(len(molecule.atoms)) if molecule and isinstance(molecule.atoms, list) else 0.0
        ),
        "charge": float(int(molecule.charge)) if molecule is not None else 0.0,
        "multiplicity": (float(int(molecule.multiplicity)) if molecule is not None else 1.0),
        "num_qubits": float(molecule_num_qubits(molecule)),
    }
    active_space = molecule.active_space if molecule is not None else None
    if isinstance(active_space, dict):
        n_electrons = active_space.get("n_electrons")
        n_orbitals = active_space.get("n_orbitals")
        if isinstance(n_electrons, int) and n_electrons > 0:
            features["n_electrons"] = float(n_electrons)
        if isinstance(n_orbitals, int) and n_orbitals > 0:
            features["n_orbitals"] = float(n_orbitals)
    return features


def is_volatile_feature_key(key: str) -> bool:
    return key.rsplit(".", 1)[-1] in _VOLATILE_CONFIG_KEYS


def _flatten_mapping_features(
    value: Mapping[Any, Any],
    *,
    prefix: str,
    numeric: dict[str, float],
    categorical: dict[str, str],
) -> None:
    for key, nested_value in value.items():
        key_str = str(key)
        if key_str in _VOLATILE_CONFIG_KEYS:
            continue
        nested_prefix = f"{prefix}.{key_str}" if prefix else key_str
        _flatten_feature_value(
            nested_value,
            prefix=nested_prefix,
            numeric=numeric,
            categorical=categorical,
        )


def _flatten_scalar_feature(
    value: Any,
    *,
    prefix: str,
    numeric: dict[str, float],
    categorical: dict[str, str],
) -> None:
    if isinstance(value, bool):
        categorical[prefix] = "true" if value else "false"
        return

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized:
            categorical[prefix] = normalized
        return

    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if math.isfinite(numeric_value):
            numeric[prefix] = numeric_value


def _flatten_feature_value(
    value: Any,
    *,
    prefix: str,
    numeric: dict[str, float],
    categorical: dict[str, str],
) -> None:
    if is_volatile_feature_key(prefix):
        return

    if isinstance(value, Mapping):
        _flatten_mapping_features(
            value,
            prefix=prefix,
            numeric=numeric,
            categorical=categorical,
        )
        return

    if isinstance(value, (list, tuple)):
        numeric[f"{prefix}.count"] = float(len(value))
        return

    _flatten_scalar_feature(
        value,
        prefix=prefix,
        numeric=numeric,
        categorical=categorical,
    )


def build_feature_set(
    *,
    mode: RunMode | str,
    backend_target: BackendTarget | str,
    basis_set: str,
    molecule: Molecule | None,
    config_payload: dict[str, Any],
    backend_options: dict[str, Any] | None,
    noise_profile: dict[str, Any] | None,
) -> tuple[dict[str, float], dict[str, str]]:
    numeric: dict[str, float] = {}
    categorical: dict[str, str] = {
        "mode": mode.value if isinstance(mode, RunMode) else str(mode),
        "backend_target": (
            backend_target.value
            if isinstance(backend_target, BackendTarget)
            else str(backend_target)
        ),
        "basis_set": normalize_basis_set(basis_set),
    }

    _flatten_feature_value(
        molecule_features(molecule),
        prefix="molecule",
        numeric=numeric,
        categorical=categorical,
    )
    _flatten_feature_value(
        config_payload,
        prefix="config",
        numeric=numeric,
        categorical=categorical,
    )
    if backend_options:
        _flatten_feature_value(
            backend_options,
            prefix="backend_options",
            numeric=numeric,
            categorical=categorical,
        )
    if noise_profile:
        _flatten_feature_value(
            noise_profile,
            prefix="noise_profile",
            numeric=numeric,
            categorical=categorical,
        )

    return numeric, categorical


# Private aliases keep the names used by the former flat service module
# available to the compatibility facade without duplicating the implementation.
_as_dict = as_dict
_molecule_num_qubits = molecule_num_qubits
_normalize_basis_set = normalize_basis_set
_coerce_positive_float = coerce_positive_float
_coerce_non_negative_int = coerce_non_negative_int
_parse_iso_datetime = parse_iso_datetime
_molecule_features = molecule_features
_is_volatile_feature_key = is_volatile_feature_key
_build_feature_set = build_feature_set


__all__ = [
    "as_dict",
    "build_feature_set",
    "coerce_non_negative_int",
    "coerce_positive_float",
    "molecule_features",
    "molecule_num_qubits",
    "normalize_basis_set",
    "parse_iso_datetime",
]
