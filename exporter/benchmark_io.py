#!/usr/bin/env python3
"""Shared input, API, and compact-output helpers for QSS benchmarks."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EXPORT_SCHEMA_VERSION = "qss-benchmark-export.v2"
CANONICAL_FIELDS = (
    "benchmark_id",
    "benchmark_name",
    "entry_id",
    "run_id",
    "molecule_id",
    "molecule",
    "algorithm",
    "basis_set",
    "backend_target",
    "backend_name",
    "requested_shots",
    "effective_shots",
    "requested_estimator_precision",
    "effective_estimator_precision",
    "measurement_mode",
    "simulator_method",
    "noise_source",
    "noise_fingerprint",
    "actual_execution_target",
    "actual_path_class",
    "reference_method",
    "reference_solver_path",
    "reference_basis",
    "reference_active_space",
    "reference_backend_target",
    "reference_validity_status",
    "reference_hamiltonian_sha256",
    "sampler_requested_shots_total",
    "seed",
    "seed_roles",
    "seed_algorithm",
    "seed_sampling",
    "seed_simulator",
    "seed_transpiler",
    "status",
    "execution_generation",
    "restarted_from_run_id",
    "created_at",
    "result_created_at",
    "runtime_seconds",
    "final_energy",
    "reference_energy",
    "signed_error",
    "absolute_error",
    "iterations",
    "converged",
    "reported_energy_is_valid",
    "projected_solve_is_diagnostic",
    "scientific_converged",
    "primary_energy_source",
    "convergence_failure_reason",
    "benchmark_eligible",
    "benchmark_exclusion_reason",
    "error_message",
)

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "excluded"}
SUCCESS_STATUSES = {"completed"}


class ExporterError(RuntimeError):
    """Raised when an exporter input or API response is invalid."""


@dataclass
class SourceBundle:
    """Normalized benchmark source shared by export and plot commands."""

    benchmark: dict[str, Any]
    rows: list[dict[str, Any]]
    source_type: str
    source_id: str
    runtime_sources: Counter[str] = field(default_factory=Counter)
    raw_benchmark: dict[str, Any] | None = None
    raw_runs: dict[str, dict[str, Any]] = field(default_factory=dict)


def _first(mapping: Mapping[str, Any] | None, *keys: str, default: Any = None) -> Any:
    if not isinstance(mapping, Mapping):
        return default
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _record(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        raw = str(value).strip()
        if not raw or raw.lower() in {"none", "null", "nan", "na", "n/a"}:
            return None
        try:
            result = float(raw)
        except ValueError:
            return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    numeric = _number(value)
    if numeric is None:
        return None
    return int(numeric)


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return True
    if raw in {"false", "0", "no", "n"}:
        return False
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


def _parse_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    raw = str(value).strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
    return [item.strip() for item in raw.split(",") if item.strip()]


def _benchmark_execution_fields(
    *,
    result: Mapping[str, Any] | None,
    config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Extract execution-budget provenance from a run export or checkpoint."""
    result_record = _record(result)
    config_record = _record(config)
    options = _record(_first(config_record, "backend_options", "backendOptions"))
    metrics = _record(_first(result_record, "algorithm_metrics", "algorithmMetrics"))
    provenance = _record(
        _first(metrics, "benchmark_provenance", "benchmarkProvenance")
    )
    execution = _record(_first(provenance, "execution"))
    if not execution:
        execution = _record(_first(metrics, "backend_execution", "backendExecution"))

    requested_shots = _first(execution, "requested_shots", "requestedShots")
    if requested_shots is None:
        requested_shots = _first(options, "shots")
    effective_shots = _first(execution, "effective_shots", "effectiveShots")

    requested_precision = _first(
        execution,
        "requested_estimator_precision",
        "requestedEstimatorPrecision",
    )
    if requested_precision is None and "estimator_precision" in options:
        requested_precision = options.get("estimator_precision")
    effective_precision = _first(
        execution,
        "effective_estimator_precision",
        "effectiveEstimatorPrecision",
    )
    noise_profile = _record(_first(config_record, "noise_profile", "noiseProfile"))
    backend_target = _text(_first(config_record, "backend_target", "backendTarget"))
    if (
        requested_precision is None
        and backend_target == "aer_simulator"
        and noise_profile
        and _number(requested_shots) is not None
    ):
        requested_precision = 1.0 / math.sqrt(float(_number(requested_shots)))

    if effective_precision is None:
        effective_precision = requested_precision
    measurement_mode = _text(_first(execution, "measurement_mode", "measurementMode"))
    if measurement_mode is None and _number(effective_precision) is not None:
        measurement_mode = "exact" if float(effective_precision) == 0.0 else "precision_sampled"

    noise_source = _text(_first(execution, "noise_source", "noiseSource"))
    if noise_source is None:
        noise_source = _text(_first(noise_profile, "source"))
    noise_fingerprint = _text(
        _first(execution, "noise_fingerprint", "noiseFingerprint")
    )
    simulator_method = _text(_first(execution, "simulator_method", "simulatorMethod"))
    if simulator_method is None:
        simulator_method = _text(_first(options, "aer_method", "method"))

    ledger = _record(_first(provenance, "work_ledger", "workLedger"))
    if not ledger:
        ledger = _record(_first(metrics, "work_ledger", "workLedger"))

    return {
        "requested_shots": _integer(requested_shots),
        "effective_shots": _integer(effective_shots),
        "requested_estimator_precision": _number(requested_precision),
        "effective_estimator_precision": _number(effective_precision),
        "measurement_mode": measurement_mode,
        "simulator_method": simulator_method,
        "noise_source": noise_source,
        "noise_fingerprint": noise_fingerprint,
        "actual_execution_target": _text(
            _first(execution, "actual_execution_target", "actualExecutionTarget")
        ),
        "actual_path_class": _text(
            _first(execution, "actual_path_class", "actualPathClass")
        ),
        "sampler_requested_shots_total": _integer(
            _first(ledger, "sampler_requested_shots_total", "samplerRequestedShotsTotal")
        ),
    }


