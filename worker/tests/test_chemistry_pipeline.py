"""Tests for chemistry pipeline helpers."""

import numpy as np
import pytest

from worker.chemistry.algorithms.qse.workflow import run_qse
from worker.chemistry.algorithms.sqd.workflow import run_sqd
from worker.chemistry.backend_selector import select_backend
from worker.chemistry.eigensolver import build_hf_reference_state
from worker.chemistry.hamiltonian_builder import (
    _hamiltonian_sha256,
    build_qubit_hamiltonian,
)
from worker.chemistry.kqd_solver import run_kqd
from worker.chemistry.molecule_builder import build_molecule
from worker.chemistry.qfd_solver import run_qfd
from worker.chemistry.skqd_solver import run_skqd
from worker.chemistry.types import ChemistryInput
from worker.chemistry.vqe_solver import run_vqe

pytest.importorskip("pyscf")
pytest.importorskip("ffsim")


def _h2_chemistry_input() -> ChemistryInput:
    return ChemistryInput(
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.7414},
        ],
        basis="sto-3g",
        active_space=(2, 2),
    )


def _n2_chemistry_input(active_space: tuple[int, int]) -> ChemistryInput:
    return ChemistryInput(
        atoms=[
            {"symbol": "N", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "N", "x": 0.0, "y": 0.0, "z": 1.0977},
        ],
        basis="sto-3g",
        active_space=active_space,
    )


def test_build_molecule_normalizes_backend_atom_records() -> None:
    """Molecule builder should normalize backend atom records for PySCF usage."""
    prepared = build_molecule(_h2_chemistry_input())

    assert len(prepared.atom_spec) == 2
    assert prepared.atom_spec[0][0] == "H"
    assert prepared.atom_spec[1][1][2] == pytest.approx(0.7414)
    assert prepared.active_space == (2, 2)


def test_build_qubit_hamiltonian_returns_h2_fixture_shapes() -> None:
    """Hamiltonian builder should produce expected H2 STO-3G tensor dimensions."""
    prepared = build_molecule(_h2_chemistry_input())
    bundle = build_qubit_hamiltonian(prepared)

    assert bundle.num_spatial_orbitals == 2
    assert bundle.num_qubits == 4
    assert bundle.one_body_tensor.shape == (2, 2)
    assert bundle.two_body_tensor.shape == (2, 2, 2, 2)
    assert bundle.metadata["pipeline"] == "pyscf+ffsim"
    assert "hf_energy" in bundle.metadata
    assert "casci_energy" in bundle.metadata
    assert bundle.metadata["reference_method"] == "CASCI"
    assert bundle.metadata["reference_backend_target"] == "local_classical"
    assert bundle.metadata["reference_solver_path"] == "pyscf+ffsim"
    assert bundle.metadata["reference_basis"] == "sto-3g"
    assert bundle.metadata["reference_active_space"] == [2, 2]
    assert len(bundle.metadata["hamiltonian_sha256"]) == 64
    manifest = bundle.metadata["problem_manifest"]
    assert manifest["manifest_sha256"] == bundle.metadata["problem_manifest_sha256"]
    assert manifest["molecule"]["atoms"][1]["coordinates"] == pytest.approx([0.0, 0.0, 0.7414])
    assert manifest["sector"]["full_target_sector_dimension"] == 4
    assert manifest["fermion_to_qubit"]["mapping"] == "jordan_wigner"
    assert bundle.metadata["reference_validity_status"] == "valid"
    assert bundle.metadata["active_space_preflight"] == "passed"
    assert bundle.metadata["active_space_capacity"] == {
        "inactive_electrons": 0,
        "frozen_core_orbitals": 0,
        "total_molecular_orbitals": 2,
        "active_orbitals": 2,
    }


def test_hamiltonian_digest_is_stable_and_definition_bound() -> None:
    kwargs = {
        "one_body_tensor": np.eye(2),
        "two_body_tensor": np.zeros((2, 2, 2, 2)),
        "constant": -0.2,
        "basis": "sto-3g",
        "charge": 0,
        "multiplicity": 1,
        "active_space": (2, 2),
    }

    first = _hamiltonian_sha256(**kwargs)
    second = _hamiltonian_sha256(**kwargs)

    assert first == second
    assert first != _hamiltonian_sha256(**{**kwargs, "active_space": (2, 1)})


