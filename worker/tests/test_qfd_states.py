"""Direct tests for QFD time-grid state helpers."""

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp
from scipy.sparse.linalg import aslinearoperator

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.algorithms.qfd.grid import (
    build_qfd_time_grid,
    qfd_spectral_width_bound,
    resolve_qfd_symmetric_kappa,
)
from worker.chemistry.algorithms.qfd.states import (
    build_dense_qfd_states,
    build_sector_qfd_states,
    evolve_dense_qfd_state,
)
from worker.chemistry.hamiltonian_action import HamiltonianAction
from worker.chemistry.time_evolution import aer_pauli_time_evolution_state


def test_build_dense_qfd_states_emits_progress_metadata() -> None:
    events: list[dict[str, object]] = []
    context = SimpleNamespace(
        hamiltonian=object(),
        operator=np.diag([0.0, 1.0]).astype(complex),
        reference_state=np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0),
        use_aer=False,
        trotter_steps=1,
        eigenvalues=np.array([0.0, 1.0]),
        eigenvectors=np.eye(2, dtype=complex),
        reference_projection=np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0),
        backend_context=None,
    )

    states = build_dense_qfd_states(
        evolution_context=context,
        time_grid=np.array([0.0, 0.2]),
        num_time_points=2,
        max_time=0.2,
        time_grid_type="linear",
        progress_callback=events.append,
    )

    assert len(states) == 2
    assert events[-1]["step"] == "time_evolution"
    assert events[-1]["completed_iterations"] == 2
    assert events[-1]["time_evolution_backend"] == "dense_matrix"


def test_build_sector_qfd_states_reports_sector_backend() -> None:
    operator = np.diag([0.0, 1.0]).astype(complex)

    class _Action:
        dimension = 2

        def expectation(self, state: np.ndarray) -> float:
            return float(np.real(np.vdot(state, operator @ state)))

        def time_evolve(self, state: np.ndarray, *, time_point: float) -> np.ndarray:
            return np.array([state[0], np.exp(-1j * time_point) * state[1]])

        def project(self, basis: np.ndarray) -> np.ndarray:
            return basis.conj().T @ operator @ basis

    events: list[dict[str, object]] = []
    states = build_sector_qfd_states(
        _Action(),
        np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0),
        np.array([0.0, 0.2]),
        max_time=0.2,
        time_grid_type="linear",
        progress_callback=events.append,
    )

    assert len(states) == 2
    assert events[-1]["time_evolution_backend"] == "sector_matrix_free"
    assert events[-1]["implemented_evolution_method"] == "sector_expm_multiply"


def test_qfd_dense_and_sector_evolution_preserve_analytic_complex_phase() -> None:
    time_grid = build_qfd_time_grid(
        qfd_variant="qfd_original_symmetric",
        num_time_points=3,
        max_time=1.0,
        time_grid_type="linear",
        kappa=8.0,
    )
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    operator = np.diag([1.0, -1.0]).astype(complex)
    eigenvalues, eigenvectors = np.linalg.eigh(operator)
    context = SimpleNamespace(
        hamiltonian=object(),
        operator=operator,
        reference_state=reference,
        use_aer=False,
        trotter_steps=1,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        reference_projection=eigenvectors.conj().T @ reference,
        backend_context=None,
    )
    expected = np.column_stack(
        [
            np.array([np.exp(-1j * time), np.exp(1j * time)]) / np.sqrt(2.0)
            for time in time_grid
        ]
    )

    dense_states = build_dense_qfd_states(
        evolution_context=context,
        time_grid=time_grid,
        num_time_points=len(time_grid),
        max_time=None,
        time_grid_type="symmetric_kappa",
        progress_callback=None,
    )
    action = HamiltonianAction(
        norb=2,
        nelec=(1, 0),
        dimension=2,
        linear_operator=aslinearoperator(operator),
    )
    sector_states = build_sector_qfd_states(
        action,
        reference,
        time_grid,
        max_time=None,
        time_grid_type="symmetric_kappa",
        progress_callback=None,
    )

    assert np.column_stack(dense_states) == pytest.approx(expected)
    assert np.column_stack(sector_states) == pytest.approx(expected)


def test_qfd_aer_evolution_preserves_analytic_complex_phase() -> None:
    time = np.pi / 4.0
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    hamiltonian = SimpleNamespace(
        num_qubits=1,
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
    )
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        simulator_method="statevector",
    )
    expected_positive = np.array([np.exp(-1j * time), np.exp(1j * time)]) / np.sqrt(2.0)
    expected_negative = np.conjugate(expected_positive)

    positive = aer_pauli_time_evolution_state(
        hamiltonian,
        reference,
        time_step=time,
        context=context,
    )
    negative = aer_pauli_time_evolution_state(
        hamiltonian,
        reference,
        time_step=-time,
        context=context,
    )

    assert positive == pytest.approx(expected_positive)
    assert negative == pytest.approx(expected_negative)


def test_qfd_dense_aer_evolution_persists_result_metadata_on_context() -> None:
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    hamiltonian = SimpleNamespace(
        num_qubits=1,
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
    )
    context = SimpleNamespace(
        backend_target="aer_simulator",
        backend_options={"device": "CPU"},
        simulator_method="statevector",
        optimization_level=1,
        resource_metadata={},
        noise_profile=None,
    )
    evolution_context = SimpleNamespace(
        hamiltonian=hamiltonian,
        reference_state=reference,
        use_aer=True,
        trotter_steps=1,
        backend_context=context,
    )

    evolve_dense_qfd_state(evolution_context=evolution_context, time_point=0.25)

    metadata = context.resource_metadata["aer_state_evolution"]
    assert metadata["actual_device"] == "CPU"
    assert metadata["device_verified"] is True
    assert metadata["aer_simulation_seconds"] >= 0.0
    assert metadata["aer_experiment_metadata"]["method"] == "statevector"


