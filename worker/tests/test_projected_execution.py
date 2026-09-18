"""Unit tests for shared KQD/QFD projected-execution policies."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from worker.chemistry.algorithms.kqd import workflow as kqd_solver
from worker.chemistry.algorithms.qfd import workflow as qfd_solver
from worker.chemistry.projected_execution import (
    ProjectedExecutionPolicy,
    QSEExecutionPolicy,
    backend_label,
    can_use_sector_action,
    num_qubits,
    num_spatial_orbitals,
    resolve_projected_execution_policy,
    resolve_qse_execution_policy,
    should_use_branch_matrix_elements,
    validate_branch_estimator_feasibility,
)
from worker.chemistry.types import ExecutionPlan


def _context(target: str | None = None, *, noise: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(backend_target=target, noise_profile=noise)


def test_projected_execution_resolves_hamiltonian_dimensions() -> None:
    assert num_qubits(SimpleNamespace(num_qubits=4)) == 4
    assert num_qubits(SimpleNamespace(pauli_hamiltonian=SimpleNamespace(num_qubits=6))) == 6
    assert num_qubits(SimpleNamespace()) == 0

    assert num_spatial_orbitals(SimpleNamespace(num_spatial_orbitals=4.9)) == 4
    assert num_spatial_orbitals(SimpleNamespace(num_spatial_orbitals=True)) is None
    assert num_spatial_orbitals(SimpleNamespace(num_spatial_orbitals=0)) is None


def test_can_use_sector_action_requires_large_noiseless_supported_hamiltonian(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "worker.chemistry.projected_execution.can_build_hamiltonian_action",
        lambda _hamiltonian: True,
    )
    hamiltonian = SimpleNamespace(num_qubits=13)

    assert can_use_sector_action(hamiltonian, _context("statevector")) is True
    assert can_use_sector_action(hamiltonian, _context("statevector", noise=object())) is False
    assert (
        can_use_sector_action(SimpleNamespace(num_qubits=13, dense_operator_matrix=[]), _context())
        is False
    )
    assert can_use_sector_action(SimpleNamespace(num_qubits=12), _context("statevector")) is False


@pytest.mark.parametrize(
    ("context", "backend", "hamiltonian", "expected"),
    [
        (_context("ibm_runtime"), None, SimpleNamespace(num_qubits=2), True),
        (_context("aer_simulator", noise=object()), object(), SimpleNamespace(num_qubits=2), True),
        (
            _context("aer_simulator"),
            object(),
            SimpleNamespace(num_qubits=13, dense_operator_matrix=[]),
            True,
        ),
        (_context("statevector"), object(), SimpleNamespace(num_qubits=13), False),
    ],
)
def test_should_use_branch_matrix_elements_matches_backend_policy(
    context: SimpleNamespace,
    backend: object | None,
    hamiltonian: SimpleNamespace,
    expected: bool,
) -> None:
    assert (
        should_use_branch_matrix_elements(
            hamiltonian=hamiltonian,
            backend=backend,
            backend_context=context,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("target", "noise", "expected_path", "expected_primitive"),
    [
        ("statevector", None, "dense_matrix", None),
        ("aer_simulator", object(), "branch_estimator", "EstimatorV2"),
        ("ibm_runtime", None, "branch_estimator", "EstimatorV2"),
    ],
)
def test_projected_policy_contains_one_path_and_primitive_decision(
    target: str,
    noise: object | None,
    expected_path: str,
    expected_primitive: str | None,
) -> None:
    policy = resolve_projected_execution_policy(
        hamiltonian=SimpleNamespace(num_qubits=2),
        backend_context=_context(target, noise=noise),
    )

    assert isinstance(policy, ProjectedExecutionPolicy)
    assert isinstance(policy, ExecutionPlan)
    assert policy.requested_backend_target == target
    assert policy.actual_path == expected_path
    assert policy.primitive == expected_primitive
    assert policy.requires_estimator is (expected_primitive is not None)
    assert policy.selection_reason


@pytest.mark.parametrize(
    ("target", "noise", "reference_method", "expected_path", "expected_primitive"),
    [
        ("statevector", None, "hf", "local_projected_matrices", None),
        ("statevector", None, "vqe", "local_vqe_reference", "EstimatorV2"),
        ("aer_simulator", object(), "hf", "measured_matrix_elements", "EstimatorV2"),
        ("ibm_runtime", None, "vqe", "measured_matrix_elements", "EstimatorV2"),
    ],
)
def test_qse_policy_owns_measurement_and_reference_primitive_decisions(
    target: str,
    noise: object | None,
    reference_method: str,
    expected_path: str,
    expected_primitive: str | None,
) -> None:
    policy = resolve_qse_execution_policy(
        backend_context=_context(target, noise=noise),
        reference_method=reference_method,
    )

    assert isinstance(policy, QSEExecutionPolicy)
    assert policy.actual_path == expected_path
    assert policy.primitive == expected_primitive
    assert policy.requires_estimator is (expected_primitive is not None)


@pytest.mark.parametrize(
    ("branch", "sector", "target", "expected"),
    [
        (True, False, "ibm_runtime", "hardware_branch_estimator"),
        (True, False, "aer_simulator", "aer_branch_estimator"),
        (False, True, "statevector", "sector_matrix_free"),
        (False, False, "aer_simulator", "aer_simulator"),
        (False, False, "statevector", "dense_matrix"),
    ],
)
def test_backend_label_is_stable(
    branch: bool,
    sector: bool,
    target: str,
    expected: str,
) -> None:
    assert (
        backend_label(
            use_branch_matrix_elements=branch,
            use_sector_action=sector,
            backend_context=_context(target),
        )
        == expected
    )


@pytest.mark.parametrize(
    ("target", "noise", "algorithm", "message"),
    [
        ("aer_simulator", object(), "qfd", "Noisy Aer QFD"),
        ("ibm_runtime", None, "kqd", "IBM Runtime KQD"),
    ],
)
def test_validate_branch_estimator_feasibility_keeps_algorithm_diagnostic(
    target: str,
    noise: object | None,
    algorithm: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_branch_estimator_feasibility(
            SimpleNamespace(num_spatial_orbitals=7),
            _context(target, noise=noise),
            algorithm=algorithm,
        )


def test_validate_branch_estimator_feasibility_raises_run_excluded_with_reason() -> None:
    from worker.exceptions import RunExcludedError

    with pytest.raises(RunExcludedError) as excinfo:
        validate_branch_estimator_feasibility(
            SimpleNamespace(num_spatial_orbitals=7),
            _context("aer_simulator", noise=object()),
            algorithm="kqd",
        )
    assert excinfo.value.reason == "projected_matrix_active_space_too_large"


def test_solver_compatibility_wrappers_keep_algorithm_specific_guardrails() -> None:
    with pytest.raises(ValueError, match="Noisy Aer KQD"):
        kqd_solver._validate_branch_estimator_feasibility(
            SimpleNamespace(num_spatial_orbitals=7),
            _context("aer_simulator", noise=object()),
        )
    with pytest.raises(ValueError, match="IBM Runtime QFD"):
        qfd_solver._validate_branch_estimator_feasibility(
            SimpleNamespace(num_spatial_orbitals=7),
            _context("ibm_runtime"),
        )