def _iso_datetime(value: Any) -> datetime | None:
    raw = _text(value)
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_iso(value: Any) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    parsed = _iso_datetime(raw)
    return parsed.isoformat() if parsed is not None else raw


def _normalize_status(value: Any) -> str:
    raw = _text(value)
    return raw.lower() if raw is not None else "missing"


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def _parse_seed_roles(value: Any) -> list[str]:
    return [str(item) for item in _parse_list(value) if str(item).strip()]


def _backend_name(config: Mapping[str, Any]) -> str | None:
    options = _record(_first(config, "backend_options", "backendOptions"))
    return _text(_first(options, "backend_name", "backendName"))


def _config_seed(config: Mapping[str, Any], algorithm: str | None) -> tuple[int | None, list[str]]:
    advanced = _record(_first(config, "advanced_config", "advancedConfig"))
    algorithm = (algorithm or "").lower()
    roles: list[str] = []

    if algorithm == "vqe" and _number(_first(advanced, "seed")) is not None:
        roles.append("algorithm")
        return _integer(_first(advanced, "seed")), roles

    if algorithm == "sqd" and _number(_first(advanced, "seed")) is not None:
        roles.append("sampling")
        return _integer(_first(advanced, "seed")), roles

    if algorithm == "skqd":
        sampling = _record(_first(advanced, "base_sampling_options", "baseSamplingOptions"))
        value = _first(sampling, "seed")
        if _number(value) is not None:
            roles.append("sampling")
            return _integer(value), roles

    backend_options = _record(_first(config, "backend_options", "backendOptions"))
    simulator_seed = _first(backend_options, "seed_simulator", "seedSimulator")
    if _number(simulator_seed) is not None:
        roles.append("simulator")
        return _integer(simulator_seed), roles

    transpiler_seed = _first(backend_options, "seed_transpiler", "seedTranspiler")
    if _number(transpiler_seed) is not None:
        roles.append("transpiler")
        return _integer(transpiler_seed), roles

    return None, roles


def _config_seeds(config: Mapping[str, Any], algorithm: str | None) -> dict[str, int | None]:
    """Extract all reproducibility seed roles without collapsing them."""
    advanced = _record(_first(config, "advanced_config", "advancedConfig"))
    options = _record(_first(config, "backend_options", "backendOptions"))
    algorithm_name = (algorithm or "").lower()
    sampling = _record(_first(advanced, "base_sampling_options", "baseSamplingOptions"))
    return {
        "seed_algorithm": _integer(_first(advanced, "seed"))
        if algorithm_name == "vqe"
        else None,
        "seed_sampling": _integer(
            _first(sampling, "seed") if algorithm_name == "skqd" else _first(advanced, "seed")
        )
        if algorithm_name in {"sqd", "skqd"}
        else None,
        "seed_simulator": _integer(_first(options, "seed_simulator", "seedSimulator")),
        "seed_transpiler": _integer(_first(options, "seed_transpiler", "seedTranspiler")),
    }


