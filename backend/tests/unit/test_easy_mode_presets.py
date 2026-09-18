from __future__ import annotations

import pytest
from app.models.enums import BackendTarget, EasyGoal, RunAlgorithm
from app.models.molecule import Molecule
from app.schemas.run import SQDAdvancedConfig
from app.services.easy_mode_presets import (
    EASY_MODE_CATALOG_VERSION,
    _split_electrons,
    build_easy_mode_advanced_config,
    build_easy_mode_metadata,
)


def _molecule_with_active_space(
    n_electrons: int | None,
    *,
    n_orbitals: int = 4,
) -> Molecule | None:
    if n_electrons is None:
        return None
    return Molecule(
        name="test",
        atoms=[],
        charge=0,
        multiplicity=1,
        active_space={"n_electrons": n_electrons, "n_orbitals": n_orbitals},
    )


@pytest.mark.parametrize(
    ("algorithm", "goal", "expected"),
    [
        (
            RunAlgorithm.VQE,
            EasyGoal.FASTEST,
            {
                "algorithm": "vqe",
                "ansatz_name": "NumberPreserving",
                "optimizer_name": "COBYLA",
                "max_iterations": 128,
                "max_function_evaluations": 128,
                "reps": 2,
            },
        ),
        (
            RunAlgorithm.VQE,
            EasyGoal.BALANCED,
            {
                "algorithm": "vqe",
                "ansatz_name": "NumberPreserving",
                "optimizer_name": "COBYLA",
                "max_iterations": 448,
                "max_function_evaluations": 448,
                "reps": 2,
                "initial_point_candidates": 2,
            },
        ),
        (
            RunAlgorithm.VQE,
            EasyGoal.BEST_ACCURACY,
            {
                "algorithm": "vqe",
                "ansatz_name": "NumberPreserving",
                "optimizer_name": "COBYLA",
                "max_iterations": 512,
                "max_function_evaluations": 512,
                "reps": 2,
            },
        ),
        (
            RunAlgorithm.SQD,
            EasyGoal.FASTEST,
            {
                "algorithm": "sqd",
                "samples_per_batch": 256,
                "num_batches": 4,
                "max_iterations": 4,
                "energy_tol": 1e-4,
                "min_selected_configurations": 2,
                "max_dim": 16,
            },
        ),
        (
            RunAlgorithm.SQD,
            EasyGoal.BALANCED,
            {
                "algorithm": "sqd",
                "samples_per_batch": 512,
                "num_batches": 8,
                "max_iterations": 8,
                "energy_tol": 7.5e-5,
                "min_selected_configurations": 2,
                "max_dim": 32,
            },
        ),
        (
            RunAlgorithm.SQD,
            EasyGoal.BEST_ACCURACY,
            {
                "algorithm": "sqd",
                "samples_per_batch": 1024,
                "num_batches": 16,
                "max_iterations": 12,
                "energy_tol": 5e-5,
                "min_selected_configurations": 2,
                "max_dim": 64,
            },
        ),
        (
            RunAlgorithm.KQD,
            EasyGoal.FASTEST,
            {
                "algorithm": "kqd",
                "krylov_dim": 4,
                "time_step": 0.35,
                "residual_tolerance": 1e-8,
            },
        ),
        (
            RunAlgorithm.KQD,
            EasyGoal.BALANCED,
            {
                "algorithm": "kqd",
                "krylov_dim": 8,
                "time_step": 0.35,
                "residual_tolerance": 1e-8,
            },
        ),
        (
            RunAlgorithm.KQD,
            EasyGoal.BEST_ACCURACY,
            {
                "algorithm": "kqd",
                "krylov_dim": 12,
                "time_step": 0.5,
                "residual_tolerance": 1e-8,
            },
        ),
        (
            RunAlgorithm.QFD,
            EasyGoal.FASTEST,
            {
                "algorithm": "qfd",
                "num_time_points": 4,
                "max_time": 0.5,
                "residual_tolerance": 1e-6,
            },
        ),
        (
            RunAlgorithm.QFD,
            EasyGoal.BALANCED,
            {
                "algorithm": "qfd",
                "num_time_points": 8,
                "max_time": 2.5,
                "residual_tolerance": 1e-6,
            },
        ),
        (
            RunAlgorithm.QFD,
            EasyGoal.BEST_ACCURACY,
            {
                "algorithm": "qfd",
                "num_time_points": 12,
                "max_time": 4.0,
                "residual_tolerance": 1e-6,
            },
        ),
        (
            RunAlgorithm.QSE,
            EasyGoal.FASTEST,
            {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles",
                "max_subspace_dim": 4,
                "residual_tolerance": 1e-8,
            },
        ),
        (
            RunAlgorithm.QSE,
            EasyGoal.BALANCED,
            {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 8,
                "residual_tolerance": 1e-8,
            },
        ),
        (
            RunAlgorithm.QSE,
            EasyGoal.BEST_ACCURACY,
            {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 12,
                "residual_tolerance": 1e-8,
            },
        ),
        (
            RunAlgorithm.SKQD,
            EasyGoal.FASTEST,
            {
                "algorithm": "skqd",
                "krylov_extension_dim": 1,
                "samples_per_state": 512,
                "residual_tolerance": 1e-6,
            },
        ),
        (
            RunAlgorithm.SKQD,
            EasyGoal.BALANCED,
            {
                "algorithm": "skqd",
                "krylov_extension_dim": 4,
                "samples_per_state": 1024,
                "residual_tolerance": 1e-6,
            },
        ),
        (
            RunAlgorithm.SKQD,
            EasyGoal.BEST_ACCURACY,
            {
                "algorithm": "skqd",
                "krylov_extension_dim": 6,
                "samples_per_state": 2048,
                "residual_tolerance": 1e-6,
            },
        ),
    ],
)
def test_build_easy_mode_advanced_config_covers_algorithm_goal_matrix(
    algorithm: RunAlgorithm,
    goal: EasyGoal,
    expected: dict[str, object],
) -> None:
    molecule = (
        _molecule_with_active_space(4)
        if algorithm in {RunAlgorithm.SQD, RunAlgorithm.SKQD}
        else None
    )

    config = build_easy_mode_advanced_config(
        algorithm=algorithm,
        goal=goal,
        molecule=molecule,
    )

    for key, value in expected.items():
        assert config[key] == value

    if algorithm == RunAlgorithm.SQD:
        assert config["sampling_state_source"] == "vqe"
        assert config["sampling_vqe_ansatz_name"] == "NumberPreserving"
        assert config["sampling_vqe_optimizer_name"] == "COBYLA"
        assert config["sampling_vqe_max_iterations"] in {128, 448, 512}
        assert config["sampling_vqe_reps"] in {1, 2}
        assert config["num_elec_a"] == 2
        assert config["num_elec_b"] == 2
        assert config["min_selected_configurations"] == 2
        assert config["carryover_threshold"] is None
        assert config["symmetrize_spin"] is False
    if algorithm == RunAlgorithm.SKQD:
        assert config["base_sampling_options"]["num_elec_a"] == 2
        assert config["base_sampling_options"]["num_elec_b"] == 2
        assert config["base_sampling_options"]["min_selected_configurations"] == 2
        assert config["base_sampling_options"]["max_dim"] in {16, 32, 64}
        assert "carryover_threshold" not in config["base_sampling_options"]
        assert config["base_sampling_options"]["symmetrize_spin"] is False


