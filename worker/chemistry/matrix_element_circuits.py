"""Circuit and observable preparation for projected matrix elements."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.circuit_artifacts import prepare_hf_reference_bits
from worker.chemistry.time_evolution import is_zero_time

_AER_BOOLEAN_OPTIONS = {
    "batched_shots_gpu",
    "runtime_parameter_bind_enable",
    "shot_branching_enable",
    "blocking_enable",
    "cuStateVec_enable",
}
_AER_INTEGER_OPTIONS = {
    "max_parallel_threads",
    "max_parallel_experiments",
    "max_parallel_shots",
}


def build_branch_state_circuit(
    *,
    hamiltonian: object,
    pauli_hamiltonian: SparsePauliOp,
    num_qubits: int,
    left_time: float,
    right_time: float,
    trotter_steps: int,
) -> Any:
    """Build a controlled branch circuit for one projected-basis pair."""
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.synthesis import LieTrotter

    system_qubits = list(range(num_qubits))
    ancilla = num_qubits
    circuit = QuantumCircuit(num_qubits + 1)
    prepare_hf_reference_bits(circuit, hamiltonian, num_qubits=num_qubits)
    circuit.h(ancilla)

    synthesis = LieTrotter(reps=int(trotter_steps))
    if not is_zero_time(left_time):
        left_gate = PauliEvolutionGate(
            pauli_hamiltonian,
            time=float(left_time),
            synthesis=synthesis,
        )
        circuit.append(left_gate.control(1, ctrl_state=0), [ancilla, *system_qubits])
    if not is_zero_time(right_time):
        right_gate = PauliEvolutionGate(
            pauli_hamiltonian,
            time=float(right_time),
            synthesis=synthesis,
        )
        circuit.append(right_gate.control(1, ctrl_state=1), [ancilla, *system_qubits])

    return circuit


def augment_system_observable(
    system_observable: SparsePauliOp, ancilla_pauli: str
) -> SparsePauliOp:
    """Attach an X or Y ancilla Pauli to every system observable term."""
    if ancilla_pauli not in {"X", "Y"}:
        raise ValueError("ancilla_pauli must be X or Y")
    return SparsePauliOp.from_list(
        [(ancilla_pauli + label, coeff) for label, coeff in system_observable.to_list()]
    ).simplify(atol=1e-12)


def transpile_aer_pub(
    circuit: Any,
    observables: list[SparsePauliOp],
    *,
    context: Any,
) -> tuple[Any, list[SparsePauliOp]]:
    """Decompose a branch circuit and align observables for Aer EstimatorV2."""
    transpiled = transpile_aer_circuit(circuit, context=context)
    layout = getattr(transpiled, "layout", None)
    if layout is None:
        return transpiled, observables
    return transpiled, [
        apply_layout_to_observable(observable, layout) for observable in observables
    ]


def transpile_aer_circuit(
    circuit: Any,
    *,
    context: Any,
    noise_model: Any | None = None,
    noise_options: Mapping[str, Any] | None = None,
) -> Any:
    """Transpile a circuit to the local Aer simulator instruction set."""
    from qiskit import transpile
    simulator_options = dict(noise_options or {})
    if noise_model is not None:
        simulator_options["noise_model"] = noise_model
    simulator = build_aer_simulator(context, extra_options=simulator_options)
    transpile_options: dict[str, Any] = {"optimization_level": optimization_level(context)}
    seed_transpiler = backend_option_int(context, "seed_transpiler")
    if seed_transpiler is not None:
        transpile_options["seed_transpiler"] = seed_transpiler
    return transpile(circuit, simulator, **transpile_options)


def build_aer_simulator(
    context: Any | None,
    *,
    extra_options: Mapping[str, Any] | None = None,
) -> Any:
    """Create the shared Aer simulator used by worker execution paths."""
    from qiskit_aer import AerSimulator

    return AerSimulator(**aer_simulator_options(context, extra_options=extra_options))


def aer_simulator_options(
    context: Any | None,
    *,
    extra_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return validated Aer simulator options from a backend context.

    The options are explicit so a benchmark can opt into GPU execution or
    bounded Aer parallelism without changing the default CPU path. Unknown
    backend fields stay out of the Aer constructor.
    """
    method = str(getattr(context, "simulator_method", None) or "automatic")
    options: dict[str, Any] = {"method": method}
    backend_options = getattr(context, "backend_options", None)
    if isinstance(backend_options, dict):
        device = backend_options.get("device")
        if isinstance(device, str) and device.upper() in {"CPU", "GPU"}:
            options["device"] = device.upper()

        for key in _AER_BOOLEAN_OPTIONS:
            value = backend_options.get(key)
            if isinstance(value, bool):
                options[key] = value

        for key in _AER_INTEGER_OPTIONS:
            value = backend_options.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            options[key] = max(1, min(int(value), 1024))

    if extra_options:
        options.update(extra_options)
    return options


def apply_layout_to_observable(observable: SparsePauliOp, layout: Any) -> SparsePauliOp:
    """Apply a transpiler layout when the observable supports that operation."""
    apply_layout = getattr(observable, "apply_layout", None)
    if not callable(apply_layout):
        return observable
    resolved = apply_layout(layout)
    return resolved if isinstance(resolved, SparsePauliOp) else observable


def optimization_level(context: Any | None) -> int:
    """Return a bounded Aer transpilation optimization level."""
    value = getattr(context, "optimization_level", None) if context is not None else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1
    return max(0, min(int(value), 3))


def backend_option_int(context: Any | None, key: str) -> int | None:
    """Read a numeric integer option from a backend context."""
    if context is None:
        return None
    options = getattr(context, "backend_options", None)
    if not isinstance(options, dict):
        return None
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


__all__ = [
    "apply_layout_to_observable",
    "aer_simulator_options",
    "augment_system_observable",
    "backend_option_int",
    "build_branch_state_circuit",
    "optimization_level",
    "transpile_aer_circuit",
    "transpile_aer_pub",
]
