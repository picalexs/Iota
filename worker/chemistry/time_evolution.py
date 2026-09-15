"""Time-evolution helpers for worker chemistry solvers."""

from __future__ import annotations

from typing import Any

import numpy as np

_AER_STATEVECTOR_METHODS = {"automatic", "statevector", "matrix_product_state"}


def prepare_exact_time_evolution(operator_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Diagonalize a Hermitian operator once for repeated exact evolution."""
    hermitian = np.asarray(operator_matrix, dtype=complex)
    hermitian = 0.5 * (hermitian + hermitian.conj().T)
    return np.linalg.eigh(hermitian)


def build_time_grid(
    *,
    num_time_points: int,
    max_time: float,
    grid_type: str = "linear",
) -> np.ndarray:
    """Build a deterministic time grid for QFD-style solvers."""
    if num_time_points < 2:
        raise ValueError("num_time_points must be at least 2")
    if max_time <= 0.0:
        raise ValueError("max_time must be positive")

    normalized_grid_type = grid_type.strip().lower()
    if normalized_grid_type == "geometric":
        positive_times = np.geomspace(max_time / num_time_points, max_time, num_time_points - 1)
        return np.concatenate([np.array([0.0]), positive_times.astype(float)])

    return np.linspace(0.0, max_time, num_time_points, dtype=float)


def _exponentiate_hermitian(matrix: np.ndarray, time_step: float) -> np.ndarray:
    """Return exp(-i * matrix * time_step) for a Hermitian matrix."""
    eigenvalues, eigenvectors = prepare_exact_time_evolution(matrix)
    phases = np.exp(-1j * eigenvalues * time_step)
    return eigenvectors @ np.diag(phases) @ eigenvectors.conj().T


def exact_time_evolution_state_from_spectrum(
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
    state: np.ndarray,
    *,
    time_step: float,
    state_projection: np.ndarray | None = None,
) -> np.ndarray:
    """Evolve a state using a precomputed Hermitian spectrum."""
    if state_projection is None:
        state_projection = eigenvectors.conj().T @ np.asarray(state, dtype=complex)

    phases = np.exp(-1j * np.asarray(eigenvalues, dtype=float) * time_step)
    evolved = eigenvectors @ (phases * state_projection)
    norm = np.linalg.norm(evolved)
    if np.isclose(norm, 0.0):
        return evolved
    return evolved / norm


def exact_time_evolution_state(
    operator_matrix: np.ndarray,
    state: np.ndarray,
    *,
    time_step: float,
) -> np.ndarray:
    """Evolve a state exactly under a Hermitian operator."""
    eigenvalues, eigenvectors = prepare_exact_time_evolution(operator_matrix)
    return exact_time_evolution_state_from_spectrum(
        eigenvalues,
        eigenvectors,
        state,
        time_step=time_step,
    )


def trotterized_time_evolution_state(
    operator_matrix: np.ndarray,
    state: np.ndarray,
    *,
    time_step: float,
    trotter_steps: int = 1,
) -> np.ndarray:
    """Apply a simple first-order Trotter approximation for time evolution."""
    if trotter_steps < 1:
        raise ValueError("trotter_steps must be positive")

    operator = np.asarray(operator_matrix, dtype=complex)
    diagonal = np.diag(np.diag(operator))
    residual = operator - diagonal
    evolved = np.asarray(state, dtype=complex)
    step_time = time_step / trotter_steps

    for _ in range(trotter_steps):
        evolved = _exponentiate_hermitian(diagonal, step_time) @ evolved
        evolved = _exponentiate_hermitian(residual, step_time) @ evolved

    norm = np.linalg.norm(evolved)
    if np.isclose(norm, 0.0):
        return evolved
    return evolved / norm


def aer_pauli_time_evolution_state(
    hamiltonian: object,
    state: np.ndarray,
    *,
    time_step: float,
    trotter_steps: int = 1,
    context: Any | None = None,
) -> np.ndarray:
    """Evolve a state by simulating a PauliEvolutionGate with AerSimulator."""
    if np.isclose(time_step, 0.0):
        return _normalized_state(state)
    if trotter_steps < 1:
        raise ValueError("trotter_steps must be positive")
    if context is not None and getattr(context, "noise_profile", None):
        raise ValueError(
            "KQD/QFD Aer time evolution requires ideal statevector simulation; "
            "noise profiles are not supported for this path."
        )

    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    from qiskit.synthesis import LieTrotter
    from worker.chemistry.matrix_element_circuits import build_aer_simulator

    pauli_hamiltonian = getattr(hamiltonian, "pauli_hamiltonian", None)
    if not isinstance(pauli_hamiltonian, SparsePauliOp):
        raise ValueError("Aer time evolution requires HamiltonianBundle.pauli_hamiltonian")

    state_array = np.ravel(_normalized_state(state))
    num_qubits = _resolve_num_qubits(hamiltonian, state_array)
    simulator_method = _simulator_method(context)
    if simulator_method not in _AER_STATEVECTOR_METHODS:
        raise ValueError(
            "KQD/QFD Aer time evolution requires aer_method='automatic', "
            "'statevector', or 'matrix_product_state'."
        )

    simulator = build_aer_simulator(context)

    circuit = QuantumCircuit(num_qubits)
    circuit.initialize([complex(value) for value in state_array], list(range(num_qubits)))
    circuit.append(
        PauliEvolutionGate(
            pauli_hamiltonian,
            time=float(time_step),
            synthesis=LieTrotter(reps=int(trotter_steps)),
        ),
        list(range(num_qubits)),
    )
    save_statevector = getattr(circuit, "save_statevector", None)
    if not callable(save_statevector):
        raise ValueError("Aer statevector save instruction is unavailable")
    save_statevector(label="statevector")

    transpile_options: dict[str, Any] = {
        "optimization_level": _optimization_level(context),
    }
    seed_transpiler = _backend_option_int(context, "seed_transpiler")
    if seed_transpiler is not None:
        transpile_options["seed_transpiler"] = seed_transpiler

    transpiled = transpile(circuit, simulator, **transpile_options)
    run_options: dict[str, Any] = {}
    seed_simulator = _backend_option_int(context, "seed_simulator")
    if seed_simulator is not None:
        run_options["seed_simulator"] = seed_simulator

    result = simulator.run(transpiled, **run_options).result()
    data = result.data(0)
    evolved = np.asarray(data["statevector"], dtype=complex)
    return _normalized_state(evolved)


def _normalized_state(state: np.ndarray) -> np.ndarray:
    state_array = np.asarray(state, dtype=complex)
    norm = float(np.linalg.norm(state_array))
    if np.isclose(norm, 0.0):
        return state_array
    return state_array / norm


def _resolve_num_qubits(hamiltonian: object, state: np.ndarray) -> int:
    if hasattr(hamiltonian, "num_qubits"):
        num_qubits = int(getattr(hamiltonian, "num_qubits"))
    else:
        width = int(round(np.log2(state.size)))
        num_qubits = width if 2**width == state.size else 0
    if num_qubits < 1 or 2**num_qubits != state.size:
        raise ValueError("State vector size is incompatible with Hamiltonian qubit count")
    return num_qubits


def _simulator_method(context: Any | None) -> str:
    value = getattr(context, "simulator_method", None) if context is not None else None
    return str(value or "automatic").strip().lower()


def _optimization_level(context: Any | None) -> int:
    value = getattr(context, "optimization_level", None) if context is not None else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1
    return max(0, min(int(value), 3))


def _backend_option_int(context: Any | None, key: str) -> int | None:
    if context is None:
        return None
    options = getattr(context, "backend_options", None)
    if not isinstance(options, dict):
        return None
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)
