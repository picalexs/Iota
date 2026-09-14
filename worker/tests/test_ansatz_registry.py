"""Tests for VQE ansatz registry behavior."""

import pytest
from qiskit.quantum_info import Statevector

from worker.chemistry.ansatz_registry import build_ansatz, supported_ansatzes


def test_supported_ansatzes_contains_phase2_set() -> None:
    assert supported_ansatzes() == {
        "efficientsu2",
        "numberpreserving",
        "realamplitudes",
        "twolocal",
    }


def test_build_ansatz_accepts_aliases() -> None:
    efficient = build_ansatz(ansatz_name="EfficientSU2", num_qubits=4)
    alias = build_ansatz(ansatz_name="two_local", num_qubits=4)

    assert efficient.num_qubits == 4
    assert alias.num_qubits == 4


def test_build_ansatz_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unsupported ansatz"):
        build_ansatz(ansatz_name="UnknownAnsatz", num_qubits=2)


def test_twolocal_is_distinct_from_efficientsu2() -> None:
    twolocal = build_ansatz(ansatz_name="TwoLocal", num_qubits=4, reps=2)
    efficientsu2 = build_ansatz(ansatz_name="EfficientSU2", num_qubits=4, reps=2)

    assert twolocal.num_qubits == 4
    assert efficientsu2.num_qubits == 4
    assert (
        twolocal.num_parameters != efficientsu2.num_parameters or twolocal.name != efficientsu2.name
    )


def test_build_ansatz_reps_propagates() -> None:
    for reps in (1, 2, 3):
        ansatz = build_ansatz(ansatz_name="EfficientSU2", num_qubits=4, reps=reps)
        assert ansatz.num_parameters > 0
        prev = (
            build_ansatz(ansatz_name="EfficientSU2", num_qubits=4, reps=reps - 1)
            if reps > 1
            else None
        )
        if prev is not None:
            assert ansatz.num_parameters > prev.num_parameters


def test_default_reps_is_2() -> None:
    ansatz_default = build_ansatz(ansatz_name="EfficientSU2", num_qubits=4)
    ansatz_explicit = build_ansatz(ansatz_name="EfficientSU2", num_qubits=4, reps=2)
    assert ansatz_default.num_parameters == ansatz_explicit.num_parameters


def test_number_preserving_ansatz_keeps_spin_sectors() -> None:
    ansatz = build_ansatz(
        ansatz_name="NumberPreserving",
        num_qubits=6,
        reps=3,
        num_electrons_alpha=1,
        num_electrons_beta=2,
    )
    state = Statevector(ansatz.assign_parameters([0.31] * ansatz.num_parameters))
    probabilities = state.probabilities_dict()

    for bitstring, probability in probabilities.items():
        if probability < 1e-10:
            continue
        # Qiskit displays the highest-index qubit first.
        alpha = bitstring[-3:]
        beta = bitstring[:3]
        assert alpha.count("1") == 1
        assert beta.count("1") == 2


def test_number_preserving_requires_an_explicit_sector() -> None:
    with pytest.raises(ValueError, match="requires num_electrons"):
        build_ansatz(ansatz_name="NumberPreserving", num_qubits=4)
