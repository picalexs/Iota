"""Paper-faithful SKQD sample-union execution."""

from __future__ import annotations

from typing import Any

import numpy as np

from worker.chemistry.algorithms.skqd.sampling import (
    SKQDKrylovSample,
    SKQDSampleUnion,
    merge_krylov_samples,
    sample_exact_krylov_states,
    sample_sector_krylov_states,
)
from worker.chemistry.algorithms.skqd.selected_ci import (
    SKQDSelectedCIOutcome,
    solve_sample_union_selected_ci,
)
from worker.chemistry.algorithms.skqd.spectral_width import (
    estimate_action_spectral_width,
    estimate_dense_spectral_width,
    estimate_pauli_spectral_width,
    paper_time_step,
)
from worker.chemistry.algorithms.sqd.config import resolve_sqd_options
from worker.chemistry.algorithms.sqd.sampling_execution import sample_bitstring_matrix
from worker.chemistry.algorithms.sqd.state import import_sqd_dependencies
from worker.chemistry.circuit_artifacts import prepare_hf_reference_bits
from worker.chemistry.reference_descriptor import build_reference_descriptor
from worker.chemistry.reference_states import build_hf_reference_state_with_source
from worker.chemistry.sector_basis import hartree_fock_sector_state
from worker.exceptions import RunExcludedError


def resolve_sampling_time_step(
    skqd_config: Any,
    *,
    spectral_width: float | None,
    spectral_source: str,
) -> tuple[float, dict[str, Any]]:
    """Resolve the Krylov time step, applying paper Delta t = pi / Delta E_{N-1}.

    An explicit user time step is honored as-is. Otherwise the step is derived
    from the estimated spectral width so nonzero Krylov phases stay within the
    principal ``(-pi, pi)`` window required by the SKQD convergence analysis.
    """
    explicit_time_step = getattr(skqd_config, "sampling_time_step", None)
    policy = getattr(skqd_config, "time_step_policy", "explicit_user_time_step")
    if explicit_time_step is not None:
        return float(explicit_time_step), {
            "time_step_policy": "explicit_user_time_step",
            "time_step": float(explicit_time_step),
            "spectral_width": (float(spectral_width) if spectral_width is not None else None),
            "spectral_width_source": spectral_source,
        }
    if spectral_width is None:
        raise ValueError("SKQD auto time step requires an estimated spectral width")
    resolved_time_step = paper_time_step(spectral_width)
    return resolved_time_step, {
        "time_step_policy": policy,
        "time_step": resolved_time_step,
        "spectral_width": float(spectral_width),
        "spectral_width_source": spectral_source,
    }


def execute_sample_union_workflow(
    *,
    hamiltonian: object,
    plan: Any,
    skqd_config: Any,
) -> tuple[SKQDSampleUnion, SKQDSelectedCIOutcome, dict[str, Any]]:
    """Sample all Krylov states and solve their selected determinant union."""
    options = resolve_sqd_options(skqd_config.sqd_config, hamiltonian)
    rng = np.random.default_rng(skqd_config.seed)
    if plan.sector_action is not None:
        spectral_width, spectral_source = estimate_action_spectral_width(
            plan.sector_action,
            pauli_hamiltonian=getattr(hamiltonian, "pauli_hamiltonian", None),
        )
        time_step, time_step_metadata = resolve_sampling_time_step(
            skqd_config,
            spectral_width=spectral_width,
            spectral_source=spectral_source,
        )
        reference = hartree_fock_sector_state(
            plan.sector_action.norb,
            plan.sector_action.nelec,
        )
        reference_source = "hartree_fock_sector"
        sample_union = sample_sector_krylov_states(
            plan.sector_action,
            reference,
            num_states=skqd_config.krylov_extension_dim,
            time_step=time_step,
            samples_per_state=skqd_config.samples_per_state,
            rng=rng,
        )
    else:
        if plan.operator is None:
            raise ValueError("SKQD sample-union workflow requires an execution operator")
        spectral_width, spectral_source = estimate_dense_spectral_width(plan.operator)
        time_step, time_step_metadata = resolve_sampling_time_step(
            skqd_config,
            spectral_width=spectral_width,
            spectral_source=spectral_source,
        )
        reference, reference_source = build_hf_reference_state_with_source(
            hamiltonian,
            fallback_dim=plan.operator.shape[0],
        )
        sample_union = sample_exact_krylov_states(
            plan.operator,
            reference,
            num_states=skqd_config.krylov_extension_dim,
            time_step=time_step,
            samples_per_state=skqd_config.samples_per_state,
            num_qubits=int(round(np.log2(plan.operator.shape[0]))),
            rng=rng,
        )

    deps = import_sqd_dependencies()
    outcome = solve_sample_union_selected_ci(
        sample_union,
        options=options,
        rng=rng,
        recover_configurations=None,
        postselect_by_hamming_right_and_left=deps.postselect_by_hamming_right_and_left,
        solve_fermion=deps.solve_fermion,
    )
    reference_descriptor = build_reference_descriptor(
        state=reference,
        reference_source=reference_source,
        preparation_path=("sector_basis" if plan.sector_action is not None else "computational_basis"),
        execution_mode="exact_statevector_oracle",
        target_sector=(
            {
                "alpha": plan.sector_action.nelec[0],
                "beta": plan.sector_action.nelec[1],
            }
            if plan.sector_action is not None
            else {
                "alpha": getattr(hamiltonian, "num_electrons_alpha", None),
                "beta": getattr(hamiltonian, "num_electrons_beta", None),
            }
        ),
        ansatz_name="hartree_fock",
    )
    metadata = {
        "algorithm_variant": "skqd_sample_union",
        "sampling_mode": "sample_union_exact",
        "sampling_source": "exact_statevector_oracle",
        "reference_policy": "hartree_fock",
        "reference_source": "exact_statevector_oracle",
        "reference_state_source": reference_source,
        "reference_descriptor": reference_descriptor,
        "execution_mode": plan.execution_mode,
        "krylov_state_count": skqd_config.krylov_extension_dim,
        "samples_per_state": skqd_config.samples_per_state,
        "seed": skqd_config.seed,
        "time_step": time_step,
        "krylov_time_step_policy": time_step_metadata,
    }
    return sample_union, outcome, metadata


