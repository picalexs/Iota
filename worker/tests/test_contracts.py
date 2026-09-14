"""Structural tests for worker orchestration contracts."""

from __future__ import annotations

from types import SimpleNamespace

from worker.adapters.base import AdapterCapabilities
from worker.chemistry.types import ChemistryInput, HamiltonianBundle, VQEResult
from worker.contracts import (
    BackendAdapterContract,
    ChemistryInputContract,
    HamiltonianBundleContract,
    JobObserver,
    ProgressSink,
    RunRepositoryContract,
    SolverResultContract,
)
from worker.persistence.run_repository import SqlRunRepository


class _Adapter:
    capabilities = AdapterCapabilities(
        backend_target="test",
        enabled=True,
        supports_noise_profile=False,
    )

    def create_estimator(self, context=None):
        del context
        return object()

    def create_sampler(self, context=None):
        del context
        return object()

    def execution_metadata(self, context=None):
        del context
        return {}


def test_worker_data_types_satisfy_structural_contracts() -> None:
    chemistry_input = ChemistryInput(atoms=["H"], active_space=(2, 2))
    hamiltonian_bundle = HamiltonianBundle(
        num_spatial_orbitals=2,
        num_qubits=4,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        one_body_tensor=SimpleNamespace(),
        two_body_tensor=SimpleNamespace(),
        constant=0.0,
        pauli_hamiltonian=SimpleNamespace(),
        metadata={},
    )
    result = VQEResult(
        algorithm="vqe",
        primary_energy=-1.0,
        primary_iterations=1,
        converged=True,
        optimal_parameters=[],
        convergence_trace=[],
    )

    assert isinstance(chemistry_input, ChemistryInputContract)
    assert isinstance(hamiltonian_bundle, HamiltonianBundleContract)
    assert isinstance(result, SolverResultContract)


def test_worker_callable_and_repository_contracts_are_small_and_structural() -> None:
    def emit(_payload: dict) -> None:
        return None

    def observe(_job: object, _metadata: dict) -> object:
        return object()

    assert isinstance(emit, ProgressSink)
    assert isinstance(observe, JobObserver)
    assert isinstance(_Adapter(), BackendAdapterContract)
    assert isinstance(SqlRunRepository(SimpleNamespace()), RunRepositoryContract)
