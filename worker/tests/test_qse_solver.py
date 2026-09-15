"""Unit tests for QSE reference-state semantics."""

from typing import cast

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.result_adapter import normalize_result
from worker.chemistry.algorithms.qse.config import QSEConfig, resolve_qse_config
from worker.chemistry.algorithms.qse.workflow import (
    _build_excitation_basis,
    _real_scalar,
    _sector_excitation_specs,
    run_qse,
)
from worker.chemistry.backend_selector import select_backend
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.sector_basis import (
    address_to_bitstring,
    apply_fermionic_excitation_sector,
    hartree_fock_sector_state,
    sector_dimension,
)


class _DenseHamiltonian:
    num_qubits = 1

    def __init__(self, matrix: np.ndarray) -> None:
        self.dense_operator_matrix = matrix


def test_qse_configuration_resolves_into_algorithm_owned_record() -> None:
    config = resolve_qse_config(
        {
            "max_subspace_dim": 4,
            "regularization": 1e-6,
            "overlap_threshold": 0.01,
            "residual_tolerance": 1e-5,
            "excitation_level": "singles_doubles",
            "reference_method": "hf",
        }
    )

    assert config == QSEConfig(
        max_subspace_dim=4,
        regularization=1e-6,
        overlap_threshold=0.01,
        residual_tolerance=1e-5,
        excitation_level="singles_doubles",
        reference_method="hf",
    )


@pytest.mark.parametrize("field", ["regularization", "residual_tolerance"])
def test_qse_configuration_rejects_explicit_non_positive_values(field: str) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        resolve_qse_config({field: 0})


def test_qse_configuration_allows_zero_overlap_threshold() -> None:
    assert resolve_qse_config({"overlap_threshold": 0}).overlap_threshold == 0.0


class _SectorHamiltonian:
    def __init__(self, *, norb: int = 7, n_alpha: int = 1, n_beta: int = 1) -> None:
        self.num_spatial_orbitals = norb
        self.num_qubits = 2 * norb
        self.num_electrons_alpha = n_alpha
        self.num_electrons_beta = n_beta
        self.one_body_tensor = np.diag(np.linspace(-1.0, 0.5, norb))
        self.two_body_tensor = np.zeros((norb, norb, norb, norb), dtype=float)
        self.constant = -0.25


class _CoupledSectorAction:
    norb = 4
    nelec = (2, 2)
    dimension = sector_dimension(norb, nelec)

    def __init__(self, coupled_address: int) -> None:
        self.coupled_address = coupled_address

    def matvec(self, _vector: np.ndarray) -> np.ndarray:
        result = np.zeros(self.dimension, dtype=complex)
        result[self.coupled_address] = 1.0
        return result


def test_qse_vqe_reference_uses_exact_emulation_without_requested_backend() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "vqe",
                "max_subspace_dim": 2,
            },
        },
    )

    assert result.execution_mode == "dense_exact_emulation"


def test_qse_sector_excitation_specs_prioritize_coupled_doubles() -> None:
    reference = hartree_fock_sector_state(4, (2, 2))
    target_state = apply_fermionic_excitation_sector(
        reference,
        create_orbitals=(2, 6),
        annihilate_orbitals=(0, 4),
        norb=4,
        nelec=(2, 2),
    )
    action = cast(HamiltonianAction, _CoupledSectorAction(int(np.argmax(np.abs(target_state)))))

    specs = _sector_excitation_specs(reference, action, excitation_level="singles_doubles")

    assert specs[0] == ("double", (2, 6), (0, 4))


def test_qse_vqe_reference_treats_null_options_as_defaults() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    backend = select_backend("statevector").create_estimator()

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "vqe",
                "vqe_reference_ansatz_name": None,
                "vqe_reference_optimizer_name": None,
                "vqe_reference_max_iterations": 8,
                "vqe_reference_reps": 1,
                "max_subspace_dim": 2,
            },
        },
    )

    assert result.algorithm == "qse"
    assert result.primary_energy is not None
    metrics = normalize_result(result)["algorithm_metrics"]
    assert len(metrics["circuit_artifacts"]) == 1
    assert metrics["circuit_artifacts"][0]["role"] == "reference"
    assert metrics["circuit_artifacts"][0]["source"] == "vqe_reference"
    assert metrics["circuit_artifacts"][0]["phase"] == "reference"
    assert metrics["circuit_artifacts"][0]["representative"] is True
    assert metrics["execution_mode"] == "dense_exact_emulation"
    assert metrics["conditioning_summary"]["reference_state_execution"] == "exact_emulation"
    assert metrics["conditioning_summary"]["termination_reason"] in {
        "converged",
        "residual_tolerance_not_met",
        "projected_metric_rank_reduced",
        "projected_metric_not_positive_definite",
        "projected_metric_unstable",
    }
    assert metrics["matrix_element_summary"]["reference_descriptor"]["reference_source"] == (
        "vqe"
    )
    assert metrics["matrix_element_summary"]["reference_descriptor"]["state_fingerprint"]