def test_qfd_aer_evolution_can_return_result_metadata(monkeypatch) -> None:
    from worker.chemistry import matrix_element_circuits

    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    hamiltonian = SimpleNamespace(
        num_qubits=1,
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
    )
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"device": "CPU", "max_parallel_threads": 2},
        simulator_method="statevector",
    )
    metadata_sink: dict[str, object] = {}
    captured_options: dict[str, object] = {}
    real_build_aer_simulator = matrix_element_circuits.build_aer_simulator

    def capture_aer_options(context, *, extra_options=None):
        captured_options.update(
            matrix_element_circuits.aer_simulator_options(
                context,
                extra_options=extra_options,
            )
        )
        return real_build_aer_simulator(context, extra_options=extra_options)

    monkeypatch.setattr(
        matrix_element_circuits,
        "build_aer_simulator",
        capture_aer_options,
    )

    evolved, metadata = aer_pauli_time_evolution_state(
        hamiltonian,
        reference,
        time_step=np.pi / 4.0,
        context=context,
        result_metadata=metadata_sink,
        return_metadata=True,
    )

    assert evolved == pytest.approx(
        np.array([np.exp(-1j * np.pi / 4.0), np.exp(1j * np.pi / 4.0)]) / np.sqrt(2.0)
    )
    assert metadata == metadata_sink
    assert metadata["aer_result_metadata"]
    assert metadata["aer_experiment_metadata"]["method"] == "statevector"
    assert metadata["aer_experiment_metadata"]["device"] == "CPU"
    assert metadata["actual_device"] == "CPU"
    assert metadata["device_verified"] is True
    assert captured_options == {
        "method": "statevector",
        "device": "CPU",
        "max_parallel_threads": 2,
    }


def test_small_symmetric_grid_times_are_evolved_in_dense_and_sector_paths() -> None:
    hamiltonian = np.diag([1e10, -1e10]).astype(complex)
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    pauli_hamiltonian = SparsePauliOp.from_list([("Z", 1e10)])
    spectral_width, bound_source = qfd_spectral_width_bound(
        operator_matrix=hamiltonian,
        pauli_hamiltonian=pauli_hamiltonian,
    )
    kappa, _kappa_metadata = resolve_qfd_symmetric_kappa(
        None,
        spectral_width_bound=spectral_width,
        bound_source=bound_source,
    )
    time_grid = build_qfd_time_grid(
        qfd_variant="qfd_original_symmetric",
        num_time_points=3,
        max_time=1.0,
        time_grid_type="linear",
        kappa=kappa,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    context = SimpleNamespace(
        hamiltonian=object(),
        operator=hamiltonian,
        reference_state=reference,
        use_aer=False,
        trotter_steps=1,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        reference_projection=eigenvectors.conj().T @ reference,
        backend_context=None,
    )
    expected = np.column_stack(
        [
            eigenvectors
            @ (np.exp(-1j * eigenvalues * time) * (eigenvectors.conj().T @ reference))
            for time in time_grid
        ]
    )
    action = HamiltonianAction(
        norb=2,
        nelec=(1, 0),
        dimension=2,
        linear_operator=aslinearoperator(hamiltonian),
    )

    dense_states = [
        evolve_dense_qfd_state(evolution_context=context, time_point=float(time))
        for time in time_grid
    ]
    sector_time_grid = np.array([0.0, 7e-10])
    sector_expected = np.column_stack(
        [
            eigenvectors
            @ (
                np.exp(-1j * eigenvalues * time)
                * (eigenvectors.conj().T @ reference)
            )
            for time in sector_time_grid
        ]
    )
    sector_states = build_sector_qfd_states(
        action,
        reference,
        sector_time_grid,
        max_time=None,
        time_grid_type="symmetric_kappa",
        progress_callback=None,
    )

    assert 0.0 < abs(time_grid[0]) < 1e-8
    assert np.column_stack(dense_states) == pytest.approx(expected)
    assert np.column_stack(sector_states) == pytest.approx(sector_expected)

    aer_context = SimpleNamespace(
        hamiltonian=SimpleNamespace(
            num_qubits=1,
            pauli_hamiltonian=pauli_hamiltonian,
        ),
        operator=hamiltonian,
        reference_state=reference,
        use_aer=True,
        trotter_steps=1,
        eigenvalues=None,
        eigenvectors=None,
        reference_projection=None,
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            simulator_method="statevector",
        ),
    )
    aer_states = [
        evolve_dense_qfd_state(evolution_context=aer_context, time_point=float(time))
        for time in time_grid
    ]
    assert np.column_stack(aer_states) == pytest.approx(expected)


def test_aer_evolves_small_nonzero_time_with_large_hamiltonian() -> None:
    time = 7e-10
    reference = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    hamiltonian = SimpleNamespace(
        num_qubits=1,
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1e10)]),
    )
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        simulator_method="statevector",
    )

    evolved = aer_pauli_time_evolution_state(
        hamiltonian,
        reference,
        time_step=time,
        context=context,
    )
    expected = np.array(
        [np.exp(-1j * 1e10 * time), np.exp(1j * 1e10 * time)], dtype=complex
    ) / np.sqrt(2.0)

    assert evolved == pytest.approx(expected)
