"""Circuit artifact serialization helpers for algorithm metrics."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, fields
from io import StringIO
from typing import Any, cast

logger = logging.getLogger(__name__)

_ARTIFACT_SCHEMA_VERSION = "2.0"
_MAX_SQD_ARTIFACTS = 32


@dataclass(frozen=True, slots=True)
class CircuitArtifactOptions:
    """Options that describe a persisted circuit artifact."""

    artifact_id: str
    algorithm: str
    role: str
    label: str
    phase: str | None = None
    representative: bool = False
    source: str | None = None
    iteration: int | None = None
    parameters: Mapping[str, Any] | None = None
    preview_style: str = "iqp"
    downsampling: dict[str, Any] | None = None
    backend_target: str | None = None
    primitive_family: str | None = None
    job_ids: list[str] | None = None
    pub_count: int | None = None
    shots: int | None = None
    transpilation_summary: dict[str, Any] | None = None
    transpiled: Any | None = None
    transpiled_preview: dict[str, Any] | None = None

    @classmethod
    def from_kwargs(cls, values: Mapping[str, Any]) -> "CircuitArtifactOptions":
        """Build options from legacy keyword arguments."""
        field_names = {field.name for field in fields(cls)}
        unknown = sorted(set(values) - field_names)
        if unknown:
            unknown_names = ", ".join(unknown)
            raise TypeError(f"Unexpected circuit artifact option(s): {unknown_names}")

        required = {"artifact_id", "algorithm", "role", "label"}
        missing = sorted(required - set(values))
        if missing:
            missing_names = ", ".join(missing)
            raise TypeError(f"Missing required circuit artifact option(s): {missing_names}")

        return cls(**{name: values[name] for name in field_names if name in values})


@dataclass(frozen=True, slots=True)
class BackendCircuitMetadata:
    """Run/backend metadata that can be attached to circuit artifacts."""

    backend_target: str | None = None
    primitive_family: str | None = None
    job_ids: list[str] | None = None
    pub_count: int | None = None
    shots: int | None = None
    transpilation_summary: dict[str, Any] | None = None
    transpiled_preview: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BackendCircuitMetadata":
        job_ids = value.get("job_ids")
        transpilation_summary = value.get("transpilation_summary")
        return cls(
            backend_target=_string_or_none(value.get("backend_target")),
            primitive_family=_string_or_none(value.get("primitive_family")),
            job_ids=[str(job_id) for job_id in job_ids]
            if isinstance(job_ids, list) and job_ids
            else None,
            pub_count=_safe_int(value.get("pub_count")),
            shots=_safe_int(value.get("shots")),
            transpilation_summary=dict(transpilation_summary)
            if isinstance(transpilation_summary, Mapping) and transpilation_summary
            else None,
            transpiled_preview=_coerce_preview_payload(value.get("transpiled_circuit_preview")),
        )


def select_sqd_artifact_iterations(total_iterations: int) -> list[int]:
    """Select SQD recovery iterations whose full circuit previews are persisted."""
    total = max(int(total_iterations), 0)
    if total <= _MAX_SQD_ARTIFACTS:
        return list(range(1, total + 1))

    first = list(range(1, 5))
    last = list(range(total - 11, total + 1))
    middle_start = 5
    middle_end = total - 12
    middle_count = 16
    middle = _evenly_spaced_iterations(middle_start, middle_end, middle_count)
    selected = sorted({*first, *middle, *last})
    return [iteration for iteration in selected if 1 <= iteration <= total]


def circuit_artifact_downsampling_policy(
    *,
    total_iterations: int,
    stored_iterations: list[int],
    reason: str = "avoid storing large repeated QASM/SVG payloads",
) -> dict[str, Any]:
    """Return the persisted SQD circuit preview downsampling policy."""
    normalized_stored = sorted({int(value) for value in stored_iterations if value >= 1})
    total = max(int(total_iterations), 0)
    dropped = [
        iteration for iteration in range(1, total + 1) if iteration not in set(normalized_stored)
    ]
    return {
        "name": "all_or_windowed_sqd_iterations",
        "max_stored_iterations": _MAX_SQD_ARTIFACTS,
        "stored_iterations": normalized_stored,
        "dropped_iterations": dropped,
        "reason": reason,
    }


def prepare_hf_reference_bits(circuit: Any, hamiltonian: object, *, num_qubits: int) -> None:
    """Prepare the Hartree-Fock occupation pattern on a computational basis register."""
    if (
        hasattr(hamiltonian, "num_spatial_orbitals")
        and hasattr(hamiltonian, "num_electrons_alpha")
        and hasattr(hamiltonian, "num_electrons_beta")
    ):
        num_orbitals = int(getattr(hamiltonian, "num_spatial_orbitals"))
        num_alpha = int(getattr(hamiltonian, "num_electrons_alpha"))
        num_beta = int(getattr(hamiltonian, "num_electrons_beta"))
        for qubit in range(min(num_alpha, num_orbitals, num_qubits)):
            circuit.x(qubit)
        for offset in range(min(num_beta, num_orbitals)):
            qubit = num_orbitals + offset
            if qubit < num_qubits:
                circuit.x(qubit)


def build_hf_reference_circuit(
    hamiltonian: object,
    *,
    num_qubits: int | None = None,
) -> Any | None:
    """Build a simple Hartree-Fock computational-basis preparation circuit."""
    try:
        from qiskit import QuantumCircuit
    except Exception:
        logger.warning("Failed to import Qiskit while building HF reference circuit", exc_info=True)
        return None

    resolved_qubits = num_qubits
    if resolved_qubits is None and hasattr(hamiltonian, "num_qubits"):
        raw_num_qubits = getattr(hamiltonian, "num_qubits")
        if isinstance(raw_num_qubits, int):
            resolved_qubits = raw_num_qubits

    if not isinstance(resolved_qubits, int) or resolved_qubits < 1:
        return None

    circuit = QuantumCircuit(resolved_qubits)
    prepare_hf_reference_bits(circuit, hamiltonian, num_qubits=resolved_qubits)
    return circuit


def serialize_legacy_circuit_preview(circuit: Any, *, style: str = "iqp") -> dict[str, Any]:
    """Serialize the legacy circuit preview payload used by existing SQD consumers."""
    preview: dict[str, Any] = {
        "qubits": _safe_int(getattr(circuit, "num_qubits", None)),
        "classical_bits": _safe_int(getattr(circuit, "num_clbits", None)),
        "style": style,
    }

    qasm = _serialize_qasm(circuit)
    if qasm is not None:
        preview["qasm"] = qasm

    diagram_svg = _render_circuit_svg(circuit, style=style)
    if diagram_svg is not None:
        preview["diagram_svg"] = diagram_svg

    return preview


def serialize_circuit_artifact(
    circuit: Any,
    options: CircuitArtifactOptions | None = None,
    **legacy_options: Any,
) -> dict[str, Any]:
    """Serialize a typed quantum-circuit artifact for algorithm_metrics."""
    resolved_options = _resolve_circuit_artifact_options(options, legacy_options)
    logical_preview = serialize_legacy_circuit_preview(
        circuit,
        style=resolved_options.preview_style,
    )
    transpiled_payload = _resolve_transpiled_payload(resolved_options)
    artifact: dict[str, Any] = {
        "schema_version": _ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "quantum_circuit",
        "id": resolved_options.artifact_id,
        "artifact_id": resolved_options.artifact_id,
        "algorithm": resolved_options.algorithm,
        "role": resolved_options.role,
        "phase": resolved_options.phase,
        "representative": resolved_options.representative,
        "label": resolved_options.label,
        "qubits": _safe_int(getattr(circuit, "num_qubits", None)),
        "classical_bits": _safe_int(getattr(circuit, "num_clbits", None)),
        "depth": _safe_call_int(circuit, "depth"),
        "size": _safe_call_int(circuit, "size"),
        "operation_counts": _operation_counts(circuit),
        "logical": logical_preview,
        "preview": logical_preview,
    }
    return _attach_circuit_artifact_options(artifact, resolved_options, transpiled_payload)


def maybe_transpiled_preview(
    circuit: Any,
    *,
    backend: Any = None,
    optimization_level: int | None = None,
    seed_transpiler: int | None = None,
) -> dict[str, Any] | None:
    """Best-effort transpilation preview; failures are intentionally non-fatal."""
    if backend is None:
        return None
    try:
        from qiskit import transpile

        kwargs: dict[str, Any] = {}
        if backend is not None:
            kwargs["backend"] = backend
        if optimization_level is not None:
            kwargs["optimization_level"] = int(optimization_level)
        if seed_transpiler is not None:
            kwargs["seed_transpiler"] = int(seed_transpiler)
        transpiled = transpile(circuit, **kwargs)
        preview = {
            "optimization_level": optimization_level,
            "qubits": _safe_int(getattr(transpiled, "num_qubits", None)),
            "depth": _safe_call_int(transpiled, "depth"),
            "size": _safe_call_int(transpiled, "size"),
            "operation_counts": _operation_counts(transpiled),
        }
        return {key: value for key, value in preview.items() if value is not None}
    except Exception:
        logger.debug("Circuit transpilation preview unavailable", exc_info=True)
        return None


def retag_circuit_artifact(
    artifact: dict[str, Any],
    *,
    algorithm: str,
    role: str,
    source: str,
    artifact_id_prefix: str,
    phase: str | None = None,
    representative: bool | None = None,
) -> dict[str, Any]:
    """Copy a nested artifact into a top-level algorithm namespace."""
    copied = dict(artifact)
    original_id = str(copied.get("id") or copied.get("artifact_id") or "artifact")
    copied["algorithm"] = algorithm
    copied["role"] = role
    copied["source"] = source
    if phase is not None:
        copied["phase"] = phase
    if representative is not None:
        copied["representative"] = representative
    copied["id"] = f"{artifact_id_prefix}.{original_id}"
    copied["artifact_id"] = f"{artifact_id_prefix}.{original_id}"
    copied["parent_artifact_id"] = original_id
    return copied


def enrich_circuit_artifacts(
    artifacts: list[dict[str, Any]] | None,
    *,
    backend_metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Attach run-level backend execution metadata to persisted circuit artifacts."""
    if not artifacts:
        return []
    metadata = BackendCircuitMetadata.from_mapping(backend_metadata or {})
    return [_enrich_circuit_artifact(artifact, metadata) for artifact in artifacts]


