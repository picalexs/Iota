"""Similarity scoring and compatibility guards for estimate history."""

from __future__ import annotations

import math

_IBM_RUNTIME_TARGET = "ibm_runtime"
_MOLECULE_NUM_QUBITS = "molecule.num_qubits"
_MOLECULE_N_ORBITALS = "molecule.n_orbitals"
_MOLECULE_ATOM_COUNT = "molecule.atom_count"
_CONFIG_EASY_MODE_CATALOG_VERSION = "config.easy_mode_catalog_version"
_NUMERIC_FEATURE_WEIGHTS: tuple[tuple[str, float], ...] = (
    (_MOLECULE_NUM_QUBITS, 3.0),
    (_MOLECULE_N_ORBITALS, 2.6),
    ("molecule.n_electrons", 2.4),
    ("backend_options.shots", 1.8),
    ("config.max_function_evaluations", 1.8),
    ("config.max_iterations", 1.7),
    ("config.samples_per_batch", 1.7),
    ("config.num_batches", 1.6),
    ("config.krylov_dim", 1.8),
    ("config.num_time_points", 1.8),
    ("config.max_subspace_dim", 1.8),
    ("config.krylov_extension_dim", 1.7),
    ("config.max_dim", 1.9),
    ("config.base_sampling_options.max_dim", 1.9),
    ("config.reps", 1.4),
    ("config.trotter_steps", 1.4),
    ("config.vqe_reference_max_iterations", 1.6),
    ("backend_options.optimization_level", 1.2),
    (_MOLECULE_ATOM_COUNT, 1.2),
)
_CATEGORICAL_FEATURE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("backend_target", 3.0),
    (_CONFIG_EASY_MODE_CATALOG_VERSION, 2.4),
    ("config.optimizer_name", 1.8),
    ("config.ansatz_name", 1.7),
    ("backend_options.backend_name", 1.7),
    ("config.reference_method", 1.6),
    ("basis_set", 1.5),
    ("config.excitation_level", 1.4),
    ("config.evolution_method", 1.4),
    ("config.time_grid_type", 1.4),
    ("backend_options.aer_method", 1.3),
    ("backend_options.selection_policy", 1.1),
    ("noise_profile.source", 1.0),
    ("noise_profile.preset", 1.0),
    ("mode", 0.7),
)


def feature_weight(key: str, *, numeric: bool) -> float:
    candidates = _NUMERIC_FEATURE_WEIGHTS if numeric else _CATEGORICAL_FEATURE_WEIGHTS
    for prefix, weight in candidates:
        if key == prefix or key.startswith(f"{prefix}."):
            return weight
    return 0.55 if numeric else 0.45


def numeric_similarity(left: float, right: float) -> float:
    if left == right:
        return 1.0
    distance = abs(math.log1p(abs(left)) - math.log1p(abs(right)))
    return math.exp(-1.35 * distance)


def categorical_similarity(key: str, left: str, right: str) -> float:
    if left == right:
        return 1.0
    if key == "backend_target":
        local_targets = {"statevector", "aer_simulator"}
        if left in local_targets and right in local_targets:
            return 0.25
        return 0.08
    if key == "mode":
        return 0.55
    return 0.0


def similarity_score(
    request_numeric: dict[str, float],
    request_categorical: dict[str, str],
    history_numeric: dict[str, float],
    history_categorical: dict[str, str],
) -> float:
    weighted_score = 0.0
    total_weight = 0.0

    for key in sorted(request_categorical.keys() & history_categorical.keys()):
        weight = feature_weight(key, numeric=False)
        total_weight += weight
        weighted_score += weight * categorical_similarity(
            key,
            request_categorical[key],
            history_categorical[key],
        )

    for key in sorted(request_numeric.keys() & history_numeric.keys()):
        weight = feature_weight(key, numeric=True)
        total_weight += weight
        weighted_score += weight * numeric_similarity(request_numeric[key], history_numeric[key])

    if total_weight <= 0.0:
        return 0.0
    return weighted_score / total_weight


def within_scale_ratio(left: float | None, right: float | None, *, max_ratio: float) -> bool:
    if left is None or right is None or left <= 0 or right <= 0:
        return True
    larger = max(left, right)
    smaller = min(left, right)
    return (larger / smaller) <= max_ratio


def passes_scale_guard(
    request_numeric: dict[str, float],
    history_numeric: dict[str, float],
) -> bool:
    request_orbitals = request_numeric.get(_MOLECULE_N_ORBITALS)
    history_orbitals = history_numeric.get(_MOLECULE_N_ORBITALS)
    if not within_scale_ratio(request_orbitals, history_orbitals, max_ratio=1.8):
        return False

    request_qubits = request_numeric.get(_MOLECULE_NUM_QUBITS)
    history_qubits = history_numeric.get(_MOLECULE_NUM_QUBITS)
    if not within_scale_ratio(request_qubits, history_qubits, max_ratio=1.8):
        return False
    if (
        request_qubits is not None
        and history_qubits is not None
        and abs(request_qubits - history_qubits) > 8.0
    ):
        return False

    request_atoms = request_numeric.get(_MOLECULE_ATOM_COUNT)
    history_atoms = history_numeric.get(_MOLECULE_ATOM_COUNT)
    if not within_scale_ratio(request_atoms, history_atoms, max_ratio=3.0):
        return False

    return True


def passes_version_guard(
    request_categorical: dict[str, str],
    history_categorical: dict[str, str],
) -> bool:
    request_version = request_categorical.get(_CONFIG_EASY_MODE_CATALOG_VERSION)
    if request_version is None:
        return True

    history_version = history_categorical.get(_CONFIG_EASY_MODE_CATALOG_VERSION)
    return history_version == request_version


def passes_backend_guard(
    request_categorical: dict[str, str],
    history_categorical: dict[str, str],
) -> bool:
    request_backend_target = request_categorical.get("backend_target")
    history_backend_target = history_categorical.get("backend_target")
    if request_backend_target == history_backend_target:
        return True
    if _IBM_RUNTIME_TARGET in {request_backend_target, history_backend_target}:
        return False
    return True


# Private aliases preserve the old helper names for the flat facade.
_feature_weight = feature_weight
_numeric_similarity = numeric_similarity
_categorical_similarity = categorical_similarity
_similarity_score = similarity_score
_within_scale_ratio = within_scale_ratio
_passes_scale_guard = passes_scale_guard
_passes_version_guard = passes_version_guard
_passes_backend_guard = passes_backend_guard


__all__ = [
    "categorical_similarity",
    "feature_weight",
    "numeric_similarity",
    "passes_backend_guard",
    "passes_scale_guard",
    "passes_version_guard",
    "similarity_score",
    "within_scale_ratio",
]