@pytest.mark.parametrize(
    ("total_electrons", "expected"),
    [
        (None, None),
        (4, {"num_elec_a": 2, "num_elec_b": 2}),
        (5, {"num_elec_a": 2, "num_elec_b": 3}),
    ],
)
def test_split_electrons_handles_missing_even_and_odd_counts(
    total_electrons: int | None,
    expected: dict[str, int] | None,
) -> None:
    assert _split_electrons(total_electrons) == expected


def test_build_easy_mode_metadata_defaults_goal_and_omits_qse_policy_for_non_qse() -> None:
    metadata = build_easy_mode_metadata(
        algorithm=RunAlgorithm.VQE,
        goal=None,
        molecule=None,
    )

    assert metadata == {
        "catalog_version": EASY_MODE_CATALOG_VERSION,
        "goal": None,
        "expanded_advanced_config": {
            "algorithm": "vqe",
            "ansatz_name": "NumberPreserving",
            "optimizer_name": "COBYLA",
            "max_iterations": 448,
            "max_function_evaluations": 448,
            "reps": 2,
            "initial_point_strategy": "zero_plus_seeded_random",
            "initial_point_candidates": 2,
            "seed": None,
            "convergence_threshold": None,
        },
    }


def test_build_easy_mode_metadata_adds_qse_reference_policy() -> None:
    metadata = build_easy_mode_metadata(
        algorithm=RunAlgorithm.QSE,
        goal=EasyGoal.FASTEST,
        molecule=None,
    )

    assert metadata["catalog_version"] == EASY_MODE_CATALOG_VERSION
    assert metadata["goal"] == EasyGoal.FASTEST.value
    assert metadata["reference_solve_policy"] == "hf_easy_mode"
    assert metadata["expanded_advanced_config"]["algorithm"] == RunAlgorithm.QSE.value


