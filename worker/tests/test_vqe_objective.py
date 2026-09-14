"""Tests for the VQE estimator objective adapter."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.algorithms.vqe.objective import (
    evaluate_energy,
    extract_pub_energy,
    extract_pub_standard_error,
)


@pytest.mark.parametrize(
    ("expectations", "expected"),
    [
        (np.asarray([1.25]), 1.25),
        ([2.5], 2.5),
        (3.75, 3.75),
    ],
)
def test_extract_pub_energy_accepts_supported_scalar_shapes(
    expectations: object,
    expected: float,
) -> None:
    result = SimpleNamespace(data=SimpleNamespace(evs=expectations))

    assert extract_pub_energy(result) == expected


def test_extract_pub_standard_error_accepts_estimator_std() -> None:
    result = SimpleNamespace(data=SimpleNamespace(stds=np.asarray([0.025])))

    assert extract_pub_standard_error(result) == pytest.approx(0.025)


def test_extract_pub_standard_error_is_optional() -> None:
    result = SimpleNamespace(data=SimpleNamespace(evs=np.asarray([1.0])))

    assert extract_pub_standard_error(result) is None


def test_evaluate_energy_builds_v2_pub_and_returns_scalar_energy() -> None:
    calls: list[object] = []

    class Job:
        def result(self):
            return [SimpleNamespace(data=SimpleNamespace(evs=np.asarray([0.125])))]

    class Backend:
        def run(self, pubs):
            calls.append(pubs)
            return Job()

    ansatz = object()
    operator = SparsePauliOp.from_list([("Z", 1.0)])
    parameters = np.asarray([0.2, -0.4])

    assert (
        evaluate_energy(
            backend=Backend(),
            ansatz=ansatz,
            operator=operator,
            parameter_values=parameters,
        )
        == 0.125
    )
    assert calls == [[(ansatz, [operator], [[0.2, -0.4]])]]
