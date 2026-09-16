"""Serializable public catalog shared by API and worker boundaries."""

from __future__ import annotations

from copy import deepcopy
from typing import NotRequired, TypedDict

from .identifiers import BackendTarget, EasyGoal, RunAlgorithm
from .registry_metadata import (
    AnsatzMetadata,
    OptimizerMetadata,
    supported_ansatz_metadata,
    supported_optimizer_metadata,
)

CATALOG_VERSION = "2026-09-16-v22"


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class NumericLimit(TypedDict):
    """Public numeric guardrail advertised to clients."""

    maximum: int | float
    minimum: NotRequired[int | float]


class CatalogChoice(TypedDict):
    """Public selector metadata without runtime implementation objects."""

    id: str
    label: str
    aliases: list[str]
    description: str
    supported_algorithms: list[str]
    metadata: dict[str, JsonValue]


class EasyGoalPreset(TypedDict):
    """Public target value associated with an easy-mode goal tier."""

    goal: str
    label: str
    chemical_accuracy_target_ha: float


RecommendationCatalog = dict[str, dict[str, dict[str, JsonValue]]]


class PublicCatalog(TypedDict):
    """Complete serializable run-configuration catalog."""

    catalog_version: str
    algorithms: list[str]
    backend_targets: list[str]
    easy_goals: list[str]
    easy_goal_presets: list[EasyGoalPreset]
    ansatzes: list[CatalogChoice]
    optimizers: list[CatalogChoice]
    limits: dict[str, NumericLimit]
    defaults: dict[str, JsonValue]
    capabilities: dict[str, dict[str, bool]]
    recommendations: RecommendationCatalog


def get_public_recommendation(*, algorithm: str, goal: str) -> dict[str, JsonValue]:
    """Return one defensive copy of a public recommendation configuration."""
    try:
        recommendation = PUBLIC_RECOMMENDATIONS[algorithm][goal]
    except KeyError as exc:
        raise ValueError(f"No public recommendation for {algorithm}:{goal}") from exc
    return deepcopy(recommendation)


def get_public_recommendation_config(*, algorithm: str, goal: str) -> dict[str, JsonValue]:
    """Return recommendation settings without benchmark-only budget metadata."""
    recommendation = get_public_recommendation(algorithm=algorithm, goal=goal)
    recommendation.pop("budget", None)
    return recommendation


PUBLIC_LIMITS: dict[str, NumericLimit] = {
    "advanced_config.max_iterations": {"minimum": 1, "maximum": 5000},
    "advanced_config.max_function_evaluations": {"minimum": 1, "maximum": 250_000},
    "advanced_config.initial_point_candidates": {"minimum": 1, "maximum": 16},
    "advanced_config.samples_per_batch": {"minimum": 1, "maximum": 2000},
    "advanced_config.samples_per_state": {"minimum": 1, "maximum": 4096},
    "advanced_config.num_batches": {"minimum": 1, "maximum": 128},
    "advanced_config.krylov_dim": {"minimum": 1, "maximum": 64},
    "advanced_config.trotter_steps": {"minimum": 1, "maximum": 32},
    "advanced_config.num_time_points": {"minimum": 1, "maximum": 128},
    "advanced_config.max_subspace_dim": {"minimum": 1, "maximum": 96},
    "advanced_config.vqe_reference_max_iterations": {"minimum": 1, "maximum": 1000},
    "advanced_config.krylov_extension_dim": {"minimum": 1, "maximum": 32},
    "molecule.active_space.n_orbitals.dense": {"minimum": 1, "maximum": 6},
    "molecule.active_space.sector_dimension": {"minimum": 1, "maximum": 500_000},
}

PUBLIC_DEFAULTS: dict[str, JsonValue] = {
    "ansatz_name": "NumberPreserving",
    "optimizer_name": "COBYLA",
    "qse_reference_ansatz_name": "NumberPreserving",
    "qse_reference_optimizer_name": "COBYLA",
}