def test_build_qubit_hamiltonian_rejects_active_space_beyond_virtual_window() -> None:
    prepared = build_molecule(_n2_chemistry_input((8, 8)))

    with pytest.raises(ValueError, match="frozen core orbitals exceeds"):
        build_qubit_hamiltonian(prepared)


def test_active_space_capacity_fails_before_scf(monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = build_molecule(_n2_chemistry_input((8, 8)))

    def fail_if_scf_runs(self) -> None:
        del self
        pytest.fail("invalid active space reached SCF")

    monkeypatch.setattr("pyscf.scf.hf.SCF.kernel", fail_if_scf_runs)

    with pytest.raises(ValueError, match="frozen core orbitals exceeds"):
        build_qubit_hamiltonian(prepared)


def test_build_qubit_hamiltonian_accepts_n2_large_benchmark_active_space() -> None:
    prepared = build_molecule(_n2_chemistry_input((10, 8)))
    bundle = build_qubit_hamiltonian(prepared)

    assert bundle.num_spatial_orbitals == 8
    assert bundle.num_qubits == 16
    assert bundle.one_body_tensor.shape == (8, 8)
    assert bundle.two_body_tensor.shape == (8, 8, 8, 8)


def test_chemistry_selector_and_solver_paths_remain_deterministic() -> None:
    """Selector and solver paths should execute with statevector primitives."""
    chemistry_input = _h2_chemistry_input()
    prepared = build_molecule(chemistry_input)
    bundle = build_qubit_hamiltonian(prepared)

    assert bundle.num_qubits == 4

    statevector = select_backend("statevector")
    assert statevector.capabilities.enabled is True

    aer = select_backend("aer_simulator")
    assert aer.capabilities.enabled is True
    assert aer.capabilities.supports_noise_profile is True

    estimator = statevector.create_estimator()
    vqe_result = run_vqe(
        hamiltonian=bundle,
        backend=estimator,
        config={
            "algorithm": "vqe",
            "max_iterations": 5,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
        },
    )
    assert vqe_result.algorithm == "vqe"
    assert vqe_result.primary_iterations is not None
    assert vqe_result.primary_iterations >= 1
    assert len(vqe_result.convergence_trace) >= 1

    sqd_result = run_sqd(
        hamiltonian=bundle,
        backend=statevector.create_sampler(),
        config={
            "algorithm": "sqd",
            "max_iterations": 3,
            "samples_per_batch": 128,
            "num_batches": 8,
            "num_elec_a": 1,
            "num_elec_b": 1,
        },
    )
    assert sqd_result.algorithm == "sqd"
    assert sqd_result.primary_iterations is not None
    assert sqd_result.primary_iterations >= 1
    assert len(sqd_result.sci_energies) == sqd_result.primary_iterations
    assert "selected_fraction" in sqd_result.postselection_summary
    assert sqd_result.subsampling_summary["num_batches"] == 8
    assert sqd_result.sci_result_package["iterations"] == sqd_result.primary_iterations

    kqd_result = run_kqd(
        hamiltonian=bundle,
        backend=object(),
        config={
            "algorithm": "kqd",
            "krylov_dim": 4,
            "time_step": 0.1,
            "evolution_method": "exact",
        },
    )
    assert kqd_result.algorithm == "kqd"
    assert kqd_result.primary_iterations is not None
    assert kqd_result.primary_iterations >= 1
    assert 1 <= len(kqd_result.ritz_values) <= kqd_result.krylov_rank
    assert "overlap_condition" in kqd_result.orthogonality_metrics

    qfd_result = run_qfd(
        hamiltonian=bundle,
        backend=object(),
        config={
            "algorithm": "qfd",
            "num_time_points": 5,
            "max_time": 0.8,
            "time_grid_type": "linear",
        },
    )
    assert qfd_result.algorithm == "qfd"
    assert qfd_result.primary_iterations == 5
    assert 1 <= len(qfd_result.filter_eigenvalues) <= 5
    assert qfd_result.conditioning_summary["time_points"] == pytest.approx(5.0)

    qse_result = run_qse(
        hamiltonian=bundle,
        backend=estimator,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "vqe",
                "excitation_level": "singles",
                "max_subspace_dim": 4,
                "regularization": 1e-6,
            },
        },
    )
    assert qse_result.algorithm == "qse"
    assert qse_result.primary_iterations is not None
    assert qse_result.primary_iterations >= 1
    assert len(qse_result.eigenvalues) >= 1
    assert qse_result.overlap_condition >= 0.0

    skqd_result = run_skqd(
        hamiltonian=bundle,
        backend=statevector.create_sampler(),
        config={
            "algorithm": "skqd",
            "advanced_config": {
                "algorithm": "skqd",
                "base_sampling_options": {
                    "samples_per_batch": 128,
                    "num_batches": 4,
                    "max_iterations": 3,
                    "num_elec_a": 1,
                    "num_elec_b": 1,
                },
                "krylov_extension_dim": 3,
            },
        },
    )
    assert skqd_result.algorithm == "skqd"
    assert skqd_result.primary_iterations is not None
    assert skqd_result.primary_iterations >= 1
    assert skqd_result.sqd_core["algorithm"] == "sqd"
    assert (
        skqd_result.krylov_extension_diagnostics["selected_solution"]
        == "skqd_sample_union"
    )


