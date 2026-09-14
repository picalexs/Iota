import json
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from worker.chemistry.reference_descriptor import (
    ReferenceDescriptor,
    build_reference_descriptor,
    fingerprint_circuit_metadata,
    fingerprint_state_vector,
)


def test_reference_descriptor_is_frozen_and_json_safe() -> None:
    descriptor = ReferenceDescriptor(
        reference_source="hf",
        preparation_path="computational_basis",
        target_sector={"alpha": np.int64(1), "beta": 1},
        sector_probability=np.float64(1.0),
        reference_energy=np.float64(-1.1),
        variance=0.0,
        state_fingerprint="state-hash",
        circuit_fingerprint="circuit-hash",
        backend_target="statevector",
        execution_mode="exact",
        ansatz_name="hf",
        metadata={"shots": np.int64(1024)},
    )

    payload = descriptor.to_metadata()

    json.dumps(payload, allow_nan=False)
    assert payload["target_sector"] == {"alpha": 1, "beta": 1}
    assert payload["metadata"] == {"shots": 1024}
    with pytest.raises(FrozenInstanceError):
        descriptor.execution_mode = "noisy"  # type: ignore[misc]


def test_state_fingerprint_normalizes_scale_and_global_phase() -> None:
    first = fingerprint_state_vector(np.array([1.0, 1.0j]))
    equivalent = fingerprint_state_vector(np.array([2.0j, -2.0]))

    assert first == equivalent


def test_state_fingerprint_changes_with_dimension_or_amplitude() -> None:
    reference = fingerprint_state_vector([1.0, 0.0])

    assert reference != fingerprint_state_vector([1.0, 0.0, 0.0])
    assert reference != fingerprint_state_vector([1.0, 1.0])


@pytest.mark.parametrize(
    "state, message",
    [
        ([], "empty"),
        ([0.0, 0.0], "non-zero"),
        ([float("nan"), 0.0], "finite"),
    ],
)
def test_state_fingerprint_rejects_invalid_states(
    state: list[float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        fingerprint_state_vector(state)


def test_circuit_metadata_fingerprint_is_order_independent() -> None:
    first = fingerprint_circuit_metadata({"qasm": "OPENQASM 3;", "depth": 2})
    equivalent = fingerprint_circuit_metadata(
        {"depth": np.int64(2), "qasm": "OPENQASM 3;"}
    )
    changed = fingerprint_circuit_metadata({"qasm": "OPENQASM 3;", "depth": 3})

    assert first == equivalent
    assert first != changed


def test_circuit_metadata_fingerprint_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError, match="keys must be strings"):
        fingerprint_circuit_metadata({1: "depth"})


def test_build_reference_descriptor_persists_shared_identity_fields() -> None:
    descriptor = build_reference_descriptor(
        state=[1.0, 0.0],
        reference_source="hartree_fock",
        preparation_path="computational_basis",
        execution_mode="exact_statevector",
        target_sector={"alpha": 1, "beta": 1},
        reference_energy=-1.1,
        variance=0.0,
        circuit_metadata={"depth": 1},
        backend_target="statevector",
    )

    assert descriptor["state_fingerprint"]
    assert descriptor["circuit_fingerprint"]
    assert descriptor["target_sector"] == {"alpha": 1, "beta": 1}