_MAX_SAMPLER_QUBITS_LOCAL_AER = 14


def _guard_sampler_circuit_tractability(
    *,
    num_qubits: int,
    pauli_hamiltonian: Any,
    backend_target: Any,
) -> None:
    """Reject SKQD sampler runs whose local Aer simulation would exhaust the worker.

    Only the local Aer target is blocked: ``ibm_runtime`` executes the circuits
    remotely, so it does not risk an out-of-memory worker crash even though the
    resulting depth remains impractical on near-term hardware.
    """
    if str(backend_target) != "aer_simulator":
        return
    if num_qubits <= _MAX_SAMPLER_QUBITS_LOCAL_AER:
        return
    pauli_terms = None
    try:
        pauli_terms = len(pauli_hamiltonian)
    except TypeError:
        pauli_terms = None
    term_note = f" ({pauli_terms} Pauli terms)" if pauli_terms is not None else ""
    raise RunExcludedError(
        f"SKQD sampler execution needs to simulate {num_qubits}-qubit Trotter circuits"
        f"{term_note} on the local Aer simulator, which exceeds the "
        f"{_MAX_SAMPLER_QUBITS_LOCAL_AER}-qubit limit (statevector memory grows as 2^n and "
        "dense molecular Trotter circuits reach tens of thousands of gates). "
        "Reduce the active space (fewer orbitals) so the circuit fits, use the "
        "statevector backend for an exact analysis oracle, or choose SQD which "
        "samples shallow reference circuits instead of deep Trotter evolutions.",
        reason="skqd_sampler_circuit_exceeds_local_aer_limit",
    )