def _benchmark_quality_fields(
    *,
    result: Mapping[str, Any] | None,
    status: str,
    final_energy: float | None,
    reference_energy: float | None,
    converged: bool | None,
) -> dict[str, Any]:
    """Extract scientific eligibility without deleting diagnostic results."""
    result_record = _record(result)
    metrics = _record(_first(result_record, "algorithm_metrics", "algorithmMetrics"))
    provenance = _record(_first(metrics, "benchmark_provenance", "benchmarkProvenance"))
    energy = _record(_first(provenance, "energy"))
    convergence = _record(_first(metrics, "convergence"))
    policy = _record(_first(metrics, "energy_policy", "energyPolicy"))
    reference = _record(
        _first(
            metrics,
            "reference_provenance",
            "referenceProvenance",
            default=_first(provenance, "reference", "reference_provenance"),
        )
    )
    explicit_eligible = _boolean(
        _first(provenance, "benchmark_eligible", "benchmarkEligible")
    )
    explicit_exclusion_reason = _text(
        _first(provenance, "benchmark_exclusion_reason", "benchmarkExclusionReason")
    )

    reported_valid = _boolean(
        _first(
            energy,
            "reported_energy_is_valid",
            "reportedEnergyIsValid",
            default=_first(result_record, "reported_energy_is_valid", "reportedEnergyIsValid"),
        )
    )
    diagnostic = _boolean(
        _first(
            energy,
            "projected_solve_is_diagnostic",
            "projectedSolveIsDiagnostic",
            default=_first(
                convergence,
                "projected_solve_is_diagnostic",
                "projectedSolveIsDiagnostic",
            ),
        )
    )
    scientific = _boolean(
        _first(
            energy,
            "scientific_converged",
            "scientificConverged",
            default=_first(
                convergence,
                "scientific_converged",
                "scientificConverged",
                default=_first(result_record, "scientific_converged", "scientificConverged"),
            ),
        )
    )
    primary_source = _text(
        _first(
            energy,
            "reported_energy_source",
            "reportedEnergySource",
            default=_first(
                policy,
                "primary_energy_source",
                "primaryEnergySource",
                default=_first(result_record, "reported_energy_source", "reportedEnergySource"),
            ),
        )
    )
    failure_reason = _text(
        _first(
            convergence,
            "convergence_failure_reason",
            "convergenceFailureReason",
            default=_first(energy, "reported_energy_invalid_reason", "reportedEnergyInvalidReason"),
        )
    )
    reference_method = _text(_first(reference, "method", "reference_method", "referenceMethod"))
    reference_status = _text(_first(reference, "validity_status", "validityStatus"))

    reason: str | None = None
    if status != "completed":
        reason = f"status_{status}"
    elif final_energy is None or reference_energy is None:
        reason = "missing_energy_or_reference"
    elif reported_valid is False:
        reason = "reported_energy_invalid"
    elif diagnostic is True:
        reason = "projected_solve_diagnostic"
    elif scientific is False or converged is False:
        reason = "scientific_convergence_not_established"
    elif reference_status is not None and reference_status != "valid":
        reason = "reference_provenance_invalid"
    elif reference_method is not None and reference_method.upper() != "CASCI":
        reason = "reference_method_unsupported"
    if explicit_eligible is not None:
        reason = None if explicit_eligible else explicit_exclusion_reason or reason

    return {
        "reference_method": reference_method,
        "reference_solver_path": _text(_first(reference, "solver_path", "solverPath")),
        "reference_basis": _text(_first(reference, "basis")),
        "reference_active_space": _first(reference, "active_space", "activeSpace"),
        "reference_backend_target": _text(
            _first(reference, "backend_target", "backendTarget")
        ),
        "reference_validity_status": reference_status,
        "reference_hamiltonian_sha256": _text(
            _first(reference, "hamiltonian_sha256", "hamiltonianSha256")
        ),
        "reported_energy_is_valid": reported_valid,
        "projected_solve_is_diagnostic": diagnostic,
        "scientific_converged": scientific,
        "primary_energy_source": primary_source,
        "convergence_failure_reason": failure_reason,
        "benchmark_eligible": reason is None,
        "benchmark_exclusion_reason": reason,
    }


def _runtime_seconds(
    run: Mapping[str, Any],
    result: Mapping[str, Any],
    segments: Iterable[Mapping[str, Any]],
) -> tuple[float | None, str | None]:
    metadata = _record(_first(run, "metadata", "run_metadata"))
    explicit = _number(_first(metadata, "runtime_seconds", "runtimeSeconds"))
    if explicit is not None and explicit >= 0:
        return explicit, "run_metadata.runtime_seconds"

    durations = [
        duration
        for segment in segments
        if (duration := _number(_first(segment, "duration_seconds", "durationSeconds"))) is not None
        and duration >= 0
    ]
    if durations:
        return sum(durations), "execution_segments.duration_seconds"

    started = _iso_datetime(_first(run, "created_at", "createdAt"))
    finished = _iso_datetime(_first(result, "created_at", "createdAt"))
    if started is not None and finished is not None:
        elapsed = (finished - started).total_seconds()
        if elapsed >= 0:
            return elapsed, "run.created_at_to_result.created_at"

    return None, None


def _compact_preset(entry: Mapping[str, Any], molecule: Mapping[str, Any]) -> dict[str, Any]:
    preset = _record(_first(entry, "preset"))
    result: dict[str, Any] = {}
    for key in ("key", "name", "formula"):
        value = _text(_first(preset, key))
        if value is not None:
            result[key] = value
    name = _text(_first(molecule, "name"))
    if name is not None:
        result.setdefault("name", name)
    return result


