"""Unit tests for backend metadata normalization."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from app.models.enums import BackendTarget
from app.services.backend_metadata import (
    preview_metadata_for_backend,
    safe_call,
    summarize_ibm_backend,
)


def test_summarize_ibm_backend_normalizes_provider_metadata() -> None:
    backend = SimpleNamespace(
        name="ibm_brisbane",
        num_qubits="127",
        status=lambda: SimpleNamespace(operational=True, pending_jobs="3"),
        configuration=lambda: SimpleNamespace(
            basis_gates=("rz", "sx", "cx"),
            coupling_map=((0, 1), (1, 2)),
            max_shots="8192",
            processor_type={"family": "Heron", "revision": 3, "segment": "A"},
        ),
        properties=lambda: SimpleNamespace(
            gates=[
                SimpleNamespace(
                    qubits=(0, 1),
                    name="cx",
                    parameters=[SimpleNamespace(name="gate_error", value=0.02)],
                )
            ],
            qubits=[[SimpleNamespace(name="readout_error", value=0.01)]],
        ),
    )

    summary = summarize_ibm_backend(backend)

    assert summary.target == BackendTarget.IBM_RUNTIME
    assert summary.name == "ibm_brisbane"
    assert summary.num_qubits == 127
    assert summary.pending_jobs == 3
    assert summary.max_shots == 8192
    assert summary.basis_gates == ["rz", "sx", "cx"]
    assert summary.coupling_map == [[0, 1], [1, 2]]
    assert summary.processor_type is not None
    assert summary.processor_type.revision == "r3"
    assert summary.qubit_errors == [
        {
            "qubit": 0,
            "readout_error": 0.01,
            "t1_us": None,
            "t2_us": None,
            "operational": True,
        }
    ]
    assert summary.gate_errors == [
        {
            "source": 0,
            "target": 1,
            "gate": "cx",
            "error": 0.02,
            "length_ns": None,
        }
    ]


def test_preview_metadata_for_backend_keeps_transport_shape_small() -> None:
    backend = SimpleNamespace(
        available=True,
        simulator=False,
        num_qubits=127,
        basis_gates=["rz", "sx"],
        coupling_map=[[0, 1]],
        coupling_map_edges=1,
        pending_jobs=3,
    )

    assert preview_metadata_for_backend(backend) == {
        "backend_available": True,
        "simulator": False,
        "backend_num_qubits": 127,
        "basis_gates": ["rz", "sx"],
        "coupling_map": [[0, 1]],
        "coupling_map_edges": 1,
        "pending_jobs": 3,
    }


def test_safe_call_logs_provider_failure_without_exception_details(caplog) -> None:
    def fail() -> None:
        raise RuntimeError("provider detail must stay out of the log")

    with caplog.at_level(logging.DEBUG, logger="app.services.backend_metadata"):
        assert safe_call(fail) is None

    assert "Backend metadata method failed" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "provider detail" not in caplog.text
