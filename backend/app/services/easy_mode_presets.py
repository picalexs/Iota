"""Easy-mode preset builders for run expansion."""

from __future__ import annotations

from typing import Any

from app.models.enums import BackendTarget, EasyGoal, RunAlgorithm
from app.models.molecule import Molecule
from app.services.active_space import extract_active_space
from shared.contracts.catalog import CATALOG_VERSION, get_public_recommendation_config

# Compatibility name retained for stored run metadata and existing imports.
EASY_MODE_CATALOG_VERSION = CATALOG_VERSION


def _active_space_electrons(molecule: Molecule | None) -> int | None:
    n_electrons, _ = extract_active_space(molecule)
    return n_electrons


def _active_space_orbitals(molecule: Molecule | None) -> int | None:
    _, n_orbitals = extract_active_space(molecule)
    return n_orbitals


def _split_electrons(total_electrons: int | None) -> dict[str, int] | None:
    if total_electrons is None:
        return None

    num_elec_a = total_electrons // 2
    num_elec_b = total_electrons - num_elec_a
    return {"num_elec_a": num_elec_a, "num_elec_b": num_elec_b}


def _normalize_backend_target(backend_target: BackendTarget | str | None) -> str | None:
    if isinstance(backend_target, BackendTarget):
        return backend_target.value
    if isinstance(backend_target, str) and backend_target.strip():
        return backend_target.strip().lower()
    return None


def _qse_reference_solve_policy(
    *,
    backend_target: BackendTarget | str | None,
    molecule: Molecule | None,
) -> str:
    return "hf_easy_mode"


def build_easy_mode_metadata(
    *,
    algorithm: RunAlgorithm | None,
    goal: EasyGoal | None,
    molecule: Molecule | None,
    backend_target: BackendTarget | str | None = None,
    has_noise_profile: bool = False,
) -> dict[str, Any]:
    """Build metadata payload stored under run_metadata.easy_mode."""
    effective_goal = goal or EasyGoal.BALANCED
    metadata: dict[str, Any] = {
        "catalog_version": EASY_MODE_CATALOG_VERSION,
        "goal": goal.value if goal else None,
        "expanded_advanced_config": build_easy_mode_advanced_config(
            algorithm=algorithm,
            goal=effective_goal,
            molecule=molecule,
            backend_target=backend_target,
            has_noise_profile=has_noise_profile,
        ),
    }

    if algorithm == RunAlgorithm.QSE:
        metadata["reference_solve_policy"] = _qse_reference_solve_policy(
            backend_target=backend_target,
            molecule=molecule,
        )

    return metadata


def _build_vqe_easy_mode_advanced_config(
    *,
    goal: EasyGoal,
    molecule: Molecule | None,
    backend_target: BackendTarget | str | None,
    has_noise_profile: bool,
) -> dict[str, Any]:
    del molecule, backend_target, has_noise_profile
    return {
        "algorithm": RunAlgorithm.VQE.value,
        **get_public_recommendation_config(
            algorithm=RunAlgorithm.VQE.value,
            goal=goal.value,
        ),
    }


def _build_sqd_easy_mode_advanced_config(
    *,
    goal: EasyGoal,
    molecule: Molecule | None,
) -> dict[str, Any]:
    expanded = {
        "algorithm": RunAlgorithm.SQD.value,
        **get_public_recommendation_config(
            algorithm=RunAlgorithm.SQD.value,
            goal=goal.value,
        ),
    }
    expanded_electrons = _split_electrons(_active_space_electrons(molecule))
    if expanded_electrons is not None:
        expanded.update(expanded_electrons)
    return expanded


def _build_kqd_easy_mode_advanced_config(
    *,
    goal: EasyGoal,
    backend_target: BackendTarget | str | None,
    has_noise_profile: bool,
) -> dict[str, Any]:
    config = {
        "algorithm": RunAlgorithm.KQD.value,
        **get_public_recommendation_config(
            algorithm=RunAlgorithm.KQD.value,
            goal=goal.value,
        ),
    }
    normalized_target = _normalize_backend_target(backend_target)
    if normalized_target == BackendTarget.IBM_RUNTIME.value or (
        normalized_target == BackendTarget.AER_SIMULATOR.value and has_noise_profile
    ):
        # Exact evolution is a local emulation shortcut. Projected matrix
        # elements on noisy Aer and IBM must come from Trotter circuits.
        config["evolution_method"] = "trotter"
    return config


