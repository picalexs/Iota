"""Tests for worker algorithm dispatcher."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp

from shared.contracts.identifiers import RunAlgorithm
from worker.adapters.base import (
    AdapterCapabilities,
    BackendAdapter,
    BackendExecutionContext,
)
from worker.chemistry.backend_selector import select_backend
from worker.chemistry.types import (
    KQDResult,
    QFDResult,
    QSEResult,
    SKQDResult,
    SQDResult,
)
from worker.exceptions import BackendError
from worker.jobs.dispatcher import (
    PrimitiveRequirement,
    algorithm_definitions,
    dispatch_algorithm,
    supported_algorithms,
)


def _dummy_hamiltonian() -> object:
    return SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
    )


def _large_pauli_hamiltonian() -> object:
    return SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("Z" + "I" * 13, 1.0)]),
        num_qubits=14,
    )


class _PrimitiveRejectingBackend(BackendAdapter):
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            backend_target="aer_simulator",
            enabled=True,
            supports_noise_profile=True,
        )

    def create_estimator(self, context=None) -> object:
        del context
        raise AssertionError("dense algorithms must not request an estimator")

    def create_sampler(self, context=None) -> object:
        del context
        raise AssertionError("dense algorithms must not request a sampler")


class _MatrixElementBackend(BackendAdapter):
    def __init__(self) -> None:
        self.estimator_contexts: list[BackendExecutionContext | None] = []

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            backend_target="ibm_runtime",
            enabled=True,
            supports_noise_profile=False,
        )

    def create_estimator(self, context=None) -> object:
        self.estimator_contexts.append(context)
        return StatevectorEstimator()

    def create_sampler(self, context=None) -> object:
        del context
        raise AssertionError("KQD/QFD hardware matrix elements must use an estimator")


def test_supported_algorithms_matches_shared_contract() -> None:
    assert supported_algorithms() == {algorithm.value for algorithm in RunAlgorithm}


def test_algorithm_registry_exposes_runtime_metadata_for_each_algorithm() -> None:
    definitions = algorithm_definitions()

    assert set(definitions) == {algorithm.value for algorithm in RunAlgorithm}
    assert all(definition.algorithm == algorithm for algorithm, definition in definitions.items())
    assert definitions["vqe"].config_namespace == "vqe"
    assert definitions["vqe"].config_resolver(
        {"advanced_config": {"algorithm": "vqe", "max_iterations": 3}}
    ) == {"algorithm": "vqe", "max_iterations": 3}
    assert definitions["vqe"].primitive_requirement is PrimitiveRequirement.ESTIMATOR
    assert (
        definitions["sqd"].primitive_requirement
        is PrimitiveRequirement.SAMPLER_AND_OPTIONAL_ESTIMATOR
    )


def test_dispatch_vqe_with_statevector_backend() -> None:
    backend = select_backend("statevector")
    progress_events: list[dict[str, object]] = []

    result = dispatch_algorithm(
        algorithm="vqe",
        backend=backend,
        config_snapshot={"max_iterations": 4},
        hamiltonian_bundle=_dummy_hamiltonian(),
        progress_callback=progress_events.append,
    )

    assert result.algorithm == "vqe"
    assert result.primary_iterations is not None
    assert result.primary_iterations >= 1
    assert progress_events
    assert all(event["algorithm"] == "vqe" for event in progress_events)
    assert all(event["stage"] == "progress" for event in progress_events)


def test_dispatch_sqd_with_statevector_backend() -> None:
    backend = select_backend("statevector")
    progress_events: list[dict[str, object]] = []

    result = cast(
        "SQDResult",
        dispatch_algorithm(
            algorithm="sqd",
            backend=backend,
            config_snapshot={
                "max_iterations": 3,
                "samples_per_batch": 128,
                "num_batches": 4,
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
        ),
    )

    assert result.algorithm == "sqd"
    assert result.primary_iterations is not None
    assert result.primary_iterations >= 1
    assert result.postselection_summary["total_samples"] == 512
    assert progress_events
    assert progress_events[-1]["algorithm"] == "sqd"
    assert progress_events[-1]["stage"] in {"progress", "completed"}


def test_dispatch_sqd_can_sample_a_vqe_prepared_state() -> None:
    backend = select_backend("statevector")
    progress_events: list[dict[str, object]] = []
    hamiltonian = SimpleNamespace(
        pauli_hamiltonian=SparsePauliOp.from_list([("ZIII", -0.5), ("IZII", -0.25)]),
        num_qubits=4,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        constant=0.0,
    )

    result = cast(
        "SQDResult",
        dispatch_algorithm(
            algorithm="sqd",
            backend=backend,
            config_snapshot={
                "sampling_state_source": "vqe",
                "sampling_vqe_ansatz_name": "NumberPreserving",
                "sampling_vqe_max_iterations": 2,
                "sampling_vqe_reps": 2,
                "max_iterations": 1,
                "samples_per_batch": 16,
                "num_batches": 1,
            },
            hamiltonian_bundle=hamiltonian,
            progress_callback=progress_events.append,
        ),
    )

    assert result.sci_result_package["sampling_source"] == "vqe_correlated_state"
    assert result.sci_result_package["sampling_provider"]["method"] == "vqe"
    assert result.sci_result_package["sampling_provider"]["max_function_evaluations"] == 2
    reference_events = [
        event for event in progress_events if event.get("progress_phase") == "reference"
    ]
    assert reference_events
    assert reference_events[-1]["reference_total_iterations"] == 2


def test_dispatch_kqd_with_statevector_backend() -> None:
    backend = select_backend("statevector")
    progress_events: list[dict[str, object]] = []

    result = cast(
        "KQDResult",
        dispatch_algorithm(
            algorithm="kqd",
            backend=backend,
            config_snapshot={
                "algorithm": "kqd",
                "advanced_config": {
                    "algorithm": "kqd",
                    "krylov_dim": 4,
                    "time_step": 0.1,
                    "evolution_method": "exact",
                },
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
        ),
    )

    assert result.algorithm == "kqd"
    assert result.primary_iterations is not None
    assert result.primary_iterations >= 1
    assert result.krylov_rank == result.primary_iterations
    assert result.orthogonality_metrics["basis_rank"] >= 1
    assert progress_events
    assert progress_events[-1]["algorithm"] == "kqd"
    assert progress_events[-1]["stage"] == "completed"


def test_dispatch_kqd_does_not_request_backend_primitive() -> None:
    progress_events: list[dict[str, object]] = []

    result = cast(
        "KQDResult",
        dispatch_algorithm(
            algorithm="kqd",
            backend=_PrimitiveRejectingBackend(),
            config_snapshot={
                "algorithm": "kqd",
                "krylov_dim": 3,
                "time_step": 0.1,
                "evolution_method": "exact",
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
        ),
    )

    assert result.algorithm == "kqd"
    assert progress_events[-1]["stage"] == "completed"


def test_dispatch_qfd_with_statevector_backend() -> None:
    backend = select_backend("statevector")
    progress_events: list[dict[str, object]] = []

    result = cast(
        "QFDResult",
        dispatch_algorithm(
            algorithm="qfd",
            backend=backend,
            config_snapshot={
                "algorithm": "qfd",
                "advanced_config": {
                    "algorithm": "qfd",
                    "num_time_points": 5,
                    "max_time": 0.8,
                    "time_grid_type": "linear",
                },
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
        ),
    )

    assert result.algorithm == "qfd"
    assert result.primary_iterations == result.conditioning_summary["time_points"]
    assert 1 <= len(result.filter_eigenvalues) <= result.primary_iterations
    assert result.conditioning_summary["requested_time_points"] == pytest.approx(5.0)
    assert progress_events
    assert progress_events[-1]["algorithm"] == "qfd"
    assert progress_events[-1]["stage"] == "completed"


def test_dispatch_qse_with_statevector_backend() -> None:
    backend = select_backend("statevector")
    progress_events: list[dict[str, object]] = []

    result = cast(
        "QSEResult",
        dispatch_algorithm(
            algorithm="qse",
            backend=backend,
            config_snapshot={
                "algorithm": "qse",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "vqe",
                    "excitation_level": "singles",
                    "max_subspace_dim": 4,
                },
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
        ),
    )

    assert result.algorithm == "qse"
    assert result.primary_iterations is not None
    assert result.primary_iterations >= 1
    assert len(result.eigenvalues) >= 1
    assert result.overlap_condition >= 0.0
    assert progress_events
    assert progress_events[-1]["algorithm"] == "qse"
    assert progress_events[-1]["stage"] == "completed"


def test_dispatch_qse_hf_does_not_request_backend_primitive() -> None:
    progress_events: list[dict[str, object]] = []

    result = cast(
        "QSEResult",
        dispatch_algorithm(
            algorithm="qse",
            backend=_PrimitiveRejectingBackend(),
            config_snapshot={
                "algorithm": "qse",
                "advanced_config": {
                    "algorithm": "qse",
                    "reference_method": "hf",
                    "max_subspace_dim": 2,
                },
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
        ),
    )

    assert result.reference_method == "hf"
    assert result.execution_mode == "sector_matrix_free"
    assert progress_events[-1]["stage"] == "completed"


def test_dispatch_skqd_with_statevector_backend() -> None:
    backend = select_backend("statevector")
    progress_events: list[dict[str, object]] = []

    result = cast(
        "SKQDResult",
        dispatch_algorithm(
            algorithm="skqd",
            backend=backend,
            config_snapshot={
                "algorithm": "skqd",
                "advanced_config": {
                    "algorithm": "skqd",
                    "base_sampling_options": {
                        "samples_per_batch": 128,
                        "num_batches": 4,
                        "max_iterations": 3,
                    },
                    "krylov_extension_dim": 3,
                },
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
        ),
    )

    assert result.algorithm == "skqd"
    assert result.primary_iterations is not None
    assert result.primary_iterations >= 1
    assert result.sqd_core["algorithm"] == "sqd"
    assert result.krylov_extension_diagnostics["sampling_mode"] == "sample_union_exact"
    assert result.krylov_extension_diagnostics["selected_solution"] == "skqd_sample_union"
    assert result.krylov_extension_diagnostics["sample_union_energy"] is not None
    assert progress_events
    assert progress_events[-1]["algorithm"] == "skqd"
    assert progress_events[-1]["stage"] == "completed"


def test_dispatch_kqd_allows_aer_time_evolution_without_primitives() -> None:
    progress_events: list[dict[str, object]] = []

    result = cast(
        "KQDResult",
        dispatch_algorithm(
            algorithm="kqd",
            backend=_PrimitiveRejectingBackend(),
            config_snapshot={
                "algorithm": "kqd",
                "krylov_dim": 2,
                "time_step": 0.1,
                "evolution_method": "exact",
                "trotter_steps": 1,
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
            backend_context=BackendExecutionContext(backend_target="aer_simulator"),
        ),
    )

    assert result.algorithm == "kqd"
    assert progress_events[-1]["time_evolution_backend"] == "aer_simulator"


def test_dispatch_qfd_allows_aer_time_evolution_without_primitives() -> None:
    progress_events: list[dict[str, object]] = []

    result = cast(
        "QFDResult",
        dispatch_algorithm(
            algorithm="qfd",
            backend=_PrimitiveRejectingBackend(),
            config_snapshot={
                "algorithm": "qfd",
                "num_time_points": 2,
                "max_time": 0.1,
                "time_grid_type": "linear",
            },
            hamiltonian_bundle=_dummy_hamiltonian(),
            progress_callback=progress_events.append,
            backend_context=BackendExecutionContext(backend_target="aer_simulator"),
        ),
    )

    assert result.algorithm == "qfd"
    assert progress_events[-1]["time_evolution_backend"] == "aer_simulator"


def test_dispatch_kqd_uses_estimator_for_large_aer_matrix_elements(monkeypatch) -> None:
    backend = _MatrixElementBackend()
    captured: dict[str, object | None] = {}

    def _fake_run_kqd(**kwargs):
        captured["backend"] = kwargs["backend"]
        captured["backend_context"] = kwargs["backend_context"]
        return KQDResult(
            algorithm="kqd",
            primary_energy=-1.0,
            primary_iterations=2,
            converged=True,
            ritz_values=[-1.0],
            krylov_rank=2,
            orthogonality_metrics={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
        )

    monkeypatch.setattr("worker.chemistry.algorithms.kqd.definition.run_kqd", _fake_run_kqd)

    result = dispatch_algorithm(
        algorithm="kqd",
        backend=backend,
        config_snapshot={
            "algorithm": "kqd",
            "krylov_dim": 2,
            "time_step": 0.1,
            "evolution_method": "trotter",
        },
        hamiltonian_bundle=_large_pauli_hamiltonian(),
        backend_context=BackendExecutionContext(backend_target="aer_simulator"),
    )

    assert result.algorithm == "kqd"
    assert captured["backend"] is not None
    context = backend.estimator_contexts[0]
    assert context is not None
    assert context.backend_target == "aer_simulator"


def test_dispatch_kqd_uses_estimator_for_noisy_small_aer_matrix_elements(monkeypatch) -> None:
    backend = _MatrixElementBackend()
    captured: dict[str, object | None] = {}

    def _fake_run_kqd(**kwargs):
        captured["backend"] = kwargs["backend"]
        return KQDResult(
            algorithm="kqd",
            primary_energy=-1.0,
            primary_iterations=2,
            converged=True,
            ritz_values=[-1.0],
            krylov_rank=2,
            orthogonality_metrics={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
        )

    monkeypatch.setattr("worker.chemistry.algorithms.kqd.definition.run_kqd", _fake_run_kqd)

    result = dispatch_algorithm(
        algorithm="kqd",
        backend=backend,
        config_snapshot={
            "algorithm": "kqd",
            "krylov_dim": 2,
            "time_step": 0.1,
            "evolution_method": "trotter",
        },
        hamiltonian_bundle=_dummy_hamiltonian(),
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile={"source": "backend_derived", "reference_backend": "ibm_kyiv"},
        ),
    )

    assert result.algorithm == "kqd"
    assert captured["backend"] is not None
    context = backend.estimator_contexts[0]
    assert context is not None
    assert context.noise_profile is not None


def test_dispatch_qfd_uses_estimator_for_large_aer_matrix_elements(monkeypatch) -> None:
    backend = _MatrixElementBackend()
    captured: dict[str, object | None] = {}

    def _fake_run_qfd(**kwargs):
        captured["backend"] = kwargs["backend"]
        captured["backend_context"] = kwargs["backend_context"]
        return QFDResult(
            algorithm="qfd",
            primary_energy=-1.0,
            primary_iterations=2,
            converged=True,
            filter_eigenvalues=[-1.0],
            conditioning_summary={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
        )

    monkeypatch.setattr("worker.chemistry.algorithms.qfd.definition.run_qfd", _fake_run_qfd)

    result = dispatch_algorithm(
        algorithm="qfd",
        backend=backend,
        config_snapshot={"algorithm": "qfd", "num_time_points": 2, "max_time": 0.1},
        hamiltonian_bundle=_large_pauli_hamiltonian(),
        backend_context=BackendExecutionContext(backend_target="aer_simulator"),
    )

    assert result.algorithm == "qfd"
    assert captured["backend"] is not None
    context = backend.estimator_contexts[0]
    assert context is not None
    assert context.backend_target == "aer_simulator"


def test_dispatch_qfd_uses_estimator_for_noisy_small_aer_matrix_elements(monkeypatch) -> None:
    backend = _MatrixElementBackend()
    captured: dict[str, object | None] = {}

    def _fake_run_qfd(**kwargs):
        captured["backend"] = kwargs["backend"]
        return QFDResult(
            algorithm="qfd",
            primary_energy=-1.0,
            primary_iterations=2,
            converged=True,
            filter_eigenvalues=[-1.0],
            conditioning_summary={},
            matrix_element_summary={"matrix_element_strategy": "branch_estimator"},
        )

    monkeypatch.setattr("worker.chemistry.algorithms.qfd.definition.run_qfd", _fake_run_qfd)

    result = dispatch_algorithm(
        algorithm="qfd",
        backend=backend,
        config_snapshot={"algorithm": "qfd", "num_time_points": 2, "max_time": 0.1},
        hamiltonian_bundle=_dummy_hamiltonian(),
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile={"source": "backend_derived", "reference_backend": "ibm_kyiv"},
        ),
    )

    assert result.algorithm == "qfd"
    assert captured["backend"] is not None
    context = backend.estimator_contexts[0]
    assert context is not None
    assert context.noise_profile is not None


def test_dispatch_kqd_uses_estimator_for_ibm_matrix_elements() -> None:
    backend = _MatrixElementBackend()

    result = dispatch_algorithm(
        algorithm="kqd",
        backend=backend,
        config_snapshot={
            "algorithm": "kqd",
            "krylov_dim": 2,
            "time_step": 0.1,
            "evolution_method": "trotter",
            "trotter_steps": 1,
        },
        hamiltonian_bundle=_dummy_hamiltonian(),
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    assert result.algorithm == "kqd"
    assert len(backend.estimator_contexts) == 1


def test_dispatch_unknown_algorithm_raises() -> None:
    backend = select_backend("statevector")

    with pytest.raises(BackendError):
        dispatch_algorithm(
            algorithm="unknown_algorithm",
            backend=backend,
            config_snapshot={},
            hamiltonian_bundle=_dummy_hamiltonian(),
        )