def normalize_api_row(
    *,
    benchmark: Mapping[str, Any],
    entry: Mapping[str, Any],
    run_export: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str | None]:
    """Normalize one saved benchmark entry and optional run export."""

    benchmark_id = _text(_first(benchmark, "id"))
    benchmark_name = _text(_first(benchmark, "name"))
    entry_id = _text(_first(entry, "id", "entry_id", "entryId")) or "entry-unknown"
    run = _record(_first(run_export or {}, "run"))
    molecule = _record(_first(run_export or {}, "molecule"))
    result = _record(_first(run_export or {}, "result"))
    segments = [
        _record(item)
        for item in _parse_list(_first(run_export or {}, "execution_segments", "executionSegments"))
        if isinstance(item, Mapping)
    ]

    algorithm = _text(_first(entry, "algorithm")) or _text(_first(run, "algorithm"))
    algorithm = algorithm.lower() if algorithm is not None else None
    config = _record(_first(run, "config_json", "configJson", "config"))
    execution_fields = _benchmark_execution_fields(result=result, config=config)
    entry_seed = _first(entry, "seed")
    seed, inferred_roles = _config_seed(config, algorithm)
    if _number(entry_seed) is not None:
        seed = _integer(entry_seed)
    seed_roles = _parse_seed_roles(_first(entry, "seed_roles", "seedRoles")) or inferred_roles

    final_energy = _number(
        _first(result, "final_energy", "finalEnergy", "reported_energy", "reportedEnergy", "energy")
    )
    reference_energy = _number(_first(result, "reference_energy", "referenceEnergy"))
    signed_error = _number(_first(result, "signed_error", "signedError"))
    if signed_error is None and final_energy is not None and reference_energy is not None:
        signed_error = final_energy - reference_energy
    absolute_error = abs(signed_error) if signed_error is not None else None

    runtime_seconds, runtime_source = _runtime_seconds(run, result, segments)
    status = _normalize_status(_first(run, "status") or _first(entry, "status"))
    if run_export is None:
        status = _normalize_status(_first(entry, "status", default="missing"))
    converged = _boolean(_first(result, "converged"))
    quality_fields = _benchmark_quality_fields(
        result=result,
        status=status,
        final_energy=final_energy,
        reference_energy=reference_energy,
        converged=converged,
    )
    seed_fields = _config_seeds(config, algorithm)

    row = {
        "benchmark_id": benchmark_id,
        "benchmark_name": benchmark_name,
        "entry_id": entry_id,
        "run_id": _text(_first(entry, "runId", "run_id", "runId"))
        or _text(_first(run, "id")),
        "molecule_id": _text(_first(run, "molecule_id", "moleculeId"))
        or _text(_first(entry, "moleculeId", "molecule_id")),
        "molecule": _text(_first(molecule, "name"))
        or _text(_first(_record(_first(entry, "preset")), "name", "formula")),
        "algorithm": algorithm,
        "basis_set": _text(_first(run, "basis_set", "basisSet"))
        or _text(_first(benchmark, "selectedBasis", "selected_basis")),
        "backend_target": _text(_first(run, "backend_target", "backendTarget")),
        "backend_name": _backend_name(config),
        **execution_fields,
        **quality_fields,
        "seed": seed,
        "seed_roles": seed_roles,
        **seed_fields,
        "status": status,
        "execution_generation": _integer(_first(run, "execution_generation")),
        "restarted_from_run_id": _text(_first(run, "restarted_from_run_id")),
        "created_at": _safe_iso(_first(run, "created_at", "createdAt")),
        "result_created_at": _safe_iso(_first(result, "created_at", "createdAt")),
        "runtime_seconds": runtime_seconds,
        "final_energy": final_energy,
        "reference_energy": reference_energy,
        "signed_error": signed_error,
        "absolute_error": absolute_error,
        "iterations": _integer(_first(result, "iterations")),
        "converged": converged,
        "error_message": _text(
            _first(entry, "errorMessage", "error_message")
            or _first(_record(_first(run, "metadata", "run_metadata")), "error_message", "errorMessage")
        ),
    }
    row["_runtime_source"] = runtime_source
    row["_preset"] = _compact_preset(entry, molecule)
    return {key: row.get(key) for key in CANONICAL_FIELDS} | {
        "_runtime_source": runtime_source,
        "_preset": row["_preset"],
    }, runtime_source