def _build_qfd_easy_mode_advanced_config(
    *,
    goal: EasyGoal,
    backend_target: BackendTarget | str | None,
    has_noise_profile: bool,
) -> dict[str, Any]:
    del backend_target, has_noise_profile
    return {
        "algorithm": RunAlgorithm.QFD.value,
        **get_public_recommendation_config(
            algorithm=RunAlgorithm.QFD.value,
            goal=goal.value,
        ),
    }


def _build_qse_easy_mode_advanced_config(
    *,
    goal: EasyGoal,
    molecule: Molecule | None,
    backend_target: BackendTarget | str | None,
) -> dict[str, Any]:
    def _qse_config(
        *,
        excitation_level: str,
        max_subspace_dim: int,
        regularization: float,
        overlap_threshold: float,
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "algorithm": RunAlgorithm.QSE.value,
            **get_public_recommendation_config(
                algorithm=RunAlgorithm.QSE.value,
                goal=goal.value,
            ),
        }
        config["reference_method"] = "hf"
        config["excitation_level"] = excitation_level
        config["max_subspace_dim"] = max_subspace_dim
        config["regularization"] = regularization
        config["overlap_threshold"] = overlap_threshold
        for key in (
            "vqe_reference_ansatz_name",
            "vqe_reference_optimizer_name",
            "vqe_reference_max_iterations",
            "vqe_reference_reps",
        ):
            config.pop(key, None)
        return config

    presets = {
        EasyGoal.FASTEST: _qse_config(
            excitation_level="singles",
            max_subspace_dim=4,
            regularization=1e-6,
            overlap_threshold=1e-4,
        ),
        EasyGoal.BALANCED: _qse_config(
            excitation_level="singles_doubles",
            max_subspace_dim=8,
            regularization=1e-7,
            overlap_threshold=1e-5,
        ),
        EasyGoal.BEST_ACCURACY: _qse_config(
            excitation_level="singles_doubles",
            max_subspace_dim=12,
            regularization=1e-7,
            overlap_threshold=5e-6,
        ),
    }
    return presets[goal]


def build_easy_mode_advanced_config(
    *,
    algorithm: RunAlgorithm | None,
    goal: EasyGoal,
    molecule: Molecule | None,
    backend_target: BackendTarget | str | None = None,
    has_noise_profile: bool = False,
) -> dict[str, Any]:
    """Build deterministic advanced config expansion for easy mode."""
    if algorithm == RunAlgorithm.VQE:
        return _build_vqe_easy_mode_advanced_config(
            goal=goal,
            molecule=molecule,
            backend_target=backend_target,
            has_noise_profile=has_noise_profile,
        )

    if algorithm == RunAlgorithm.SQD:
        return _build_sqd_easy_mode_advanced_config(goal=goal, molecule=molecule)

    if algorithm == RunAlgorithm.KQD:
        return _build_kqd_easy_mode_advanced_config(
            goal=goal,
            backend_target=backend_target,
            has_noise_profile=has_noise_profile,
        )

    if algorithm == RunAlgorithm.QFD:
        return _build_qfd_easy_mode_advanced_config(
            goal=goal,
            backend_target=backend_target,
            has_noise_profile=has_noise_profile,
        )

    if algorithm == RunAlgorithm.QSE:
        return _build_qse_easy_mode_advanced_config(
            goal=goal,
            molecule=molecule,
            backend_target=backend_target,
        )

    if algorithm == RunAlgorithm.SKQD:
        return build_skqd_easy_mode_advanced_config(goal, molecule)

    raise ValueError(f"Unsupported easy-mode algorithm '{algorithm}'")


def build_skqd_easy_mode_advanced_config(
    goal: EasyGoal,
    molecule: Molecule | None,
) -> dict[str, Any]:
    """Build the deterministic SKQD easy-mode advanced config."""
    recommendation = get_public_recommendation_config(
        algorithm=RunAlgorithm.SKQD.value,
        goal=goal.value,
    )
    sampling_keys = {
        "min_selected_configurations",
        "seed",
        "symmetrize_spin",
        "max_dim",
        "spin_sq_target",
    }
    expanded: dict[str, Any] = {
        "algorithm": RunAlgorithm.SKQD.value,
        "samples_per_state": recommendation["samples_per_state"],
        "base_sampling_options": {
            key: value for key, value in recommendation.items() if key in sampling_keys
        },
        "krylov_extension_dim": recommendation["krylov_extension_dim"],
        "time_step": recommendation["time_step"],
        "residual_tolerance": recommendation["residual_tolerance"],
    }
    expanded_electrons = _split_electrons(_active_space_electrons(molecule))
    if expanded_electrons is not None:
        expanded["base_sampling_options"] = {
            **expanded["base_sampling_options"],
            **expanded_electrons,
        }
    return expanded
