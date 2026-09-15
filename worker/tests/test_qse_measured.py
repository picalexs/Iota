"""Unit tests for measured-matrix-element QSE (noisy/hardware targets)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import Operator, SparsePauliOp, Statevector

from worker.adapters.result_adapter import normalize_result
from worker.chemistry.algorithms.qse.excitations import apply_fermionic_excitation
from worker.chemistry.algorithms.qse.measured import (
    _estimator_pub_chunk_size,
    build_measured_excitation_operators,
    estimate_measured_qse_matrices,
)
from worker.chemistry.algorithms.qse.workflow import run_qse
from worker.chemistry.eigensolver import solve_stabilized_generalized_eigenproblem
from worker.chemistry.reference_states import build_hf_reference_state


def test_measured_qse_accepts_bounded_aer_pub_chunk_override() -> None:
    context = SimpleNamespace(
        backend_target="aer_simulator",
        backend_options={"aer_pub_chunk_size": 3},
        noise_profile={"source": "custom_preset"},
    )

    assert _estimator_pub_chunk_size(context) == 3


class _HamiltonianBundle:
    """Minimal Hamiltonian bundle exposing a Pauli operator and HF metadata."""

    def __init__(
        self,
        pauli: SparsePauliOp,
        *,
        num_qubits: int = 4,
        n_alpha: int = 1,
        n_beta: int = 1,
        norb: int = 2,
    ) -> None:
        self.pauli_hamiltonian = pauli
        self.num_qubits = num_qubits
        self.num_electrons_alpha = n_alpha
        self.num_electrons_beta = n_beta
        self.num_spatial_orbitals = norb


class _EstimatorData:
    def __init__(self, evs: list[float], stds: list[float]) -> None:
        self.evs = np.array(evs, dtype=float)
        self.stds = np.array(stds, dtype=float)


class _PubResult:
    def __init__(self, evs: list[float], stds: list[float]) -> None:
        self.data = _EstimatorData(evs, stds)


class _Job:
    def __init__(self, results: list[_PubResult]) -> None:
        self._results = results

    def result(self) -> list[_PubResult]:
        return self._results


class _MockEstimator:
    """Exact-expectation estimator that ignores the circuit and uses one state.

    A Gaussian perturbation with a reported standard error models a noisy or
    hardware estimator without any live backend access.
    """

    def __init__(self, state: np.ndarray, *, noise: float = 0.0, seed: int = 0) -> None:
        self._state = Statevector(state)
        self._noise = float(noise)
        self._rng = np.random.default_rng(seed)
        self.pub_count = 0

    def run(self, pubs: list[tuple[object, list[SparsePauliOp]]]) -> _Job:
        results: list[_PubResult] = []
        for _circuit, observables in pubs:
            self.pub_count += 1
            evs: list[float] = []
            stds: list[float] = []
            for observable in observables:
                value = float(np.real(self._state.expectation_value(observable)))
                if self._noise:
                    value += float(self._rng.normal(0.0, self._noise))
                evs.append(value)
                stds.append(self._noise)
            results.append(_PubResult(evs, stds))
        return _Job(results)


def _four_qubit_hamiltonian(seed: int = 1) -> SparsePauliOp:
    rng = np.random.default_rng(seed)
    labels = [
        "IIII",
        "ZIII",
        "IZII",
        "IIZI",
        "IIIZ",
        "ZZII",
        "IIZZ",
        "XXII",
        "IIXX",
        "XIXI",
        "IYIY",
    ]
    return SparsePauliOp.from_list([(label, float(rng.normal())) for label in labels])


def _noisy_ctx(backend_target: str) -> SimpleNamespace:
    return SimpleNamespace(
        backend_target=backend_target,
        noise_profile=(object() if backend_target == "aer_simulator" else None),
        simulator_method="automatic",
        optimization_level=1,
        backend_options={},
    )


def test_measured_excitation_operators_match_statevector_excitations() -> None:
    """Jordan-Wigner excitation operators reproduce the exact statevector action."""
    num_qubits = 4
    operators = build_measured_excitation_operators(
        num_qubits=num_qubits,
        excitation_level="singles_doubles",
        max_dimension=8,
    )
    # A_0 is the identity.
    assert np.allclose(Operator(operators[0]).data, np.eye(2**num_qubits))

    # Every non-identity operator equals the dense fermionic excitation matrix
    # for some create/annihilate pattern; check a representative single.
    single = SparsePauliOp.from_list(
        [
            ("IIXX", 0.25),
        ]
    )
    del single  # placeholder to document intent

    # Direct comparison: build the operator for create (1,) annihilate (0,) and
    # compare against apply_fermionic_excitation on all basis vectors.
    from worker.chemistry.algorithms.qse.measured import _excitation_operator

    operator = _excitation_operator(
        num_qubits,
        create_orbitals=(1,),
        annihilate_orbitals=(0,),
    )
    matrix = Operator(operator).data
    for index in range(2**num_qubits):
        vector = np.zeros(2**num_qubits, dtype=complex)
        vector[index] = 1.0
        expected = apply_fermionic_excitation(
            vector,
            create_orbitals=(1,),
            annihilate_orbitals=(0,),
            num_qubits=num_qubits,
        )
        assert np.allclose(matrix @ vector, expected, atol=1e-9)


def test_measured_qse_assembles_hermitian_matrices_with_identity_reference() -> None:
    hamiltonian = _HamiltonianBundle(_four_qubit_hamiltonian())
    reference = build_hf_reference_state(hamiltonian, fallback_dim=16)
    estimator = _MockEstimator(reference)

    estimate = estimate_measured_qse_matrices(
        hamiltonian=hamiltonian,
        estimator=estimator,
        excitation_level="singles_doubles",
        max_dimension=8,
        backend_context=None,
    )

    projected = estimate.projected_hamiltonian
    overlap = estimate.overlap
    assert projected.shape == overlap.shape
    assert projected.shape[0] > 1
    # Hermitian symmetrized.
    assert np.allclose(projected, projected.conj().T)
    assert np.allclose(overlap, overlap.conj().T)
    # A_0 = identity, so S_00 is a structural identity.
    assert overlap[0, 0] == pytest.approx(1.0)
    # H_00 is the exact reference energy <psi|H|psi>.
    exact_energy = float(np.real(np.vdot(reference, Operator(hamiltonian.pauli_hamiltonian).data @ reference)))
    assert float(np.real(projected[0, 0])) == pytest.approx(exact_energy, abs=1e-9)
    assert estimate.summary["matrix_element_strategy"] == "branch_estimator"
    assert estimate.summary["max_standard_error"] == 0.0


def test_measured_qse_run_returns_diagnostic_not_converged() -> None:
    hamiltonian = _HamiltonianBundle(_four_qubit_hamiltonian(seed=3))
    reference = build_hf_reference_state(hamiltonian, fallback_dim=16)
    estimator = _MockEstimator(reference, noise=0.03, seed=7)

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=estimator,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 8,
            },
        },
        backend_context=_noisy_ctx("aer_simulator"),
    )

    assert result.execution_mode == "measured_matrix_elements"
    assert result.converged is False
    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.primary_energy is not None
    # The stabilized noisy solve is a rank-reduced diagnostic.
    assert result.conditioning_summary["stability_state"] in {"stabilized", "stable"}

    normalized = normalize_result(result)
    convergence = normalized["algorithm_metrics"]["convergence"]
    assert convergence["scientific_converged"] is False
    assert normalized["reported_energy_source"] in {
        "stabilized_projected_diagnostic",
        "lowest_qse_projected_eigenvalue",
    }


def test_measured_qse_rank_reduced_solve_is_reportable_diagnostic() -> None:
    hamiltonian = _HamiltonianBundle(_four_qubit_hamiltonian(seed=5))
    reference = build_hf_reference_state(hamiltonian, fallback_dim=16)
    # Higher noise forces overlap thresholding to drop rank.
    estimator = _MockEstimator(reference, noise=0.08, seed=11)

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=estimator,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 8,
            },
        },
        backend_context=_noisy_ctx("aer_simulator"),
    )

    diagnostics = result.conditioning_summary
    assert diagnostics["stability_state"] == "stabilized"
    assert int(diagnostics["retained_rank"]) >= 1
    assert result.converged is False

    normalized = normalize_result(result)
    # A reportable diagnostic keeps a finite reported energy.
    assert normalized["reported_energy"] is not None
    assert normalized["reported_energy_source"] == "stabilized_projected_diagnostic"


def test_measured_qse_ibm_target_uses_mock_estimator_without_live_access() -> None:
    hamiltonian = _HamiltonianBundle(_four_qubit_hamiltonian(seed=9))
    reference = build_hf_reference_state(hamiltonian, fallback_dim=16)
    estimator = _MockEstimator(reference, noise=0.02, seed=13)

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=estimator,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 8,
            },
        },
        backend_context=_noisy_ctx("ibm_runtime"),
    )

    assert result.execution_mode == "measured_matrix_elements"
    assert result.matrix_element_summary["backend_target"] == "ibm_runtime"
    assert result.converged is False
    # The mock estimator was actually exercised (no live IBM call).
    assert estimator.pub_count > 0


def test_measured_qse_zero_rank_overlap_is_hard_failure() -> None:
    # A zero-rank / non-positive overlap must raise inside the stabilized solver.
    projected = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=complex)
    zero_overlap = np.zeros((2, 2), dtype=complex)
    with pytest.raises(ValueError, match="zero retained rank"):
        solve_stabilized_generalized_eigenproblem(projected, zero_overlap)


def test_measured_qse_non_finite_matrix_is_hard_failure() -> None:
    hamiltonian = _HamiltonianBundle(
        SparsePauliOp.from_list([("IIII", 1.0), ("ZIII", 0.5), ("IZII", 0.3)])
    )

    class _NanEstimator:
        def run(self, pubs: list[tuple[object, list[SparsePauliOp]]]) -> _Job:
            return _Job(
                [
                    _PubResult([np.nan] * len(observables), [0.0] * len(observables))
                    for _circuit, observables in pubs
                ]
            )

    with pytest.raises(ValueError, match="finite"):
        run_qse(
            hamiltonian=hamiltonian,
            backend=_NanEstimator(),
            config={
                "algorithm": "qse",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "hf",
                    "excitation_level": "singles_doubles",
                    "max_subspace_dim": 8,
                },
            },
            backend_context=_noisy_ctx("ibm_runtime"),
        )


def _assert_hermitian_observable(observable: SparsePauliOp) -> None:
    """Fail if any Pauli coefficient carries an imaginary part.

    Mirrors the Aer/IBM EstimatorV2 rejection of non-Hermitian observables:
    ``ValueError: Non-Hermitian input observable: ... non-zero imaginary part``.
    """
    coeffs = np.asarray(observable.coeffs, dtype=complex)
    if coeffs.size and bool(np.any(np.abs(coeffs.imag) > 1e-9)):
        raise ValueError(
            "Non-Hermitian input observable: the simplified input observable "
            "has a non-zero imaginary part in its coefficients."
        )


class _HermitianStrictEstimator:
    """Estimator that rejects non-Hermitian observables like Aer EstimatorV2.

    It computes the exact real expectation of each (Hermitian) observable on a
    fixed reference state, so every off-diagonal complex matrix element must be
    reconstructed from two Hermitian measurements.
    """

    def __init__(self, state: np.ndarray) -> None:
        self._state = Statevector(state)
        self.observed: list[SparsePauliOp] = []

    def run(self, pubs: list[tuple[object, list[SparsePauliOp]]]) -> _Job:
        results: list[_PubResult] = []
        for _circuit, observables in pubs:
            evs: list[float] = []
            for observable in observables:
                _assert_hermitian_observable(observable)
                self.observed.append(observable)
                expectation = self._state.expectation_value(observable)
                # A Hermitian observable must have a (numerically) real value.
                assert abs(float(np.imag(expectation))) <= 1e-9
                evs.append(float(np.real(expectation)))
            results.append(_PubResult(evs, [0.0] * len(evs)))
        return _Job(results)


def test_measured_qse_submits_only_hermitian_observables() -> None:
    """Every observable reaching the estimator must be Hermitian (real coeffs)."""
    hamiltonian = _HamiltonianBundle(_four_qubit_hamiltonian(seed=17))
    reference = build_hf_reference_state(hamiltonian, fallback_dim=16)
    estimator = _HermitianStrictEstimator(reference)

    estimate = estimate_measured_qse_matrices(
        hamiltonian=hamiltonian,
        estimator=estimator,
        excitation_level="singles_doubles",
        max_dimension=8,
        backend_context=None,
    )

    # The strict estimator raises on any non-Hermitian observable, so reaching
    # this point already proves the fix. Assert observables were exercised and
    # every recorded coefficient set is real.
    assert estimator.observed
    for observable in estimator.observed:
        coeffs = np.asarray(observable.coeffs, dtype=complex)
        assert np.all(np.abs(coeffs.imag) <= 1e-9)
    # The assembled matrices remain Hermitian.
    assert np.allclose(estimate.projected_hamiltonian, estimate.projected_hamiltonian.conj().T)
    assert np.allclose(estimate.overlap, estimate.overlap.conj().T)
    assert estimate.summary["hermitian_observable_decomposition"] is True


def test_measured_qse_reconstructs_complex_off_diagonal_element() -> None:
    """An off-diagonal element with a known non-zero imaginary part is recovered.

    The reference state is chosen so that a specific overlap S_ij is genuinely
    complex; the fix must reconstruct <O> = <O_re> + i <O_im> exactly, whereas
    the old single-real-EV path would have discarded the imaginary part.
    """
    hamiltonian = _HamiltonianBundle(_four_qubit_hamiltonian(seed=23))
    # A superposition reference makes off-diagonal overlaps complex in general.
    raw = np.zeros(16, dtype=complex)
    raw[0b0011] = 1.0
    raw[0b0101] = 1.0j
    raw[0b0110] = 0.5 - 0.5j
    reference = raw / np.linalg.norm(raw)

    estimator = _HermitianStrictEstimator(reference)
    estimate = estimate_measured_qse_matrices(
        hamiltonian=hamiltonian,
        estimator=estimator,
        excitation_level="singles_doubles",
        max_dimension=8,
        backend_context=None,
    )

    # Independently compute the exact projected/overlap matrices from the dense
    # excitation operators on the same reference state.
    operators = build_measured_excitation_operators(
        num_qubits=4,
        excitation_level="singles_doubles",
        max_dimension=8,
    )
    h_dense = Operator(hamiltonian.pauli_hamiltonian).data
    a_dense = [Operator(op).data for op in operators]
    dimension = len(operators)
    expected_h = np.zeros((dimension, dimension), dtype=complex)
    expected_s = np.zeros((dimension, dimension), dtype=complex)
    for row in range(dimension):
        left = a_dense[row].conj().T
        for col in range(dimension):
            expected_h[row, col] = reference.conj() @ (left @ h_dense @ a_dense[col] @ reference)
            expected_s[row, col] = reference.conj() @ (left @ a_dense[col] @ reference)
    expected_h = 0.5 * (expected_h + expected_h.conj().T)
    expected_s = 0.5 * (expected_s + expected_s.conj().T)
    expected_s[0, 0] = 1.0

    assert np.allclose(estimate.projected_hamiltonian, expected_h, atol=1e-9)
    assert np.allclose(estimate.overlap, expected_s, atol=1e-9)

    # At least one reconstructed off-diagonal overlap has a non-zero imaginary
    # part, which the old real-only path could not have produced.
    off_diagonal = estimate.overlap - np.diag(np.diag(estimate.overlap))
    assert np.max(np.abs(off_diagonal.imag)) > 1e-3


def test_measured_qse_real_h2_noisy_aer_completes_as_diagnostic() -> None:
    """A real H2 noisy-Aer QSE run completes without the non-Hermitian error.

    Uses a genuine Aer EstimatorV2 (not a mock), which rejects non-Hermitian
    observables with:
        ValueError: Non-Hermitian input observable ...
    Before the Hermitian-decomposition fix, the off-diagonal composite
    observables A_i^dag H A_j and A_i^dag A_j reached the estimator directly and
    crashed. The run must now finish as a non-converged diagnostic.
    """
    from worker.adapters.aer_adapter import AerAdapter
    from worker.adapters.base import BackendExecutionContext

    # Minimal-basis H2 (STO-3G, 2 spatial orbitals -> 4 spin-qubits) style
    # Hamiltonian with non-diagonal (X/Y) terms so off-diagonal projected
    # elements are genuinely non-Hermitian composite operators.
    h2_pauli = SparsePauliOp.from_list(
        [
            ("IIII", -0.8105),
            ("ZIII", 0.1721),
            ("IZII", 0.1721),
            ("IIZI", -0.2257),
            ("IIIZ", -0.2257),
            ("ZZII", 0.1686),
            ("IIZZ", 0.1686),
            ("ZIZI", 0.1205),
            ("IZIZ", 0.1205),
            ("ZIIZ", 0.1659),
            ("IZZI", 0.1659),
            ("XXXX", 0.0453),
            ("YYYY", 0.0453),
            ("XXYY", 0.0453),
            ("YYXX", 0.0453),
        ]
    )
    hamiltonian = _HamiltonianBundle(h2_pauli, num_qubits=4, n_alpha=1, n_beta=1, norb=2)

    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"seed_simulator": 7},
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        },
        shots=512,
    )
    estimator = AerAdapter().create_estimator(context)

    result = run_qse(
        hamiltonian=hamiltonian,
        backend=estimator,
        config={
            "algorithm": "qse",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "hf",
                "excitation_level": "singles_doubles",
                "max_subspace_dim": 4,
            },
        },
        backend_context=context,
    )

    assert result.execution_mode == "measured_matrix_elements"
    assert result.matrix_element_summary["matrix_element_strategy"] == "branch_estimator"
    assert result.matrix_element_summary["backend_target"] == "aer_simulator"
    # Measured QSE stays a non-converged diagnostic.
    assert result.converged is False
    assert result.primary_energy is not None
    assert np.isfinite(result.primary_energy)

    normalized = normalize_result(result)
    assert normalized["algorithm_metrics"]["convergence"]["scientific_converged"] is False


def test_measured_qse_statevector_target_keeps_exact_path() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    result = run_qse(
        hamiltonian=hamiltonian,
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
        backend_context=SimpleNamespace(backend_target="statevector", noise_profile=None),
    )
    assert result.execution_mode == "dense_exact_emulation"


def test_measured_qse_ideal_aer_keeps_exact_path() -> None:
    hamiltonian = SparsePauliOp.from_list([("Z", 1.0)])
    result = run_qse(
        hamiltonian=hamiltonian,
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
        backend_context=SimpleNamespace(backend_target="aer_simulator", noise_profile=None),
    )
    assert result.execution_mode == "dense_exact_emulation"