def test_qse_hf_reference_emits_reference_circuit_artifact() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    backend = select_backend("statevector").create_estimator()

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "max_subspace_dim": 2,
            },
        },
    )

    metrics = normalize_result(result)["algorithm_metrics"]
    assert len(metrics["circuit_artifacts"]) == 1
    assert metrics["circuit_artifacts"][0]["role"] == "reference"
    assert metrics["circuit_artifacts"][0]["source"] == "hf_reference"
    assert metrics["circuit_artifacts"][0]["label"] == "Hartree-Fock reference"


def test_qse_real_scalar_accepts_numerical_imaginary_residue() -> None:
    assert _real_scalar(1.25 + 1e-9j, label="test energy") == pytest.approx(1.25)


def test_qse_reference_energy_tolerates_complex_matrix_residue() -> None:
    hamiltonian = _DenseHamiltonian(
        np.array(
            [
                [1.0, 0.1 + 1e-9j],
                [0.1 - 2e-9j, -1.0],
            ],
            dtype=complex,
        )
    )

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": [1.0, 0.0],
                "excitation_level": "singles",
                "max_subspace_dim": 2,
            },
        },
    )

    assert isinstance(result.reference_state_energy, float)
    assert all(isinstance(value, float) for value in result.eigenvalues)
    assert "circuit_artifacts" not in normalize_result(result)["algorithm_metrics"]


def test_qse_dense_wrapper_preserves_result_and_completion_contract() -> None:
    events: list[dict[str, object]] = []
    result = run_qse(
        hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": [1.0, 0.0],
                "max_subspace_dim": 2,
            },
        },
        progress_callback=events.append,
    )

    completion = events[-1]
    assert completion["algorithm"] == "qse"
    assert completion["stage"] == "completed"
    assert completion["subspace_dim"] == result.primary_iterations
    assert completion["execution_mode"] == "dense_exact_emulation"
    assert result.primary_energy == result.eigenvalues[0]
    assert result.reference_state_energy == 1.0
    assert result.overlap_condition >= 0.0
    assert result.residual_norm is not None
    assert result.relative_residual is not None


def test_qse_sector_wrapper_preserves_completion_metadata_and_result_fields() -> None:
    events: list[dict[str, object]] = []
    result = run_qse(
        hamiltonian=_SectorHamiltonian(),
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "max_subspace_dim": 2,
            },
        },
        progress_callback=events.append,
    )

    completion = events[-1]
    assert completion["execution_mode"] == "sector_matrix_free"
    assert completion["sector_dimension"] == 49
    assert completion["num_spatial_orbitals"] == 7
    assert completion["subspace_dim"] == result.primary_iterations
    assert result.algorithm == "qse"
    assert result.primary_energy == result.eigenvalues[0]
    assert result.overlap_condition >= 0.0
    assert result.relative_residual is not None


def test_qse_provided_state_accepts_complex_json_scalars() -> None:
    hamiltonian = _DenseHamiltonian(
        np.array(
            [
                [0.0, 0.2],
                [0.2, -1.0],
            ],
            dtype=complex,
        )
    )

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 1.0}],
                "excitation_level": "singles",
                "max_subspace_dim": 2,
            },
        },
    )

    assert result.reference_state_energy == pytest.approx(-0.5)
    assert result.primary_energy is not None


def test_qse_singles_doubles_expands_subspace() -> None:
    hamiltonian = _DenseHamiltonian(np.diag(np.linspace(-1.0, 1.0, 16)).astype(complex))
    backend = select_backend("statevector").create_estimator()
    reference = [0.0] * 16
    reference[5] = 1.0

    singles = run_qse(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": reference,
                "excitation_level": "singles",
                "max_subspace_dim": 16,
            },
        },
    )
    singles_doubles = run_qse(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": reference,
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 16,
            },
        },
    )

    assert singles.primary_iterations == 3
    assert singles_doubles.primary_iterations is not None
    assert singles_doubles.primary_iterations > singles.primary_iterations


def test_qse_dense_excitation_basis_preserves_spin_sector() -> None:
    reference = np.zeros(16, dtype=complex)
    reference[5] = 1.0
    operator = np.diag(np.linspace(-1.0, 1.0, 16)).astype(complex)

    basis = _build_excitation_basis(
        reference,
        operator,
        excitation_level="singles_doubles",
        target_rank=16,
        overlap_threshold=1e-10,
        regularization=1e-8,
        progress_callback=None,
    )

    support = {
        basis_index
        for vector in basis
        for basis_index, amplitude in enumerate(np.asarray(vector, dtype=complex))
        if abs(amplitude) > 1e-10
    }

    assert support
    assert support.issubset({5, 6, 9, 10})