def test_number_preserving_vqe_reaches_h2_casci_in_target_sector() -> None:
    """The chemistry VQE must solve H2 without sector leakage."""
    bundle = build_qubit_hamiltonian(build_molecule(_h2_chemistry_input()))

    result = run_vqe(
        hamiltonian=bundle,
        backend=select_backend("statevector").create_estimator(),
        config={
            "algorithm": "vqe",
            "max_iterations": 300,
            "optimizer_name": "COBYLA",
            "ansatz_name": "NumberPreserving",
            "reps": 2,
            "seed": 7,
        },
    )

    assert result.converged is True
    assert result.primary_energy == pytest.approx(bundle.metadata["casci_energy"], abs=1e-6)
    assert result.optimizer_diagnostics["ideal_sector_leakage"] == pytest.approx(
        0.0, abs=1e-12
    )


def test_number_preserving_vqe_h2_baseline_declares_targets_and_budget() -> None:
    """The local-exact H2 baseline records its targets and evaluation budget."""
    bundle = build_qubit_hamiltonian(build_molecule(_h2_chemistry_input()))
    hf_energy = float(bundle.metadata["hf_energy"])
    casci_energy = float(bundle.metadata["casci_energy"])

    result = run_vqe(
        hamiltonian=bundle,
        backend=select_backend("statevector").create_estimator(),
        config={
            "algorithm": "vqe",
            "max_iterations": 300,
            "max_function_evaluations": 448,
            "optimizer_name": "COBYLA",
            "ansatz_name": "NumberPreserving",
            "reps": 2,
            "seed": 7,
        },
    )

    assert bundle.metadata["reference_method"] == "CASCI"
    assert np.isfinite(hf_energy)
    assert np.isfinite(casci_energy)
    assert hf_energy > casci_energy
    assert result.primary_energy == pytest.approx(casci_energy, abs=1e-6)
    assert result.optimizer_diagnostics["ideal_sector_leakage"] == pytest.approx(
        0.0, abs=1e-12
    )
    assert result.optimizer_diagnostics["effective_max_function_evaluations"] == 448
    assert 1 <= result.optimizer_diagnostics["objective_evaluations"] <= 448


def test_full_h2_qse_reaches_casci_with_valid_projected_pencil() -> None:
    """The full allowed H2 QSE space must reproduce the target-sector FCI energy."""
    bundle = build_qubit_hamiltonian(build_molecule(_h2_chemistry_input()))
    reference = build_hf_reference_state(bundle, fallback_dim=2**bundle.num_qubits)

    result = run_qse(
        hamiltonian=bundle,
        backend=select_backend("statevector").create_estimator(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": reference.tolist(),
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 4,
                "residual_tolerance": 1e-9,
            },
        },
    )

    assert result.primary_iterations == 4
    assert result.primary_energy == pytest.approx(bundle.metadata["casci_energy"], abs=1e-9)
    assert result.converged is True
    diagnostics = result.conditioning_summary
    assert diagnostics["overlap_psd"] is True
    assert diagnostics["overlap_psd_min_eigenvalue"] > 0.0
    assert diagnostics["metric_normalization_error"] < 1e-10
    assert diagnostics["max_relative_generalized_residual"] < 1e-10
    assert result.relative_residual is not None
    assert result.relative_residual < 1e-9

    sector_result = run_qse(
        hamiltonian=bundle,
        backend=select_backend("statevector").create_estimator(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 4,
                "residual_tolerance": 1e-9,
            },
        },
    )

    assert sector_result.primary_energy == pytest.approx(bundle.metadata["casci_energy"], abs=1e-9)
    assert sector_result.converged is True
    assert sector_result.relative_residual is not None
    assert sector_result.relative_residual < 1e-9
