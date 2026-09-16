"""Tests for SKQD paper-faithful time-step scaling and Trotter synthesis."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.algorithms.skqd import sample_union as workflow
from worker.chemistry.algorithms.skqd.config import resolve_skqd_config
from worker.chemistry.algorithms.skqd.spectral_width import (
    estimate_action_spectral_width,
    estimate_dense_spectral_width,
    estimate_pauli_spectral_width,
    paper_time_step,
)
from worker.chemistry.hamiltonian_action import build_hamiltonian_action


def test_config_defaults_to_paper_time_step_policy_and_second_order_trotter() -> None:
    result = resolve_skqd_config({})

    assert result.sampling_time_step is None
    assert result.time_step_policy == "paper_spectral_width_pi_over_delta_e"
    assert result.trotter_order == 2
    assert result.trotter_steps == 1


def test_config_honors_explicit_time_step_and_trotter_order() -> None:
    result = resolve_skqd_config({"time_step": 0.3, "trotter_order": 1})

    assert result.sampling_time_step == pytest.approx(0.3)
    assert result.time_step_policy == "explicit_user_time_step"
    assert result.trotter_order == 1


def test_estimate_dense_spectral_width_matches_exact_range() -> None:
    operator = np.diag([-2.0, 1.0, 3.0]).astype(complex)

    width, source = estimate_dense_spectral_width(operator)

    assert width == pytest.approx(5.0)
    assert source == "exact_dense_spectrum"
    # Delta t = pi / Delta E_{N-1}
    assert paper_time_step(width) == pytest.approx(np.pi / 5.0)


def test_estimate_pauli_spectral_width_uses_coefficient_l1_bound() -> None:
    pauli = SparsePauliOp.from_list([("Z", 1.5), ("X", -0.5)])

    width, source = estimate_pauli_spectral_width(pauli)

    assert width == pytest.approx(2.0 * (1.5 + 0.5))
    assert source == "pauli_coefficient_l1_bound"


def test_estimate_action_spectral_width_matches_dense_sector() -> None:
    hamiltonian = SimpleNamespace(
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        one_body_tensor=np.diag([-1.0, 0.5]),
        two_body_tensor=np.zeros((2, 2, 2, 2)),
        constant=0.0,
    )
    action = build_hamiltonian_action(hamiltonian)

    width, source = estimate_action_spectral_width(action)

    assert width > 0.0
    assert source == "exact_sector_spectrum"


def test_large_action_spectral_width_uses_safe_pauli_bound() -> None:
    diagonal = np.linspace(-100.0, 100.0, 5000)
    action = SimpleNamespace(
        dimension=diagonal.size,
        matvec=lambda vector: diagonal * vector,
    )
    pauli = SparsePauliOp.from_list([("Z", 100.0)])

    width, source = estimate_action_spectral_width(action, pauli_hamiltonian=pauli)

    assert width == pytest.approx(200.0)
    assert width >= diagonal[-1] - diagonal[0]
    assert source == "pauli_coefficient_l1_bound"


def test_large_action_without_safe_spectral_bound_fails_closed() -> None:
    action = SimpleNamespace(dimension=5000, matvec=lambda vector: vector)

    with pytest.raises(ValueError, match="conservative Pauli spectral bound"):
        estimate_action_spectral_width(action)


def test_resolve_sampling_time_step_applies_paper_scaling_when_auto() -> None:
    config = SimpleNamespace(
        sampling_time_step=None,
        time_step_policy="paper_spectral_width_pi_over_delta_e",
    )

    time_step, metadata = workflow.resolve_sampling_time_step(
        config,
        spectral_width=4.0,
        spectral_source="pauli_coefficient_l1_bound",
    )

    assert time_step == pytest.approx(np.pi / 4.0)
    assert metadata["time_step_policy"] == "paper_spectral_width_pi_over_delta_e"
    assert metadata["spectral_width"] == pytest.approx(4.0)
    assert metadata["spectral_width_source"] == "pauli_coefficient_l1_bound"


def test_resolve_sampling_time_step_honors_explicit_value() -> None:
    config = SimpleNamespace(
        sampling_time_step=0.15,
        time_step_policy="explicit_user_time_step",
    )

    time_step, metadata = workflow.resolve_sampling_time_step(
        config,
        spectral_width=4.0,
        spectral_source="pauli_coefficient_l1_bound",
    )

    assert time_step == pytest.approx(0.15)
    assert metadata["time_step_policy"] == "explicit_user_time_step"


def test_sampler_workflow_uses_second_order_suzuki_trotter_and_auto_time_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake_sample_bitstring_matrix(backend, **kwargs):
        del backend
        circuit = kwargs["sampling_circuit_factory"]()
        calls.append(circuit)
        index = len(calls) - 1
        return np.asarray([[index == 1]], dtype=bool).repeat(3, axis=0), circuit

    monkeypatch.setattr(workflow, "sample_bitstring_matrix", fake_sample_bitstring_matrix)
    hamiltonian = SimpleNamespace(
        num_qubits=1,
        pauli_hamiltonian=SparsePauliOp.from_list([("X", 1.0)]),
    )
    config = SimpleNamespace(
        krylov_extension_dim=2,
        sampling_time_step=None,
        time_step_policy="paper_spectral_width_pi_over_delta_e",
        samples_per_state=3,
        seed=7,
        trotter_steps=1,
        trotter_order=2,
    )

    _result, metadata = workflow.execute_sampler_sample_union_workflow(
        hamiltonian=hamiltonian,
        backend=object(),
        skqd_config=config,
        backend_context=SimpleNamespace(backend_target="aer_simulator"),
    )

    assert metadata["trotter_order"] == 2
    assert metadata["trotter_synthesis"] == "suzuki_trotter_order_2"
    # Delta t = pi / (2 * sum|c_i|) = pi / 2 for a single unit-coefficient term.
    assert metadata["time_step"] == pytest.approx(np.pi / 2.0)
    assert metadata["krylov_time_step_policy"]["spectral_width_source"] == (
        "pauli_coefficient_l1_bound"
    )