def test_qse_basis_uses_fermionic_singles_not_hamiltonian_powers() -> None:
    reference = np.zeros(16, dtype=complex)
    reference[5] = 1.0
    operator = np.zeros((16, 16), dtype=complex)
    operator[1, 5] = 1.0
    operator[5, 1] = 1.0

    basis = _build_excitation_basis(
        reference,
        operator,
        excitation_level="singles",
        target_rank=4,
        overlap_threshold=1e-10,
        regularization=1e-8,
        progress_callback=None,
    )

    assert len(basis) >= 2
    assert basis[0] == pytest.approx(reference)
    expected_single = np.zeros(16, dtype=complex)
    expected_single[6] = 1.0
    assert basis[1] == pytest.approx(expected_single)
    assert not np.allclose(basis[1], operator @ reference)


def test_qse_overlap_threshold_prunes_dependent_excitation_states() -> None:
    hamiltonian = _DenseHamiltonian(np.diag(np.linspace(-1.0, 1.0, 16)).astype(complex))

    loose_threshold = run_qse(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": [
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
                "excitation_level": "singles",
                "max_subspace_dim": 16,
                "overlap_threshold": 1.1,
            },
        },
    )
    strict_threshold = run_qse(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": [
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
                "excitation_level": "singles",
                "max_subspace_dim": 16,
                "overlap_threshold": 1e-10,
            },
        },
    )

    assert loose_threshold.primary_iterations == 1
    assert strict_threshold.primary_iterations is not None
    assert strict_threshold.primary_iterations > 1


def test_qse_marks_large_projected_residual_as_not_converged() -> None:
    hamiltonian = SparsePauliOp.from_list([("ZZ", 0.5), ("XI", 0.2), ("IX", -0.15)])
    backend = select_backend("statevector").create_estimator()

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": [1.0, 0.0, 0.0, 0.0],
                "excitation_level": "singles",
                "max_subspace_dim": 4,
            },
        },
    )

    assert result.converged is False
    assert result.relative_residual is not None
    assert result.convergence_threshold is not None
    assert result.relative_residual > result.convergence_threshold


def test_qse_preserves_configured_residual_tolerance() -> None:
    hamiltonian = SparsePauliOp.from_list([("ZZ", 0.5), ("XI", 0.2), ("IX", -0.15)])
    backend = select_backend("statevector").create_estimator()

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=backend,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_state",
                "provided_state_vector": [1.0, 0.0, 0.0, 0.0],
                "excitation_level": "singles",
                "max_subspace_dim": 4,
                "residual_tolerance": 1e-3,
            },
        },
    )

    assert result.convergence_threshold == pytest.approx(1e-3)


def test_qse_hf_sector_path_does_not_materialize_dense_matrix(monkeypatch: pytest.MonkeyPatch):
    def _fail_dense_resolution(*args, **kwargs):
        del args, kwargs
        raise AssertionError("QSE sector path should not resolve a dense matrix")

    monkeypatch.setattr(
        "worker.chemistry.algorithms.qse.workflow.resolve_operator_matrix",
        _fail_dense_resolution,
    )

    result = run_qse(
        hamiltonian=_SectorHamiltonian(),
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles",
                "max_subspace_dim": 4,
                "residual_tolerance": 1e-8,
            },
        },
    )

    assert result.algorithm == "qse"
    assert result.primary_iterations == 4
    assert result.primary_energy is not None
    assert result.overlap_condition >= 0.0


def test_qse_provided_sector_reference_uses_sparse_amplitudes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_dense_resolution(*args, **kwargs):
        del args, kwargs
        raise AssertionError("QSE provided_sector path should not resolve a dense matrix")

    monkeypatch.setattr(
        "worker.chemistry.algorithms.qse.workflow.resolve_operator_matrix",
        _fail_dense_resolution,
    )
    bitstring = address_to_bitstring(0, norb=7, nelec=(1, 1))

    result = run_qse(
        hamiltonian=_SectorHamiltonian(),
        backend=object(),
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "provided_sector",
                "provided_sector_amplitudes": [
                    {"bitstring": bitstring, "amplitude": 1.0},
                ],
                "excitation_level": "singles",
                "max_subspace_dim": 4,
                "residual_tolerance": 1e-8,
            },
        },
    )

    assert result.primary_energy is not None
    assert result.primary_iterations == 4


def test_qse_provided_state_requires_state_vector() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    with pytest.raises(ValueError, match="requires provided_state_vector"):
        run_qse(
            hamiltonian=hamiltonian,
            backend=object(),
            config={
                "algorithm": "qse",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "provided_state",
                    "max_subspace_dim": 2,
                },
            },
        )


def test_qse_rejects_unknown_reference_method() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])

    with pytest.raises(ValueError, match="Unsupported QSE reference_method"):
        run_qse(
            hamiltonian=hamiltonian,
            backend=object(),
            config={
                "algorithm": "qse",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "unsupported",
                    "max_subspace_dim": 2,
                },
            },
        )


def test_qse_rejects_unknown_excitation_level() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    backend = select_backend("statevector").create_estimator()

    with pytest.raises(ValueError, match="Unsupported QSE excitation_level"):
        run_qse(
            hamiltonian=hamiltonian,
            backend=backend,
            config={
                "algorithm": "qse",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "provided_state",
                    "provided_state_vector": [1.0, 0.0],
                    "excitation_level": "triples",
                    "max_subspace_dim": 2,
                },
            },
        )