@pytest.mark.parametrize("goal", list(EasyGoal))
def test_build_easy_mode_kqd_uses_trotter_evolution_for_noisy_aer(goal: EasyGoal) -> None:
    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.KQD,
        goal=goal,
        molecule=None,
        backend_target=BackendTarget.AER_SIMULATOR,
        has_noise_profile=True,
    )

    assert config["evolution_method"] == "trotter"
    assert config["trotter_steps"] == 1


def test_build_easy_mode_kqd_keeps_exact_statevector_preset() -> None:
    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.KQD,
        goal=EasyGoal.FASTEST,
        molecule=None,
        backend_target=BackendTarget.STATEVECTOR,
    )

    assert config["evolution_method"] == "exact"
    assert config["trotter_steps"] == 1


def test_build_easy_mode_qse_uses_hf_reference_for_small_and_large_active_space() -> None:
    small_molecule = _molecule_with_active_space(2, n_orbitals=5)
    molecule = _molecule_with_active_space(8, n_orbitals=8)

    small_config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.QSE,
        goal=EasyGoal.BALANCED,
        molecule=small_molecule,
    )
    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.QSE,
        goal=EasyGoal.BALANCED,
        molecule=molecule,
    )
    metadata = build_easy_mode_metadata(
        algorithm=RunAlgorithm.QSE,
        goal=EasyGoal.BALANCED,
        molecule=molecule,
    )

    assert small_config["reference_method"] == "hf"
    assert "vqe_reference_max_iterations" not in small_config
    assert config["reference_method"] == "hf"
    assert "vqe_reference_max_iterations" not in config
    assert metadata["reference_solve_policy"] == "hf_easy_mode"


def test_build_easy_mode_vqe_uses_shared_budget_for_h2_like_active_spaces() -> None:
    molecule = _molecule_with_active_space(2, n_orbitals=2)

    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.VQE,
        goal=EasyGoal.BALANCED,
        molecule=molecule,
    )

    assert config["ansatz_name"] == "NumberPreserving"
    assert config["optimizer_name"] == "COBYLA"
    assert config["max_iterations"] == 448
    assert config["max_function_evaluations"] == 448
    assert config["reps"] == 2
    assert config["initial_point_candidates"] == 2


def test_build_easy_mode_vqe_uses_shared_best_accuracy_budget_without_noise() -> None:
    molecule = _molecule_with_active_space(2, n_orbitals=2)

    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.VQE,
        goal=EasyGoal.BEST_ACCURACY,
        molecule=molecule,
        backend_target=BackendTarget.STATEVECTOR,
    )

    assert config["ansatz_name"] == "NumberPreserving"
    assert config["optimizer_name"] == "COBYLA"
    assert config["max_iterations"] == 512
    assert config["max_function_evaluations"] == 512
    assert config["reps"] == 2
    assert config["initial_point_candidates"] == 4


def test_build_easy_mode_vqe_uses_shared_best_accuracy_budget_with_noise() -> None:
    molecule = _molecule_with_active_space(2, n_orbitals=2)

    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.VQE,
        goal=EasyGoal.BEST_ACCURACY,
        molecule=molecule,
        backend_target=BackendTarget.AER_SIMULATOR,
        has_noise_profile=True,
    )

    assert config["ansatz_name"] == "NumberPreserving"
    assert config["optimizer_name"] == "COBYLA"
    assert config["max_iterations"] == 512
    assert config["max_function_evaluations"] == 512
    assert config["reps"] == 2
    assert config["initial_point_candidates"] == 4


@pytest.mark.parametrize(
    ("algorithm", "backend_target", "has_noise_profile", "expected"),
    [
        (
            RunAlgorithm.VQE,
            BackendTarget.IBM_RUNTIME,
            False,
            {"ansatz_name": "NumberPreserving", "max_function_evaluations": 512},
        ),
        (
            RunAlgorithm.KQD,
            BackendTarget.IBM_RUNTIME,
            False,
            {"krylov_dim": 12},
        ),
        (
            RunAlgorithm.QFD,
            BackendTarget.AER_SIMULATOR,
            True,
            {"num_time_points": 12},
        ),
    ],
)
def test_easy_mode_applies_shared_backend_noise_cap_to_all_callers(
    algorithm: RunAlgorithm,
    backend_target: BackendTarget,
    has_noise_profile: bool,
    expected: dict[str, object],
) -> None:
    molecule = (
        _molecule_with_active_space(2, n_orbitals=2) if algorithm == RunAlgorithm.VQE else None
    )

    config = build_easy_mode_advanced_config(
        algorithm=algorithm,
        goal=EasyGoal.BEST_ACCURACY,
        molecule=molecule,
        backend_target=backend_target,
        has_noise_profile=has_noise_profile,
    )

    for key, value in expected.items():
        assert config[key] == value