def _resolve_circuit_artifact_options(
    options: CircuitArtifactOptions | None,
    legacy_options: Mapping[str, Any],
) -> CircuitArtifactOptions:
    if options is not None and legacy_options:
        raise TypeError("Pass either CircuitArtifactOptions or legacy keyword options, not both")
    if options is not None:
        return options
    return CircuitArtifactOptions.from_kwargs(legacy_options)


def _resolve_transpiled_payload(
    options: CircuitArtifactOptions,
) -> dict[str, Any] | None:
    if isinstance(options.transpiled_preview, dict):
        transpiled_source = options.transpiled_preview
    elif options.transpiled is not None:
        transpiled_source = serialize_legacy_circuit_preview(
            options.transpiled,
            style=options.preview_style,
        )
    else:
        transpiled_source = None
    return _coerce_preview_payload(transpiled_source)


def _attach_circuit_artifact_options(
    artifact: dict[str, Any],
    options: CircuitArtifactOptions,
    transpiled_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    _set_if_not_none(artifact, "source", options.source)
    _set_if_not_none(artifact, "backend_target", options.backend_target)
    _set_if_not_none(artifact, "primitive_family", options.primitive_family)
    _set_optional_int(artifact, "iteration", options.iteration)
    _set_optional_int(artifact, "pub_count", options.pub_count)
    _set_optional_int(artifact, "shots", options.shots)
    if options.parameters is not None:
        artifact["parameters"] = dict(options.parameters)
    if options.downsampling is not None:
        artifact["downsampling"] = dict(options.downsampling)
    if options.job_ids:
        artifact["job_ids"] = [str(job_id) for job_id in options.job_ids]
    if options.transpilation_summary:
        artifact["transpilation_summary"] = dict(options.transpilation_summary)
    _attach_transpiled_preview(artifact, transpiled_payload)
    return artifact


def _enrich_circuit_artifact(
    artifact: dict[str, Any],
    metadata: BackendCircuitMetadata,
) -> dict[str, Any]:
    copied = dict(artifact)
    _set_if_not_none(copied, "backend_target", metadata.backend_target)
    _set_if_not_none(copied, "primitive_family", metadata.primitive_family)
    _set_if_not_none(copied, "job_ids", metadata.job_ids)
    _set_if_not_none(copied, "pub_count", metadata.pub_count)
    _set_if_not_none(copied, "shots", metadata.shots)
    _set_if_not_none(copied, "transpilation_summary", metadata.transpilation_summary)
    if bool(copied.get("representative")):
        _attach_transpiled_preview(copied, metadata.transpiled_preview)
    return copied


def _attach_transpiled_preview(
    artifact: dict[str, Any],
    transpiled_payload: dict[str, Any] | None,
) -> None:
    if not transpiled_payload:
        return
    artifact["transpiled"] = dict(transpiled_payload)
    artifact["transpiled_preview"] = dict(transpiled_payload)


def _set_optional_int(
    payload: dict[str, Any],
    key: str,
    value: int | None,
) -> None:
    if value is not None:
        payload[key] = int(value)


def _set_if_not_none(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


def _serialize_qasm(circuit: Any) -> str | None:
    try:
        from qiskit.qasm3 import dumps

        return dumps(circuit)
    except Exception:
        logger.warning("Failed to export circuit artifact as OpenQASM 3", exc_info=True)
        return None


def _render_circuit_svg(circuit: Any, *, style: str) -> str | None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.figure import Figure
        from qiskit.visualization import circuit_drawer

        figure = circuit_drawer(
            circuit,
            output="mpl",
            style=style,
            fold=24,
            idle_wires=False,
            cregbundle=False,
            with_layout=False,
        )
        if not isinstance(figure, Figure):
            return None
        mpl_figure = cast(Figure, figure)
        buffer = StringIO()
        mpl_figure.savefig(buffer, format="svg", bbox_inches="tight", transparent=True)
        plt.close(mpl_figure)
        return buffer.getvalue()
    except Exception:
        logger.warning("Failed to render circuit artifact SVG", exc_info=True)
        return None


def _operation_counts(circuit: Any) -> dict[str, int]:
    count_ops = getattr(circuit, "count_ops", None)
    if not callable(count_ops):
        return {}
    try:
        raw_counts = count_ops()
        if not isinstance(raw_counts, Mapping):
            return {}
        return {str(name): int(count) for name, count in raw_counts.items()}
    except Exception:
        return {}


def _safe_call_int(obj: Any, method_name: str) -> int | None:
    method = getattr(obj, method_name, None)
    if not callable(method):
        return None
    try:
        return _safe_int(method())
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _string_or_none(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _coerce_preview_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    preview = {
        "qubits": _safe_int(value.get("qubits")),
        "classical_bits": _safe_int(value.get("classical_bits")),
        "style": _string_or_none(value.get("style")),
        "qasm": _string_or_none(value.get("qasm")),
        "diagram_svg": _string_or_none(value.get("diagram_svg")),
    }
    return {key: current for key, current in preview.items() if current is not None}


def _evenly_spaced_iterations(start: int, end: int, count: int) -> list[int]:
    if count <= 0 or end < start:
        return []
    if count == 1:
        return [start + (end - start) // 2]

    span = end - start
    selected = [start + round(span * index / (count - 1)) for index in range(count)]
    unique = sorted({value for value in selected if start <= value <= end})
    if len(unique) >= count:
        return unique[:count]

    for candidate in range(start, end + 1):
        if candidate not in unique:
            unique.append(candidate)
        if len(unique) >= count:
            break
    return sorted(unique[:count])
