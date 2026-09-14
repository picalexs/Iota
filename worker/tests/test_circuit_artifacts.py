"""Tests for circuit artifact serialization helpers."""

from __future__ import annotations

import pytest

from worker.chemistry import circuit_artifacts
from worker.chemistry.circuit_artifacts import (
    CircuitArtifactOptions,
    enrich_circuit_artifacts,
    serialize_circuit_artifact,
)


class _FakeCircuit:
    num_qubits = 2
    num_clbits = 1

    def depth(self) -> int:
        return 3

    def size(self) -> int:
        return 4

    def count_ops(self) -> dict[str, int]:
        return {"x": 1, "measure": 1}


def test_serialize_circuit_artifact_accepts_options_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        circuit_artifacts,
        "serialize_legacy_circuit_preview",
        lambda _circuit, *, style: {"qubits": 2, "classical_bits": 1, "style": style},
    )

    artifact = serialize_circuit_artifact(
        _FakeCircuit(),
        CircuitArtifactOptions(
            artifact_id="vqe.final",
            algorithm="vqe",
            role="final",
            label="Final VQE circuit",
            representative=True,
            source="optimized_parameters",
            parameters={"bound": True},
            pub_count=2,
            shots=1024,
            job_ids=["job-a"],
            transpiled_preview={"qubits": 2, "style": "iqp", "qasm": "OPENQASM 3.0;"},
        ),
    )

    assert artifact["artifact_id"] == "vqe.final"
    assert artifact["preview"] == {"qubits": 2, "classical_bits": 1, "style": "iqp"}
    assert artifact["parameters"] == {"bound": True}
    assert artifact["pub_count"] == 2
    assert artifact["shots"] == 1024
    assert artifact["job_ids"] == ["job-a"]
    assert artifact["transpiled_preview"]["qasm"] == "OPENQASM 3.0;"


def test_serialize_circuit_artifact_keeps_legacy_keyword_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        circuit_artifacts,
        "serialize_legacy_circuit_preview",
        lambda _circuit, *, style: {"qubits": 2, "style": style},
    )

    artifact = serialize_circuit_artifact(
        _FakeCircuit(),
        artifact_id="sqd.iteration.1.sampler",
        algorithm="sqd",
        role="sqd_sampling",
        label="Recovery iter 1",
        iteration=1,
    )

    assert artifact["id"] == "sqd.iteration.1.sampler"
    assert artifact["algorithm"] == "sqd"
    assert artifact["iteration"] == 1


def test_serialize_circuit_artifact_rejects_mixed_option_styles() -> None:
    with pytest.raises(TypeError, match="either CircuitArtifactOptions or legacy"):
        serialize_circuit_artifact(
            _FakeCircuit(),
            CircuitArtifactOptions(
                artifact_id="qse.reference.hf",
                algorithm="qse",
                role="reference",
                label="Hartree-Fock reference",
            ),
            artifact_id="legacy.id",
        )


def test_enrich_circuit_artifacts_adds_backend_metadata_to_copies() -> None:
    original = {
        "artifact_id": "vqe.final",
        "representative": True,
    }

    enriched = enrich_circuit_artifacts(
        [original],
        backend_metadata={
            "backend_target": "ibm_runtime",
            "primitive_family": "estimator",
            "job_ids": [123],
            "pub_count": 3,
            "shots": 4096,
            "transpilation_summary": {"depth": 5},
            "transpiled_circuit_preview": {
                "qubits": 2,
                "qasm": "OPENQASM 3.0;",
                "ignored": "value",
            },
        },
    )

    assert enriched == [
        {
            "artifact_id": "vqe.final",
            "representative": True,
            "backend_target": "ibm_runtime",
            "primitive_family": "estimator",
            "job_ids": ["123"],
            "pub_count": 3,
            "shots": 4096,
            "transpilation_summary": {"depth": 5},
            "transpiled": {"qubits": 2, "qasm": "OPENQASM 3.0;"},
            "transpiled_preview": {"qubits": 2, "qasm": "OPENQASM 3.0;"},
        }
    ]
    assert original == {"artifact_id": "vqe.final", "representative": True}
