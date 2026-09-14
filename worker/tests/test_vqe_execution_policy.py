"""Tests for VQE execution-path diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.algorithms.vqe.config import select_vqe_execution_policy
from worker.chemistry.vqe_solver import run_vqe


class _FakeEstimatorJob:
    def result(self):
        return [
            SimpleNamespace(
                data=SimpleNamespace(
                    evs=np.asarray([0.0]),
                    stds=np.asarray([0.025]),
                )
            )
        ]


class _FakeEstimator:
    def run(self, pubs):
        del pubs
        return _FakeEstimatorJob()


@pytest.mark.parametrize(
    ("backend_target", "noise_profile", "expected"),
    [
        ("statevector", None, ("local_exact", "statevector_exact")),
        ("aer_simulator", None, ("sampled_aer", "aer_simulator")),
        (
            "aer_simulator",
            {"source": "custom_preset"},
            ("sampled_aer", "aer_custom_noise"),
        ),
        ("ibm_runtime", None, ("hardware", "ibm_runtime")),
        (None, None, (None, "backend_target_unavailable")),
    ],
)
def test_select_vqe_execution_policy_classifies_backend_path(
    backend_target, noise_profile, expected
) -> None:
    assert select_vqe_execution_policy(
        backend_target=backend_target,
        noise_profile=noise_profile,
    ) == expected


def test_run_vqe_records_policy_without_overriding_explicit_optimizer() -> None:
    result = run_vqe(
        hamiltonian=SparsePauliOp.from_list([("Z", 1.0)]),
        backend=_FakeEstimator(),
        config={
            "algorithm": "vqe",
            "max_iterations": 1,
            "optimizer_name": "COBYLA",
            "ansatz_name": "EfficientSU2",
            "initial_point_strategy": "zero",
        },
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile={"source": "custom_preset"},
        ),
    )

    diagnostics = result.optimizer_diagnostics
    assert diagnostics["execution_policy"] == "sampled_aer"
    assert diagnostics["execution_policy_selection_reason"] == "aer_custom_noise"
    assert diagnostics["optimizer_name"] == "COBYLA"
    assert diagnostics["optimizer_selection_reason"] == "explicit"