PUBLIC_EASY_GOAL_PRESETS: list[EasyGoalPreset] = [
    {
        "goal": EasyGoal.FASTEST.value,
        "label": "5.0 mHa",
        "chemical_accuracy_target_ha": 5e-3,
    },
    {
        "goal": EasyGoal.BALANCED.value,
        "label": "1.6 mHa",
        "chemical_accuracy_target_ha": 1.6e-3,
    },
    {
        "goal": EasyGoal.BEST_ACCURACY.value,
        "label": "0.5 mHa",
        "chemical_accuracy_target_ha": 5e-4,
    },
]

PUBLIC_BACKEND_CAPABILITIES: dict[str, dict[str, bool]] = {
    BackendTarget.STATEVECTOR.value: {
        "enabled": True,
        "supports_noise_profile": False,
        "supports_shots": False,
    },
    BackendTarget.AER_SIMULATOR.value: {
        "enabled": True,
        "supports_noise_profile": True,
        "supports_shots": True,
    },
    BackendTarget.IBM_RUNTIME.value: {
        "enabled": True,
        "supports_noise_profile": False,
        "supports_shots": True,
    },
}

PUBLIC_RECOMMENDATIONS: RecommendationCatalog = {
    "vqe": {
        "fastest": {
            "ansatz_name": "NumberPreserving",
            "optimizer_name": "COBYLA",
            "max_iterations": 128,
            "max_function_evaluations": 128,
            "reps": 2,
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 1,
            "seed": None,
            "convergence_threshold": None,
            "budget": {
                "objective_evaluations": 128,
                "initial_point_candidates": 1,
            },
        },
        "balanced": {
            "ansatz_name": "NumberPreserving",
            "optimizer_name": "COBYLA",
            "max_iterations": 448,
            "max_function_evaluations": 448,
            "reps": 2,
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 2,
            "seed": None,
            "convergence_threshold": None,
            "budget": {
                "objective_evaluations": 448,
                "initial_point_candidates": 2,
            },
        },
        "best_accuracy": {
            "ansatz_name": "NumberPreserving",
            "optimizer_name": "COBYLA",
            "max_iterations": 512,
            "max_function_evaluations": 512,
            "reps": 2,
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 4,
            "seed": None,
            "convergence_threshold": None,
            "budget": {
                "objective_evaluations": 512,
                "initial_point_candidates": 4,
            },
        },
    },
    "sqd": {
        "fastest": {
            "samples_per_batch": 256,
            "num_batches": 4,
            "max_iterations": 4,
            "sampling_state_source": "vqe",
            "sampling_vqe_ansatz_name": "NumberPreserving",
            "sampling_vqe_optimizer_name": "COBYLA",
            "sampling_vqe_max_iterations": 128,
            "sampling_vqe_reps": 1,
            "sampling_vqe_seed": None,
            "energy_tol": 1e-4,
            "occupancies_tol": 1e-4,
            "min_selected_configurations": 2,
            "seed": None,
            "symmetrize_spin": False,
            "carryover_threshold": None,
            "max_dim_mode": "shared",
            "max_dim": 16,
            "max_dim_a": None,
            "max_dim_b": None,
            "spin_sq_target": None,
            "budget": {
                "samples": 1024,
                "recovery_rounds": 4,
                "selected_ci_max_dim": 16,
                "sampling_vqe_iterations": 128,
            },
        },
        "balanced": {
            "samples_per_batch": 512,
            "num_batches": 8,
            "max_iterations": 8,
            "sampling_state_source": "vqe",
            "sampling_vqe_ansatz_name": "NumberPreserving",
            "sampling_vqe_optimizer_name": "COBYLA",
            "sampling_vqe_max_iterations": 448,
            "sampling_vqe_reps": 2,
            "sampling_vqe_seed": None,
            "energy_tol": 7.5e-5,
            "occupancies_tol": 7.5e-5,
            "min_selected_configurations": 2,
            "seed": None,
            "symmetrize_spin": False,
            "carryover_threshold": None,
            "max_dim_mode": "shared",
            "max_dim": 32,
            "max_dim_a": None,
            "max_dim_b": None,
            "spin_sq_target": None,
            "budget": {
                "samples": 4096,
                "recovery_rounds": 8,
                "selected_ci_max_dim": 32,
                "sampling_vqe_iterations": 448,
            },
        },
        "best_accuracy": {
            "samples_per_batch": 1024,
            "num_batches": 16,
            "max_iterations": 12,
            "sampling_state_source": "vqe",
            "sampling_vqe_ansatz_name": "NumberPreserving",
            "sampling_vqe_optimizer_name": "COBYLA",
            "sampling_vqe_max_iterations": 512,
            "sampling_vqe_reps": 2,
            "sampling_vqe_seed": None,
            "energy_tol": 5e-5,
            "occupancies_tol": 5e-5,
            "min_selected_configurations": 2,
            "seed": None,
            "symmetrize_spin": False,
            "carryover_threshold": None,
            "max_dim_mode": "shared",
            "max_dim": 64,
            "max_dim_a": None,
            "max_dim_b": None,
            "spin_sq_target": None,
            "budget": {
                "samples": 16384,
                "recovery_rounds": 12,
                "selected_ci_max_dim": 64,
                "sampling_vqe_iterations": 512,
            },
        },
    },
    "kqd": {
        "fastest": {
            "krylov_dim": 4,
            "time_step": 0.35,
            "evolution_method": "exact",
            "trotter_steps": 1,
            "residual_tolerance": 1e-8,
            "budget": {"krylov_dim": 4},
        },
        "balanced": {
            "krylov_dim": 8,
            "time_step": 0.35,
            "evolution_method": "exact",
            "trotter_steps": 1,
            "residual_tolerance": 1e-8,
            "budget": {"krylov_dim": 8},
        },
        "best_accuracy": {
            "krylov_dim": 12,
            "time_step": 0.5,
            "evolution_method": "exact",
            "trotter_steps": 1,
            "residual_tolerance": 1e-8,
            "budget": {"krylov_dim": 12},
        },
    },
    "qfd": {
        "fastest": {
            "num_time_points": 4,
            "max_time": 0.5,
            "time_grid_type": "linear",
            "trotter_steps": 1,
            "residual_tolerance": 1e-6,
            "budget": {"num_time_points": 4},
        },
        "balanced": {
            "num_time_points": 8,
            "max_time": 2.5,
            "time_grid_type": "linear",
            "trotter_steps": 1,
            "residual_tolerance": 1e-6,
            "budget": {"num_time_points": 8},
        },
        "best_accuracy": {
            "num_time_points": 12,
            "max_time": 4.0,
            "time_grid_type": "geometric",
            "trotter_steps": 1,
            "residual_tolerance": 1e-6,
            "budget": {"num_time_points": 12},
        },
    },
    "qse": {
        "fastest": {
            "reference_method": "hf",
            "excitation_level": "singles",
            "max_subspace_dim": 4,
            "vqe_reference_ansatz_name": "NumberPreserving",
            "vqe_reference_optimizer_name": "COBYLA",
            "vqe_reference_max_iterations": 128,
            "vqe_reference_reps": 1,
            "regularization": 1e-6,
            "overlap_threshold": 1e-4,
            "residual_tolerance": 1e-8,
            "budget": {"max_subspace_dim": 4, "reference_method": "hf"},
        },
        "balanced": {
            "reference_method": "hf",
            "excitation_level": "singles_doubles",
            "max_subspace_dim": 8,
            "vqe_reference_ansatz_name": "NumberPreserving",
            "vqe_reference_optimizer_name": "COBYLA",
            "vqe_reference_max_iterations": 256,
            "vqe_reference_reps": 1,
            "regularization": 1e-7,
            "overlap_threshold": 1e-5,
            "residual_tolerance": 1e-8,
            "budget": {"max_subspace_dim": 8, "reference_method": "hf"},
        },
        "best_accuracy": {
            "reference_method": "hf",
            "excitation_level": "singles_doubles",
            "max_subspace_dim": 12,
            "vqe_reference_ansatz_name": "NumberPreserving",
            "vqe_reference_optimizer_name": "COBYLA",
            "vqe_reference_max_iterations": 512,
            "vqe_reference_reps": 1,
            "regularization": 1e-7,
            "overlap_threshold": 5e-6,
            "residual_tolerance": 1e-8,
            "budget": {"max_subspace_dim": 12, "reference_method": "hf"},
        },
    },
    "skqd": {
        "fastest": {
            "samples_per_state": 512,
            "min_selected_configurations": 2,
            "seed": None,
            "symmetrize_spin": False,
            "max_dim": 16,
            "spin_sq_target": None,
            "krylov_extension_dim": 1,
            "time_step": 0.2,
            "residual_tolerance": 1e-6,
            "budget": {
            "krylov_states": 1,
                "samples_per_state": 512,
                "total_samples": 512,
                "selected_ci_max_dim": 16,
            },
        },
        "balanced": {
            "samples_per_state": 1024,
            "min_selected_configurations": 2,
            "seed": None,
            "symmetrize_spin": False,
            "max_dim": 32,
            "spin_sq_target": None,
            "krylov_extension_dim": 4,
            "time_step": 0.22,
            "residual_tolerance": 1e-6,
            "budget": {
                "krylov_states": 4,
                "samples_per_state": 1024,
                "total_samples": 4096,
                "selected_ci_max_dim": 32,
            },
        },
        "best_accuracy": {
            "samples_per_state": 2048,
            "min_selected_configurations": 2,
            "seed": None,
            "symmetrize_spin": False,
            "max_dim": 64,
            "spin_sq_target": None,
            "krylov_extension_dim": 6,
            "time_step": 0.26,
            "residual_tolerance": 1e-6,
            "budget": {
                "krylov_states": 6,
                "samples_per_state": 2048,
                "total_samples": 12288,
                "selected_ci_max_dim": 64,
            },
        },
    },
}


