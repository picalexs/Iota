"""Direct tests for QFD time-grid state helpers."""

from types import SimpleNamespace

import numpy as np

from worker.chemistry.algorithms.qfd.states import build_dense_qfd_states, build_sector_qfd_states


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
