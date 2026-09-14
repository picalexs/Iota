"""Pure helpers for normalizing backend metadata into API models."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from statistics import median
from typing import Any

from app.models.enums import BackendTarget
from app.schemas.backend import BackendProcessorType, BackendSummary

logger = logging.getLogger(__name__)


def summarize_ibm_backend(backend: Any) -> BackendSummary:
    """Convert an IBM Runtime backend object into the public summary model."""
    name = string_attr_or_call(backend, "name") or "unknown_ibm_backend"
    status = safe_call(getattr(backend, "status", None))
    configuration = safe_call(getattr(backend, "configuration", None))
    properties = safe_call(getattr(backend, "properties", None))

    basis_gates = list_attr(backend, "basis_gates") or list_attr(configuration, "basis_gates")
    raw_coupling_map = list_attr(backend, "coupling_map") or list_attr(
        configuration, "coupling_map"
    )
    coupling_map = normalize_coupling_map(raw_coupling_map)
    pending_jobs = int_attr(status, "pending_jobs")
    operational = bool_attr(status, "operational")
    error_rate = extract_error_rate(properties)
    processor_type = extract_processor_type(backend, configuration)
    qubit_errors = extract_qubit_errors(properties)
    gate_errors = extract_gate_errors(properties)

    return BackendSummary(
        target=BackendTarget.IBM_RUNTIME,
        name=name,
        display_name=name,
        available=operational is not False,
        credential_configured=True,
        credentials_usable=True,
        simulator=False,
        supports_noise_profile=False,
        supports_transpile_preview=True,
        num_qubits=int_attr(backend, "num_qubits") or int_attr(configuration, "num_qubits"),
        pending_jobs=pending_jobs,
        operational=operational,
        basis_gates=basis_gates,
        coupling_map=coupling_map,
        coupling_map_edges=len(coupling_map) if coupling_map is not None else None,
        max_shots=int_attr(backend, "max_shots") or int_attr(configuration, "max_shots"),
        error_rate=error_rate,
        processor_type=processor_type,
        qubit_errors=qubit_errors,
        gate_errors=gate_errors,
    )


def summarize_ibm_calibration_payload(
    payload: Mapping[str, Any] | None,
) -> tuple[float | None, list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """Extract catalog-safe calibration fields from a Runtime properties response."""
    if payload is None:
        return None, None, None

    qubit_errors = _payload_qubit_errors(payload)
    gate_errors = _payload_gate_errors(payload)
    gate_values = [item["error"] for item in gate_errors or [] if item["error"] is not None]
    readout_values = [
        item["readout_error"] for item in qubit_errors or [] if item["readout_error"] is not None
    ]
    values = gate_values or readout_values
    error_rate = float(median(values)) if values else None
    return error_rate, qubit_errors, gate_errors


def _payload_qubit_errors(payload: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    raw_qubits = payload.get("qubits")
    if not isinstance(raw_qubits, Sequence) or isinstance(raw_qubits, (str, bytes)):
        return None

    rows: list[dict[str, Any]] = []
    for index, parameters in enumerate(raw_qubits):
        if not isinstance(parameters, Sequence) or isinstance(parameters, (str, bytes)):
            continue
        readout_error = _payload_parameter_value(parameters, "readout_error")
        t1 = _payload_parameter_value(parameters, "T1")
        t2 = _payload_parameter_value(parameters, "T2")
        if readout_error is None and t1 is None and t2 is None:
            continue
        rows.append(
            {
                "qubit": index,
                "readout_error": readout_error,
                "t1_us": t1,
                "t2_us": t2,
                "operational": True,
            }
        )
    return rows or None


def _payload_gate_errors(payload: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    raw_gates = payload.get("gates")
    if not isinstance(raw_gates, Sequence) or isinstance(raw_gates, (str, bytes)):
        return None

    rows: list[dict[str, Any]] = []
    for gate in raw_gates:
        if not isinstance(gate, Mapping):
            continue
        qubits = gate.get("qubits")
        parameters = gate.get("parameters")
        if (
            not isinstance(qubits, Sequence)
            or isinstance(qubits, (str, bytes))
            or len(qubits) < 2
            or not isinstance(parameters, Sequence)
            or isinstance(parameters, (str, bytes))
        ):
            continue
        try:
            source, target = int(qubits[0]), int(qubits[1])
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "source": source,
                "target": target,
                "gate": str(gate.get("gate") or gate.get("name") or "cx"),
                "error": _payload_parameter_value(parameters, "gate_error"),
                "length_ns": _payload_parameter_value(parameters, "gate_length"),
            }
        )
    return rows or None


def _payload_parameter_value(parameters: Sequence[Any], name: str) -> float | None:
    for parameter in parameters:
        if isinstance(parameter, Mapping) and parameter.get("name") == name:
            return float_or_none(parameter.get("value"))
    return None


def preview_metadata_for_backend(backend: BackendSummary) -> dict[str, Any]:
    """Return the metadata fields exposed by the transpile preview response."""
    metadata: dict[str, Any] = {
        "backend_available": backend.available,
        "simulator": backend.simulator,
    }
    if backend.num_qubits is not None:
        metadata["backend_num_qubits"] = backend.num_qubits
    if backend.basis_gates is not None:
        metadata["basis_gates"] = backend.basis_gates
    if backend.coupling_map is not None:
        metadata["coupling_map"] = backend.coupling_map
    if backend.coupling_map_edges is not None:
        metadata["coupling_map_edges"] = backend.coupling_map_edges
    if backend.pending_jobs is not None:
        metadata["pending_jobs"] = backend.pending_jobs
    return metadata


def safe_call(callable_obj: Any) -> Any:
    """Call provider metadata methods and omit fields that the provider cannot read."""
    if callable_obj is None:
        return None
    try:
        return callable_obj()
    except Exception as exc:
        logger.debug(
            "Backend metadata method failed; omitting the affected field (%s)",
            type(exc).__name__,
        )
        return None


def string_attr_or_call(obj: Any, attr: str) -> str | None:
    value = getattr(obj, attr, None)
    if callable(value):
        value = safe_call(value)
    return str(value) if value is not None else None


def extract_processor_type(*candidates: Any) -> BackendProcessorType | None:
    for candidate in candidates:
        if candidate is None:
            continue

        processor_type = getattr(candidate, "processor_type", None)
        if callable(processor_type):
            processor_type = safe_call(processor_type)
        normalized = normalize_processor_type(processor_type)
        if normalized is not None:
            return normalized

        direct = normalize_processor_type(candidate)
        if direct is not None:
            return direct

    return None


def normalize_processor_type(value: Any) -> BackendProcessorType | None:
    if value is None:
        return None

    if isinstance(value, dict):
        family = clean_string(value.get("family"))
        revision = normalize_processor_revision(value.get("revision"))
        segment = clean_string(value.get("segment"))
    else:
        family = clean_string(getattr(value, "family", None))
        revision = normalize_processor_revision(getattr(value, "revision", None))
        segment = clean_string(getattr(value, "segment", None))

    if family is None and revision is None and segment is None:
        return None

    return BackendProcessorType(family=family, revision=revision, segment=segment)


def normalize_processor_revision(value: Any) -> str | None:
    raw = clean_string(value)
    if raw is None:
        return None
    return raw if raw.lower().startswith("r") else f"r{raw}"


def clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def int_attr(obj: Any, attr: str) -> int | None:
    value = getattr(obj, attr, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bool_attr(obj: Any, attr: str) -> bool | None:
    value = getattr(obj, attr, None)
    return value if isinstance(value, bool) else None


def list_attr(obj: Any, attr: str) -> list[Any] | None:
    value = getattr(obj, attr, None)
    if value is None:
        return None
    return list(value)


def normalize_coupling_map(value: Sequence[Any] | None) -> list[list[int]] | None:
    if value is None:
        return None

    edges: list[list[int]] = []
    for edge in value:
        try:
            source, target = edge
            edges.append([int(source), int(target)])
        except (TypeError, ValueError):
            continue
    return edges


def extract_error_rate(properties: Any) -> float | None:
    if properties is None:
        return None

    direct_error = direct_error_rate(properties)
    if direct_error is not None:
        return direct_error

    values = gate_error_values(properties) or readout_error_values(properties)
    return float(median(values)) if values else None


def direct_error_rate(properties: Any) -> float | None:
    for attr in ("gate_error", "readout_error"):
        value = getattr(properties, attr, None)
        if not callable(value):
            continue
        try:
            direct_error = float_or_none(value())
        except TypeError:
            continue
        if direct_error is not None:
            return direct_error
    return None


def gate_error_values(properties: Any) -> list[float]:
    values: list[float] = []
    for gate in getattr(properties, "gates", []) or []:
        for parameter in getattr(gate, "parameters", []) or []:
            if getattr(parameter, "name", None) == "gate_error":
                numeric = float_or_none(getattr(parameter, "value", None))
                if numeric is not None:
                    values.append(numeric)
    return values


def readout_error_values(properties: Any) -> list[float]:
    values: list[float] = []
    for qubit in getattr(properties, "qubits", []) or []:
        for parameter in qubit or []:
            if getattr(parameter, "name", None) == "readout_error":
                numeric = float_or_none(getattr(parameter, "value", None))
                if numeric is not None:
                    values.append(numeric)
    return values


def extract_qubit_errors(properties: Any) -> list[dict[str, Any]] | None:
    if properties is None:
        return None

    rows: list[dict[str, Any]] = []
    for index, qubit in enumerate(getattr(properties, "qubits", []) or []):
        readout_error = parameter_value(qubit, "readout_error")
        t1 = parameter_value(qubit, "T1")
        t2 = parameter_value(qubit, "T2")
        if readout_error is None and t1 is None and t2 is None:
            continue
        rows.append(
            {
                "qubit": index,
                "readout_error": readout_error,
                "t1_us": t1,
                "t2_us": t2,
                "operational": True,
            }
        )
    return rows or None


def extract_gate_errors(properties: Any) -> list[dict[str, Any]] | None:
    if properties is None:
        return None

    rows: list[dict[str, Any]] = []
    for gate in getattr(properties, "gates", []) or []:
        qubits = getattr(gate, "qubits", None)
        if not isinstance(qubits, Sequence) or len(qubits) < 2:
            continue
        error = parameter_value(getattr(gate, "parameters", []) or [], "gate_error")
        length = parameter_value(getattr(gate, "parameters", []) or [], "gate_length")
        rows.append(
            {
                "source": int(qubits[0]),
                "target": int(qubits[1]),
                "gate": str(getattr(gate, "gate", None) or getattr(gate, "name", None) or "cx"),
                "error": error,
                "length_ns": length,
            }
        )
    return rows or None


def parameter_value(parameters: Sequence[Any], name: str) -> float | None:
    for parameter in parameters:
        if getattr(parameter, "name", None) == name:
            return float_or_none(getattr(parameter, "value", None))
    return None


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