def test_build_easy_mode_keeps_projected_kqd_qfd_dimensions_for_target_paths() -> None:
    kqd_ibm = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.KQD,
        goal=EasyGoal.BALANCED,
        molecule=None,
        backend_target=BackendTarget.IBM_RUNTIME,
    )
    qfd_ibm = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.QFD,
        goal=EasyGoal.BEST_ACCURACY,
        molecule=None,
        backend_target=BackendTarget.IBM_RUNTIME,
    )
    kqd_noisy_aer = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.KQD,
        goal=EasyGoal.BEST_ACCURACY,
        molecule=None,
        backend_target=BackendTarget.AER_SIMULATOR,
        has_noise_profile=True,
    )

    assert kqd_ibm["krylov_dim"] == 8
    assert kqd_ibm["evolution_method"] == "trotter"
    assert qfd_ibm["num_time_points"] == 12
    assert kqd_noisy_aer["krylov_dim"] == 12
    assert kqd_noisy_aer["evolution_method"] == "trotter"


def test_build_easy_mode_qse_uses_hf_reference_for_ibm_measured_path() -> None:
    molecule = _molecule_with_active_space(2, n_orbitals=2)

    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.QSE,
        goal=EasyGoal.BALANCED,
        molecule=molecule,
        backend_target=BackendTarget.IBM_RUNTIME,
    )
    metadata = build_easy_mode_metadata(
        algorithm=RunAlgorithm.QSE,
        goal=EasyGoal.BALANCED,
        molecule=molecule,
        backend_target=BackendTarget.IBM_RUNTIME,
    )

    assert config["reference_method"] == "hf"
    assert "vqe_reference_max_iterations" not in config
    assert metadata["reference_solve_policy"] == "hf_easy_mode"


def test_build_easy_mode_advanced_config_sqd_skips_electron_injection_without_active_space() -> (
    None
):
    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.SQD,
        goal=EasyGoal.BALANCED,
        molecule=None,
    )

    assert "num_elec_a" not in config
    assert "num_elec_b" not in config


def test_build_easy_mode_advanced_config_skqd_skips_electron_injection_without_active_space() -> (
    None
):
    config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.SKQD,
        goal=EasyGoal.BALANCED,
        molecule=None,
    )

    assert "num_elec_a" not in config["base_sampling_options"]
    assert "num_elec_b" not in config["base_sampling_options"]


def test_sqd_schema_exposes_seed_and_min_selected_configuration_contract() -> None:
    config = SQDAdvancedConfig(
        algorithm=RunAlgorithm.SQD,
        samples_per_batch=64,
        num_batches=2,
        max_iterations=3,
        num_elec_a=None,
        num_elec_b=None,
        energy_tol=None,
        occupancies_tol=None,
        seed=0,
        min_selected_configurations=4,
        symmetrize_spin=None,
        carryover_threshold=None,
        max_dim=None,
        spin_sq_target=None,
        sci_solver_options=None,
    )

    dumped = config.model_dump()
    assert dumped["seed"] == 0
    assert dumped["min_selected_configurations"] == 4


def test_build_easy_mode_advanced_config_ignores_invalid_active_space_electron_values() -> None:
    molecule = Molecule(
        name="test-invalid-active-space",
        atoms=[],
        charge=0,
        multiplicity=1,
        active_space={"n_electrons": True, "n_orbitals": 4},
    )

    sqd_config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.SQD,
        goal=EasyGoal.FASTEST,
        molecule=molecule,
    )
    skqd_config = build_easy_mode_advanced_config(
        algorithm=RunAlgorithm.SKQD,
        goal=EasyGoal.FASTEST,
        molecule=molecule,
    )

    assert "num_elec_a" not in sqd_config
    assert "num_elec_b" not in sqd_config
    assert "num_elec_a" not in skqd_config["base_sampling_options"]
    assert "num_elec_b" not in skqd_config["base_sampling_options"]


def test_build_easy_mode_advanced_config_rejects_unsupported_algorithm() -> None:
    with pytest.raises(ValueError, match="Unsupported easy-mode algorithm 'None'"):
        build_easy_mode_advanced_config(
            algorithm=None,
            goal=EasyGoal.BALANCED,
            molecule=None,
        )