def _choice_metadata(
    *,
    choice_id: str,
    item: AnsatzMetadata | OptimizerMetadata,
    supported_algorithms: list[str],
    metadata: dict[str, JsonValue],
) -> CatalogChoice:
    """Build a JSON-safe selector entry from shared registry metadata."""
    return {
        "id": choice_id,
        "label": str(item["label"]),
        "aliases": [str(alias) for alias in item["aliases"]],
        "description": str(item["description"]),
        "supported_algorithms": supported_algorithms,
        "metadata": metadata,
    }


def _json_strings(values: list[str]) -> list[JsonValue]:
    """Convert string values to the recursive JSON value type."""
    result: list[JsonValue] = []
    result.extend(values)
    return result


def get_public_catalog() -> PublicCatalog:
    """Return a defensive copy of the cross-service run-configuration catalog."""
    algorithms = [algorithm.value for algorithm in RunAlgorithm]
    ansatzes = [
        _choice_metadata(
            choice_id=str(item["label"]),
            item=item,
            supported_algorithms=[RunAlgorithm.VQE.value, RunAlgorithm.QSE.value],
            metadata={
                "canonical_worker_id": canonical_id,
                "default_reps": item["default_reps"],
            },
        )
        for canonical_id, item in supported_ansatz_metadata().items()
    ]
    optimizers = [
        _choice_metadata(
            choice_id=optimizer_id,
            item=item,
            supported_algorithms=[RunAlgorithm.VQE.value, RunAlgorithm.QSE.value],
            metadata={
                "kind": item["kind"],
                "scipy_method": item["scipy_method"],
                "allowed_options": _json_strings(item["allowed_options"]),
                "supports_max_function_evaluations": item["supports_max_function_evaluations"],
            },
        )
        for optimizer_id, item in supported_optimizer_metadata().items()
    ]
    return {
        "catalog_version": CATALOG_VERSION,
        "algorithms": algorithms,
        "backend_targets": [backend.value for backend in BackendTarget],
        "easy_goals": [goal.value for goal in EasyGoal],
        "easy_goal_presets": deepcopy(PUBLIC_EASY_GOAL_PRESETS),
        "ansatzes": ansatzes,
        "optimizers": optimizers,
        "limits": deepcopy(PUBLIC_LIMITS),
        "defaults": deepcopy(PUBLIC_DEFAULTS),
        "capabilities": deepcopy(PUBLIC_BACKEND_CAPABILITIES),
        "recommendations": deepcopy(PUBLIC_RECOMMENDATIONS),
    }