def normalize_folder_row(
    row: Mapping[str, Any],
    *,
    benchmark: Mapping[str, Any] | None = None,
    index: int = 0,
) -> tuple[dict[str, Any], str | None]:
    """Normalize canonical or legacy local benchmark rows."""

    source = dict(row)
    benchmark = benchmark or {}
    run_id = _text(_first(source, "run_id", "runId"))
    entry_id = _text(_first(source, "entry_id", "entryId")) or f"legacy:{index:04d}"
    algorithm = _text(_first(source, "algorithm", "method"))
    molecule = _text(_first(source, "molecule", "molecule_name"))
    final_energy = _number(_first(source, "final_energy", "finalEnergy"))
    reference_energy = _number(_first(source, "reference_energy", "referenceEnergy"))
    signed_error = _number(_first(source, "signed_error", "signedError"))
    if signed_error is None and final_energy is not None and reference_energy is not None:
        signed_error = final_energy - reference_energy
    absolute_error = _number(_first(source, "absolute_error", "energy_error"))
    if absolute_error is None and signed_error is not None:
        absolute_error = abs(signed_error)

    runtime = _number(
        _first(
            source,
            "runtime_seconds",
            "algorithm_wall_time_seconds",
            "wall_time_seconds",
            "end_to_end_wall_time_seconds",
        )
    )
    runtime_source = "folder.runtime_seconds" if runtime is not None else None
    status = _normalize_status(_first(source, "status"))
    if status == "missing" and _first(source, "error"):
        status = "failed"
    converged = _boolean(_first(source, "converged"))
    quality_fields = _benchmark_quality_fields(
        result=source,
        status=status,
        final_energy=final_energy,
        reference_energy=reference_energy,
        converged=converged,
    )
    seed_fields = _config_seeds(source, algorithm)
    for field_name in seed_fields:
        explicit_seed = _number(_first(source, field_name))
        if explicit_seed is not None:
            seed_fields[field_name] = _integer(explicit_seed)

    execution_fields = _benchmark_execution_fields(result=source, config=source)
    for field in (
        "requested_shots",
        "effective_shots",
        "requested_estimator_precision",
        "effective_estimator_precision",
        "measurement_mode",
        "simulator_method",
        "noise_source",
        "noise_fingerprint",
        "actual_execution_target",
        "actual_path_class",
        "sampler_requested_shots_total",
    ):
        if field in source:
            execution_fields[field] = source.get(field)

    canonical = {
        "benchmark_id": _text(_first(source, "benchmark_id", "benchmarkId"))
        or _text(_first(benchmark, "id")),
        "benchmark_name": _text(_first(source, "benchmark_name", "benchmarkName"))
        or _text(_first(benchmark, "name")),
        "entry_id": entry_id,
        "run_id": run_id,
        "molecule_id": _text(_first(source, "molecule_id", "moleculeId")),
        "molecule": molecule,
        "algorithm": algorithm.lower() if algorithm else None,
        "basis_set": _text(_first(source, "basis_set", "basisSet"))
        or _text(_first(benchmark, "selectedBasis", "selected_basis")),
        "backend_target": _text(_first(source, "backend_target", "backendTarget")),
        "backend_name": _text(_first(source, "backend_name", "backendName")),
        **execution_fields,
        **quality_fields,
        "seed": _integer(_first(source, "seed")),
        "seed_roles": _parse_seed_roles(_first(source, "seed_roles", "seedRoles")),
        **seed_fields,
        "status": status,
        "execution_generation": _integer(_first(source, "execution_generation")),
        "restarted_from_run_id": _text(_first(source, "restarted_from_run_id")),
        "created_at": _safe_iso(_first(source, "created_at", "createdAt")),
        "result_created_at": _safe_iso(_first(source, "result_created_at", "resultCreatedAt")),
        "runtime_seconds": runtime,
        "final_energy": final_energy,
        "reference_energy": reference_energy,
        "signed_error": signed_error,
        "absolute_error": absolute_error,
        "iterations": _integer(_first(source, "iterations")),
        "converged": converged,
        "error_message": _text(_first(source, "error_message", "errorMessage", "error")),
    }
    return canonical | {
        "_runtime_source": runtime_source,
        "_preset": _record(_first(source, "preset")),
    }, runtime_source


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExporterError(f"Cannot read JSON file {path}: {exc}") from exc