def execute_sampler_sample_union_workflow(
    *,
    hamiltonian: object,
    backend: Any,
    skqd_config: Any,
    backend_context: Any | None,
) -> tuple[SKQDSampleUnion, dict[str, Any]]:
    """Sample each time-evolved Krylov circuit through the selected sampler."""
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.synthesis import LieTrotter, SuzukiTrotter

    num_qubits = int(getattr(hamiltonian, "num_qubits", 0))
    pauli_hamiltonian = getattr(hamiltonian, "pauli_hamiltonian", None)
    if num_qubits < 1 or pauli_hamiltonian is None:
        raise ValueError("SKQD sampler execution requires a qubit Hamiltonian")

    _guard_sampler_circuit_tractability(
        num_qubits=num_qubits,
        pauli_hamiltonian=pauli_hamiltonian,
        backend_target=getattr(backend_context, "backend_target", None),
    )

    spectral_width, spectral_source = estimate_pauli_spectral_width(pauli_hamiltonian)
    sampling_time_step, time_step_metadata = resolve_sampling_time_step(
        skqd_config,
        spectral_width=spectral_width,
        spectral_source=spectral_source,
    )

    trotter_order = int(getattr(skqd_config, "trotter_order", 2))
    trotter_steps_per_interval = int(skqd_config.trotter_steps)
    if trotter_order <= 1:
        synthesis_name = "lie_trotter_first_order"
    else:
        synthesis_name = f"suzuki_trotter_order_{trotter_order}"

    def factory_for_time(krylov_index: int, time_point: float):
        def build_circuit(**_kwargs: Any) -> QuantumCircuit:
            circuit = QuantumCircuit(num_qubits)
            prepare_hf_reference_bits(circuit, hamiltonian, num_qubits=num_qubits)
            if not np.isclose(time_point, 0.0):
                repetitions = max(krylov_index, 1) * trotter_steps_per_interval
                if trotter_order <= 1:
                    synthesis: Any = LieTrotter(reps=repetitions)
                else:
                    synthesis = SuzukiTrotter(order=trotter_order, reps=repetitions)
                circuit.append(
                    PauliEvolutionGate(
                        pauli_hamiltonian,
                        time=float(time_point),
                        synthesis=synthesis,
                    ),
                    list(range(num_qubits)),
                )
            # Primitive samplers do not all decompose PauliEvolutionGate. Keep
            # the declared Trotter synthesis while sending a basis-gate circuit
            # to Aer and Runtime samplers.
            return circuit.decompose(reps=2)

        return build_circuit

    samples_by_state: list[SKQDKrylovSample] = []
    circuit_metadata: list[dict[str, Any]] = []
    work_ledger: dict[str, Any] = {
        "ledger_version": 1,
        "counting_scope": "worker_observed",
        "sampler_run_attempts": 0,
        "sampler_successful_runs": 0,
        "sampler_retry_count": 0,
        "sampler_requested_shots_total": 0,
        "sampler_returned_raw_sample_rows": 0,
        "sampler_retained_sample_rows": 0,
    }
    for krylov_index in range(skqd_config.krylov_extension_dim):
        time_point = float(krylov_index * sampling_time_step)
        samples, _circuit = sample_bitstring_matrix(
            backend,
            num_bits=num_qubits,
            total_samples=skqd_config.samples_per_state,
            rng=np.random.default_rng(skqd_config.seed + krylov_index),
            sampling_circuit_factory=factory_for_time(krylov_index, time_point),
            return_circuit=True,
            work_ledger=work_ledger,
            retry_with_increased_shots=False,
        )
        samples = np.asarray(samples, dtype=bool)
        if samples.shape[0] < skqd_config.samples_per_state:
            raise RuntimeError(
                f"SKQD sampler returned {samples.shape[0]} rows for Krylov state "
                f"{krylov_index}; requested {skqd_config.samples_per_state}"
            )
        samples = samples[: skqd_config.samples_per_state]
        work_ledger["sampler_retained_sample_rows"] += int(samples.shape[0])
        samples_by_state.append(
            SKQDKrylovSample(
                krylov_index=krylov_index,
                time_point=time_point,
                bitstring_matrix=samples,
            )
        )
        circuit_metadata.append(
            {
                "krylov_index": krylov_index,
                "time_point": time_point,
                "num_qubits": int(getattr(_circuit, "num_qubits", num_qubits)),
                "depth": (
                    int(_circuit.depth())
                    if callable(getattr(_circuit, "depth", None))
                    else None
                ),
                "trotter_repetitions": (
                    max(krylov_index, 1) * trotter_steps_per_interval
                    if not np.isclose(time_point, 0.0)
                    else 0
                ),
                "operation_names": sorted(
                    {
                        str(instruction.operation.name)
                        for instruction in getattr(_circuit, "data", [])
                    }
                ),
            }
        )

    reference_state, reference_state_source = build_hf_reference_state_with_source(
        hamiltonian,
        fallback_dim=2**num_qubits,
    )
    reference_descriptor = build_reference_descriptor(
        state=reference_state,
        reference_source=reference_state_source,
        preparation_path="sampler_hf_circuit",
        execution_mode="sampler_circuits",
        target_sector={
            "alpha": getattr(hamiltonian, "num_electrons_alpha", None),
            "beta": getattr(hamiltonian, "num_electrons_beta", None),
        },
        circuit_metadata=circuit_metadata,
        backend_target=getattr(backend_context, "backend_target", None),
        ansatz_name="hartree_fock",
    )
    sample_union = merge_krylov_samples(samples_by_state, work_ledger=work_ledger)
    return sample_union, {
        "algorithm_variant": "skqd_sample_union",
        "sampling_mode": "sample_union_sampler",
        "sampling_source": "sampler_krylov_circuits",
        "reference_policy": "hartree_fock",
        "reference_source": "hf_sampler_circuit",
        "reference_state_source": reference_state_source,
        "reference_descriptor": reference_descriptor,
        "execution_mode": "sampler_circuits",
        "backend_target": getattr(backend_context, "backend_target", None),
        "krylov_state_count": skqd_config.krylov_extension_dim,
        "samples_per_state": skqd_config.samples_per_state,
        "seed": skqd_config.seed,
        "trotter_steps": skqd_config.trotter_steps,
        "trotter_steps_per_krylov_interval": trotter_steps_per_interval,
        "trotter_order": trotter_order,
        "trotter_synthesis": synthesis_name,
        "trotter_step_policy": "fixed_delta_t",
        "time_step": sampling_time_step,
        "krylov_time_step_policy": time_step_metadata,
        "krylov_circuit_metadata": circuit_metadata,
        "work_ledger": dict(sample_union.work_ledger),
    }


__all__ = [
    "execute_sample_union_workflow",
    "execute_sampler_sample_union_workflow",
    "resolve_sampling_time_step",
]