def _submission_rows(path: Path, benchmark: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build status-only rows from a create_benchmark checkpoint."""

    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise ExporterError(f"Expected an object in {path}")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not all(isinstance(item, Mapping) for item in entries):
        raise ExporterError(f"Expected checkpoint entries in {path}")
    molecules = {
        str(item.get("id")): item
        for item in payload.get("molecules", [])
        if isinstance(item, Mapping) and item.get("id") is not None
    }

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(entries):
        snapshot = _record(item.get("snapshot"))
        config = _record(item.get("run_config", item.get("runConfig")))
        molecule_id = _text(
            _first(snapshot, "moleculeId", "molecule_id")
            or _first(config, "molecule_id", "moleculeId")
        )
        molecule_record = _record(molecules.get(molecule_id or ""))
        preset = _record(_first(snapshot, "preset"))
        options = _record(_first(config, "backend_options", "backendOptions"))
        rows.append(
            {
                "benchmark_id": _text(_first(benchmark, "id")) or _text(payload.get("benchmark_id")),
                "benchmark_name": _text(_first(benchmark, "name")),
                "entry_id": _text(item.get("entry_id"))
                or _text(_first(snapshot, "id", "entry_id", "entryId"))
                or f"checkpoint:{index:04d}",
                "run_id": _text(item.get("run_id")) or _text(_first(snapshot, "runId", "run_id")),
                "molecule_id": molecule_id,
                "molecule": _text(_first(molecule_record, "name"))
                or _text(_first(preset, "name", "formula")),
                "algorithm": _text(_first(snapshot, "algorithm"))
                or _text(_first(config, "algorithm")),
                "basis_set": _text(_first(config, "basis_set_override", "basisSetOverride"))
                or _text(_first(benchmark, "selectedBasis", "selected_basis")),
                "backend_target": _text(_first(config, "backend_target", "backendTarget")),
                "backend_name": _text(_first(options, "backend_name", "backendName")),
                **_benchmark_execution_fields(result=None, config=config),
                "seed": item.get("seed", _first(snapshot, "seed")),
                "seed_roles": item.get("seed_roles", _first(snapshot, "seedRoles", "seed_roles")),
                "status": item.get("status") or _first(snapshot, "status"),
                "error_message": item.get("error_message")
                or _first(snapshot, "errorMessage", "error_message"),
            }
        )
    return rows


def _read_rows_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        value = _read_json(path)
        if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
            raise ExporterError(f"Expected a JSON list of row objects in {path}")
        return [dict(item) for item in value]
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError as exc:
        raise ExporterError(f"Cannot read CSV file {path}: {exc}") from exc


def _find_folder_rows(input_dir: Path) -> Path:
    candidates = (
        "runs.json",
        "runs.csv",
        "benchmark_rows.json",
        "benchmark_rows.csv",
        "benchmark_rows_pipeline.json",
        "benchmark_rows_pipeline.csv",
        "benchmark_rows_parallel.json",
        "benchmark_rows_parallel.csv",
        "benchmark_rows_basis.json",
        "benchmark_rows_basis.csv",
    )
    for name in candidates:
        path = input_dir / name
        if path.is_file():
            return path
    nested_export = input_dir / "export"
    if nested_export.is_dir():
        return _find_folder_rows(nested_export)
    submission = input_dir / "submission.json"
    if submission.is_file():
        return submission
    expected = ", ".join(candidates)
    raise ExporterError(f"No benchmark rows found in {input_dir}; expected {expected}")


def compact_benchmark(benchmark: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "id",
        "name",
        "campaignId",
        "campaign_id",
        "campaignMetadata",
        "campaign_metadata",
        "selectedMoleculeKeys",
        "selected_molecule_keys",
        "selectedAlgorithms",
        "selected_algorithms",
        "selectedBasis",
        "selected_basis",
        "selectedBackendMode",
        "selected_backend_mode",
        "selectedBackendName",
        "selected_backend_name",
        "chemicalAccuracyHa",
        "chemical_accuracy_ha",
        "createdAt",
        "created_at",
        "updatedAt",
        "updated_at",
    ):
        if key in benchmark:
            result[key] = _json_value(benchmark[key])

    compact_entries: list[dict[str, Any]] = []
    for entry in _parse_list(_first(benchmark, "entries")):
        if not isinstance(entry, Mapping):
            continue
        compact: dict[str, Any] = {}
        for key in (
            "id",
            "algorithm",
            "status",
            "moleculeId",
            "molecule_id",
            "runId",
            "run_id",
            "seed",
            "seedRoles",
            "seed_roles",
            "errorMessage",
            "error_message",
            "preset",
        ):
            if key in entry:
                compact[key] = _json_value(entry[key])
        compact_entries.append(compact)
    result["entries"] = compact_entries
    return result


def load_folder_source(input_dir: Path) -> SourceBundle:
    input_dir = input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise ExporterError(f"Input folder does not exist or is not a directory: {input_dir}")

    benchmark_path = input_dir / "benchmark.json"
    benchmark = _read_json(benchmark_path) if benchmark_path.is_file() else {}
    if not isinstance(benchmark, Mapping):
        raise ExporterError(f"Expected an object in {benchmark_path}")

    rows_path = _find_folder_rows(input_dir)
    raw_rows = (
        _submission_rows(rows_path, benchmark)
        if rows_path.name == "submission.json"
        else _read_rows_file(rows_path)
    )
    rows: list[dict[str, Any]] = []
    runtime_sources: Counter[str] = Counter()
    for index, raw_row in enumerate(raw_rows):
        normalized, runtime_source = normalize_folder_row(raw_row, benchmark=benchmark, index=index)
        rows.append(normalized)
        if runtime_source:
            runtime_sources[runtime_source] += 1

    rows.sort(key=_row_sort_key)
    source_id = _text(_first(benchmark, "id")) or str(input_dir)
    return SourceBundle(
        benchmark=dict(benchmark),
        rows=rows,
        source_type="folder",
        source_id=source_id,
        runtime_sources=runtime_sources,
    )


class QssApiClient:
    """Small JSON client for the read/write QSS API endpoints used here."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener or urlopen

    def request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            response = self._opener(request, timeout=self.timeout)
            raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ExporterError(f"QSS API {method} {path} returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise ExporterError(f"QSS API {method} {path} is unavailable: {exc.reason}") from exc
        except OSError as exc:
            raise ExporterError(f"QSS API {method} {path} failed: {exc}") from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExporterError(f"QSS API {method} {path} returned invalid JSON") from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: Mapping[str, Any]) -> Any:
        return self.request("POST", path, payload)

    def patch(self, path: str, payload: Mapping[str, Any]) -> Any:
        return self.request("PATCH", path, payload)


def _api_entries(benchmark: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries = _first(benchmark, "entries")
    if entries is None:
        return []
    if not isinstance(entries, list) or not all(isinstance(item, Mapping) for item in entries):
        raise ExporterError("Saved benchmark entries must be a list of objects")
    return [dict(item) for item in entries]


def load_api_source(
    benchmark_id: str,
    *,
    base_url: str,
    client: QssApiClient | None = None,
    include_raw: bool = False,
) -> SourceBundle:
    api = client or QssApiClient(base_url)
    raw_benchmark = api.get(f"/api/benchmarks/{benchmark_id}")
    if not isinstance(raw_benchmark, Mapping):
        raise ExporterError("Benchmark API response must be an object")
    benchmark = dict(raw_benchmark)
    rows: list[dict[str, Any]] = []
    raw_runs: dict[str, dict[str, Any]] = {}
    runtime_sources: Counter[str] = Counter()

    for index, entry in enumerate(_api_entries(benchmark)):
        raw_run_id = _first(entry, "runId", "run_id")
        run_export: dict[str, Any] | None = None
        if _text(raw_run_id):
            run_export_value = api.get(f"/api/runs/{_text(raw_run_id)}/export")
            if not isinstance(run_export_value, Mapping):
                raise ExporterError(f"Run export for entry {index} is not an object")
            run_export = dict(run_export_value)
            if include_raw:
                raw_runs[str(raw_run_id)] = run_export

        normalized, runtime_source = normalize_api_row(
            benchmark=benchmark,
            entry=entry,
            run_export=run_export,
        )
        if normalized["entry_id"] == "entry-unknown":
            normalized["entry_id"] = f"entry:{index:04d}"
        rows.append(normalized)
        if runtime_source:
            runtime_sources[runtime_source] += 1

    rows.sort(key=_row_sort_key)
    return SourceBundle(
        benchmark=benchmark,
        rows=rows,
        source_type="api",
        source_id=str(benchmark_id),
        runtime_sources=runtime_sources,
        raw_benchmark=benchmark if include_raw else None,
        raw_runs=raw_runs,
    )


def _row_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, int, str]:
    seed = _integer(row.get("seed"))
    return (
        str(row.get("entry_id") or ""),
        str(row.get("molecule") or ""),
        str(row.get("algorithm") or ""),
        seed if seed is not None else -1,
        str(row.get("run_id") or ""),
    )


def source_signature(rows: Iterable[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        [{key: row.get(key) for key in CANONICAL_FIELDS} for row in rows],
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _successful_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if _benchmark_row_is_eligible(row)
        and _number(row.get("absolute_error")) is not None
    ]


def _benchmark_row_is_eligible(row: Mapping[str, Any]) -> bool:
    """Return whether a row may contribute to benchmark comparisons."""
    explicit = row.get("benchmark_eligible")
    if isinstance(explicit, bool):
        return explicit
    if str(row.get("status") or "").lower() not in SUCCESS_STATUSES:
        return False
    if row.get("reported_energy_is_valid") is False:
        return False
    if row.get("projected_solve_is_diagnostic") is True:
        return False
    if row.get("scientific_converged") is False or row.get("converged") is False:
        return False
    return True


def _group_summary(rows: list[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "UNKNOWN")].append(row)

    summaries: list[dict[str, Any]] = []
    for group, group_rows in sorted(groups.items()):
        successful = _successful_rows(group_rows)
        errors = [float(row["absolute_error"]) for row in successful if row.get("absolute_error") is not None]
        runtimes = [
            float(row["runtime_seconds"])
            for row in successful
            if _number(row.get("runtime_seconds")) is not None
        ]
        convergence = [
            bool(row["converged"])
            for row in successful
            if isinstance(row.get("converged"), bool)
        ]
        summaries.append(
            {
                key: group,
                "run_count": len(group_rows),
                "successful_count": len(successful),
                "failed_or_incomplete_count": len(group_rows) - len(successful),
                "mean_absolute_error": statistics.mean(errors) if errors else None,
                "median_absolute_error": statistics.median(errors) if errors else None,
                "mean_runtime_seconds": statistics.mean(runtimes) if runtimes else None,
                "convergence_rate": statistics.mean(convergence) if convergence else None,
            }
        )
    return summaries


def summarize_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Build compact summaries with explicit valid-value denominators."""

    successful = _successful_rows(rows)
    by_algorithm = _group_summary(rows, "algorithm")
    by_molecule = _group_summary(rows, "molecule")
    by_algorithm_path = _group_summary(
        [
            dict(row, algorithm_path=_algorithm_path_label(row))
            for row in rows
        ],
        "algorithm_path",
    )
    best: list[dict[str, Any]] = []
    for molecule, molecule_rows in sorted(
        itertools_group(rows, "molecule"), key=lambda item: item[0]
    ):
        candidates = [
            item
            for item in _group_summary(molecule_rows, "algorithm")
            if item["mean_absolute_error"] is not None
        ]
        if candidates:
            winner = min(candidates, key=lambda item: float(item["mean_absolute_error"]))
            best.append(
                {
                    "molecule": molecule,
                    "algorithm": winner["algorithm"],
                    "mean_absolute_error": winner["mean_absolute_error"],
                    "successful_count": winner["successful_count"],
                    "reason": None,
                }
            )
        else:
            best.append(
                {
                    "molecule": molecule,
                    "algorithm": None,
                    "mean_absolute_error": None,
                    "successful_count": 0,
                    "reason": "no valid successful energy errors",
                }
            )

    status_counts = Counter(str(row.get("status") or "missing") for row in rows)
    return {
        "row_count": len(rows),
        "successful_result_count": len(successful),
        "status_counts": dict(sorted(status_counts.items())),
        "by_algorithm": by_algorithm,
        "by_algorithm_path": by_algorithm_path,
        "by_molecule": by_molecule,
        "best_algorithm_by_molecule": best,
    }


def _algorithm_path_label(row: Mapping[str, Any]) -> str:
    algorithm = str(row.get("algorithm") or "UNKNOWN")
    path = str(row.get("actual_path_class") or "unknown_path")
    return f"{algorithm} · {path}"


def itertools_group(
    rows: Iterable[Mapping[str, Any]], key: str
) -> list[tuple[str, list[Mapping[str, Any]]]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "UNKNOWN")].append(row)
    return list(groups.items())


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return json.dumps(value, separators=(",", ":"))
    if value is None:
        return ""
    return value


def write_rows_json(rows: list[Mapping[str, Any]], path: Path) -> None:
    path.write_text(
        json.dumps([{key: row.get(key) for key in CANONICAL_FIELDS} for row in rows], indent=2)
        + "\n",
        encoding="utf-8",
    )


def write_rows_csv(rows: list[Mapping[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CANONICAL_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in CANONICAL_FIELDS})


def write_records_csv(records: list[Mapping[str, Any]], path: Path) -> None:
    fieldnames: list[str] = []
    for record in records:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({key: _csv_value(record.get(key)) for key in fieldnames})


def compact_manifest(bundle: SourceBundle, *, files: list[str]) -> dict[str, Any]:
    summary = summarize_rows(bundle.rows)
    source_metadata = {
        "source_type": bundle.source_type,
        "source_id": bundle.source_id,
        "exported_at": datetime.now().astimezone().isoformat(),
        "schema_version": EXPORT_SCHEMA_VERSION,
        "row_count": len(bundle.rows),
        "source_signature": source_signature(bundle.rows),
    }
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "source_type": bundle.source_type,
        "source_id": bundle.source_id,
        "exported_at": source_metadata["exported_at"],
        "source_metadata": source_metadata,
        "row_count": len(bundle.rows),
        "successful_result_count": summary["successful_result_count"],
        "status_counts": summary["status_counts"],
        "runtime_sources": dict(bundle.runtime_sources),
        "source_signature": source_signature(bundle.rows),
        "files": sorted(files),
    }


def write_summary_files(summary: Mapping[str, Any], output_dir: Path) -> None:
    summaries_dir = output_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    (summaries_dir / "summary.json").write_text(
        json.dumps(dict(summary), indent=2) + "\n", encoding="utf-8"
    )
    write_records_csv(summary["by_algorithm"], summaries_dir / "by_algorithm.csv")
    write_records_csv(summary["by_algorithm_path"], summaries_dir / "by_algorithm_path.csv")
    write_records_csv(summary["by_molecule"], summaries_dir / "by_molecule.csv")
    write_records_csv(
        summary["best_algorithm_by_molecule"],
        summaries_dir / "best_algorithm_by_molecule.csv",
    )


__all__ = [
    "CANONICAL_FIELDS",
    "EXPORT_SCHEMA_VERSION",
    "ExporterError",
    "QssApiClient",
    "SourceBundle",
    "compact_manifest",
    "compact_benchmark",
    "load_api_source",
    "load_folder_source",
    "normalize_api_row",
    "normalize_folder_row",
    "source_signature",
    "summarize_rows",
    "write_rows_csv",
    "write_rows_json",
    "write_summary_files",
]
