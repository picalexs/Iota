"""Smart parallel orchestration helpers for benchmark notebooks.

This module keeps notebook cells small while providing:
- resource-aware method scheduling,
- same-basis parallel execution policy,
- clean orchestrator-side progress output,
- shared per-basis append artifacts for batched execution.
"""

from __future__ import annotations

import csv
import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

from quantum_diag.benchmark_matrix import BenchmarkMatrixRunner
from quantum_diag.config import ExperimentSpec
from quantum_diag.results_aggregation import export_csv, export_json, to_dataframe
from quantum_diag.run_benchmark_demo import _build_reference_energy_maps


DEFAULT_METHOD_RESOURCE_COST: dict[str, int] = {
    "SQD": 1,
    "VQE": 2,
    "ADAPT-VQE": 2,
    "SKQD": 3,
    "KQD": 3,
    "QFD": 4,
    "QSE": 4,
}


# Keep a stable superset for CSV append mode.
ROW_FIELDNAMES: list[str] = [
    "basis_alias",
    "basis_set",
    "method",
    "molecule",
    "seed",
    "ansatz_type",
    "optimizer",
    "runtime_measurement_mode",
    "final_energy",
    "reference_energy",
    "energy_error",
    "iterations",
    "wall_time_seconds",
    "algorithm_wall_time_seconds",
    "end_to_end_wall_time_seconds",
    "prewarm_share_seconds",
    "converged",
    "shots_used",
    "convergence_criterion",
    "warnings",
    "warnings_count",
    "warnings_total_count",
    "cobyla_maxfun_adjusted",
    "chemistry_pipeline",
    "num_qubits",
    "hamiltonian_dimension",
    "active_space",
    "error",
    "traceback",
]


def _read_mem_available_gib() -> float | None:
    """Read current MemAvailable from /proc/meminfo in GiB."""
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    mem_kib = float(line.split()[1])
                    return mem_kib / (1024.0 * 1024.0)
    except Exception:
        return None
    return None


def _detect_resource_plan(
    *,
    cpu_fraction: float = 1.0,
    mem_fraction: float = 1.0,
    mem_per_unit_gib: float = 1.0,
) -> dict[str, int | float | None]:
    """Detect host resources and derive scheduling budget.

    cpu_fraction and mem_fraction are in [0.05, 1.0] and define how much of
    host resources can be consumed by the scheduler.
    """
    cpu_count = os.cpu_count() or 4

    # Keep fractions in a safe range to avoid silent misconfiguration.
    cpu_fraction = min(1.0, max(0.05, float(cpu_fraction)))
    mem_fraction = min(1.0, max(0.05, float(mem_fraction)))
    mem_per_unit_gib = max(0.25, float(mem_per_unit_gib))

    mem_available_gib: float | None = _read_mem_available_gib()

    cpu_budget_units = max(1, int(cpu_count * cpu_fraction))
    if mem_available_gib is None:
        mem_budget_units = cpu_budget_units
    else:
        mem_budget_units = max(1, int((mem_available_gib * mem_fraction) // mem_per_unit_gib))

    budget_units = max(1, min(cpu_budget_units, mem_budget_units))

    max_threads = max(1, min(cpu_count, cpu_budget_units, budget_units))
    return {
        "cpu_count": cpu_count,
        "mem_available_gib": mem_available_gib,
        "cpu_fraction": cpu_fraction,
        "mem_fraction": mem_fraction,
        "mem_per_unit_gib": mem_per_unit_gib,
        "cpu_budget_units": cpu_budget_units,
        "mem_budget_units": mem_budget_units,
        "budget_units": budget_units,
        "max_threads": max_threads,
    }


def _json_default(value: Any) -> Any:
    """JSON serializer fallback for benchmark row values."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _format_seconds(seconds: float) -> str:
    """Format seconds into a compact human-readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rem_seconds = seconds % 60
    if minutes < 60:
        return f"{minutes}m{rem_seconds:04.1f}s"
    hours = int(minutes // 60)
    rem_minutes = minutes % 60
    return f"{hours}h{rem_minutes:02d}m"


def _status_header() -> str:
    """Return the one-line header for compact scheduler status rows."""
    return (
        "TIME     | BASIS | EVENT     | METHOD    | COST | BUDGET | RUN | QUEUE | DONE  | "
        "ROWS | OK  | ERR | ELAPSED  | INFO"
    )


def _trim_info(text: str, max_len: int = 64) -> str:
    """Trim info text for compact status rows."""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def _format_err(value: float | None) -> str:
    """Format error values for compact status logging."""
    if value is None:
        return "n/a"
    return f"{value:.2e}"


def _coerce_bool(value: Any) -> bool | None:
    """Best-effort conversion of benchmark converged field to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _summarize_method_rows(method_rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    """Build compact method-level summary metrics for status rows."""
    success_rows = [row for row in method_rows if not row.get("error")]
    error_rows = len(method_rows) - len(success_rows)

    energy_errors: list[float] = []
    runtimes: list[float] = []
    converged_flags: list[bool] = []

    for row in success_rows:
        err_val = row.get("energy_error")
        if isinstance(err_val, (int, float)):
            energy_errors.append(float(err_val))

        runtime_val = row.get("algorithm_wall_time_seconds")
        if not isinstance(runtime_val, (int, float)):
            runtime_val = row.get("wall_time_seconds")
        if isinstance(runtime_val, (int, float)):
            runtimes.append(float(runtime_val))

        converged = _coerce_bool(row.get("converged"))
        if converged is not None:
            converged_flags.append(converged)

    mean_error = sum(energy_errors) / len(energy_errors) if energy_errors else None
    min_error = min(energy_errors) if energy_errors else None
    max_error = max(energy_errors) if energy_errors else None
    mean_runtime = sum(runtimes) / len(runtimes) if runtimes else None
    conv_rate = (
        (sum(1 for flag in converged_flags if flag) / len(converged_flags))
        if converged_flags
        else None
    )

    return {
        "rows": len(method_rows),
        "ok": len(success_rows),
        "err": error_rows,
        "mean_error": mean_error,
        "min_error": min_error,
        "max_error": max_error,
        "mean_runtime": mean_runtime,
        "convergence_rate": conv_rate,
    }


def _print_status_row(
    *,
    basis: str,
    event: str,
    method: str = "-",
    cost: str = "-",
    budget: str = "-",
    running: str = "-",
    queued: str = "-",
    done: str = "-",
    rows: str = "-",
    ok: str = "-",
    err: str = "-",
    elapsed: str = "-",
    info: str = "",
) -> None:
    """Print one compact status row with consistent columns."""
    timestamp = time.strftime("%H:%M:%S")
    info_text = _trim_info(info)
    print(
        f"{timestamp:<8} | {basis:<5} | {event:<9} | {method:<9} | "
        f"{cost:>4} | {budget:>6} | {running:>3} | {queued:>5} | {done:>5} | "
        f"{rows:>4} | {ok:>3} | {err:>3} | {elapsed:>8} | {info_text}",
        flush=True,
    )


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append rows as JSON lines into a single shared file."""
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=_json_default) + "\n")


def _append_csv(path: Path, rows: list[dict[str, Any]], write_header: bool) -> bool:
    """Append rows into a single shared CSV file with stable fieldnames."""
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=ROW_FIELDNAMES,
            extrasaction="ignore",
        )
        if write_header:
            writer.writeheader()

        for row in rows:
            normalized: dict[str, Any] = {}
            for key in ROW_FIELDNAMES:
                val = row.get(key)
                if isinstance(val, (list, dict, tuple)):
                    normalized[key] = json.dumps(val, default=_json_default)
                else:
                    normalized[key] = val
            writer.writerow(normalized)

    return False


def _build_base_spec(
    *,
    molecules: list[str],
    seeds: list[int],
    ansatz_types: list[str],
    optimizers: list[str],
    max_iterations: int,
    basis_set: str,
) -> ExperimentSpec:
    """Build a base experiment spec used for matrix runner construction."""
    return ExperimentSpec(
        molecule_name=molecules[0],
        basis_set=basis_set,
        method="VQE",
        ansatz_type=ansatz_types[0],
        optimizer=optimizers[0],
        max_iterations=max_iterations,
        shots=1024,
        seed=seeds[0],
        backend_name="qasm_simulator",
    )


def _run_single_method_batch(
    *,
    basis_alias: str,
    basis_set: str,
    method: str,
    molecules: list[str],
    seeds: list[int],
    ansatz_types: list[str],
    optimizers: list[str],
    max_iterations: int,
    progress: bool,
    progress_every: int,
) -> tuple[str, list[dict[str, Any]], float]:
    """Run one method batch for a given basis alias."""
    reference_energy_map, _ = _build_reference_energy_maps(
        molecules=molecules,
        basis_set=basis_set,
    )
    base_spec = _build_base_spec(
        molecules=molecules,
        seeds=seeds,
        ansatz_types=ansatz_types,
        optimizers=optimizers,
        max_iterations=max_iterations,
        basis_set=basis_set,
    )

    runner = BenchmarkMatrixRunner(base_spec, reference_energy_map)

    t0 = time.perf_counter()
    rows = runner.run_matrix(
        methods=[method],
        molecules=molecules,
        seeds=seeds,
        ansatz_types=ansatz_types,
        optimizers=optimizers,
        max_iterations=max_iterations,
        progress=progress,
        progress_every=max(1, progress_every),
    )
    elapsed = max(0.0, time.perf_counter() - t0)

    for row in rows:
        row["basis_alias"] = basis_alias
        row["basis_set"] = basis_set

    return method, rows, elapsed


def _run_basis_serial(
    *,
    run_output_dir: Path,
    basis_alias: str,
    basis_set: str,
    methods: list[str],
    molecules: list[str],
    seeds: list[int],
    ansatz_types: list[str],
    optimizers: list[str],
    max_iterations: int,
    progress_every: int,
    heartbeat_seconds: float,
    worker_progress: bool,
) -> list[dict[str, Any]]:
    """Run all methods for one basis alias sequentially (no parallel workers)."""
    basis_output_dir = run_output_dir / f"basis_{basis_alias}"
    basis_output_dir.mkdir(parents=True, exist_ok=True)

    shared_jsonl = basis_output_dir / "benchmark_rows_partial.jsonl"
    shared_csv = basis_output_dir / "benchmark_rows_partial.csv"
    shared_jsonl.write_text("", encoding="utf-8")
    shared_csv.write_text("", encoding="utf-8")

    basis_rows: list[dict[str, Any]] = []
    write_csv_header = True
    total_methods = len(methods)

    print("\n" + "-" * 140)
    print(_status_header(), flush=True)
    _print_status_row(
        basis=basis_alias,
        event="BASIS",
        method="-",
        cost="-",
        budget="0/1",
        running="0",
        queued=str(total_methods),
        done=f"0/{total_methods}",
        rows="0",
        ok="0",
        err="0",
        elapsed="0.0s",
        info=f"start basis_set={basis_set} (serial)",
    )

    basis_t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=1) as pool:
        for idx, method in enumerate(methods):
            _print_status_row(
                basis=basis_alias,
                event="SUBMIT",
                method=method,
                cost="1",
                budget="1/1",
                running="1",
                queued=str(total_methods - idx - 1),
                done=f"{idx}/{total_methods}",
                rows=str(len(basis_rows)),
                info="scheduled (serial)",
            )

            started_at = time.perf_counter()
            future = pool.submit(
                _run_single_method_batch,
                basis_alias=basis_alias,
                basis_set=basis_set,
                method=method,
                molecules=molecules,
                seeds=seeds,
                ansatz_types=ansatz_types,
                optimizers=optimizers,
                max_iterations=max_iterations,
                progress=worker_progress,
                progress_every=progress_every,
            )

            while True:
                done_set, _ = wait(
                    {future},
                    timeout=max(1.0, heartbeat_seconds),
                    return_when=FIRST_COMPLETED,
                )
                if done_set:
                    break

                _print_status_row(
                    basis=basis_alias,
                    event="HEARTBEAT",
                    method=method,
                    cost="1",
                    budget="1/1",
                    running="1",
                    queued=str(total_methods - idx - 1),
                    done=f"{idx}/{total_methods}",
                    rows=str(len(basis_rows)),
                    elapsed=_format_seconds(max(0.0, time.perf_counter() - started_at)),
                    info="running (serial)",
                )

            method_name, method_rows, elapsed = future.result()

            basis_rows.extend(method_rows)
            _append_jsonl(shared_jsonl, method_rows)
            write_csv_header = _append_csv(shared_csv, method_rows, write_csv_header)

            method_summary = _summarize_method_rows(method_rows)
            success_count = int(method_summary["ok"] or 0)
            error_count = int(method_summary["err"] or 0)
            conv_rate_val = method_summary["convergence_rate"]
            if isinstance(conv_rate_val, (int, float)):
                conv_str = f"{100.0 * float(conv_rate_val):.0f}%"
            else:
                conv_str = "n/a"

            mean_rt_val = method_summary["mean_runtime"]
            mean_rt_str = _format_seconds(float(mean_rt_val)) if isinstance(mean_rt_val, (int, float)) else "n/a"

            info = (
                f"err(mean/best/worst)={_format_err(method_summary['mean_error'])}/"
                f"{_format_err(method_summary['min_error'])}/"
                f"{_format_err(method_summary['max_error'])} "
                f"conv={conv_str} avg_rt={mean_rt_str}"
            )

            _print_status_row(
                basis=basis_alias,
                event="DONE",
                method=method_name,
                cost="-",
                budget="0/1",
                running="0",
                queued=str(total_methods - idx - 1),
                done=f"{idx + 1}/{total_methods}",
                rows=str(len(basis_rows)),
                ok=str(success_count),
                err=str(error_count),
                elapsed=_format_seconds(elapsed),
                info=info,
            )

    basis_elapsed = max(0.0, time.perf_counter() - basis_t0)
    _print_status_row(
        basis=basis_alias,
        event="COMPLETE",
        method="-",
        cost="-",
        budget="0/1",
        running="0",
        queued="0",
        done=f"{total_methods}/{total_methods}",
        rows=str(len(basis_rows)),
        elapsed=_format_seconds(basis_elapsed),
        info="basis done",
    )

    method_order = {name: idx for idx, name in enumerate(methods)}
    basis_rows.sort(
        key=lambda r: (
            method_order.get(str(r.get("method", "")), 999),
            str(r.get("molecule", "")),
            int(r.get("seed", 0)) if isinstance(r.get("seed", None), int) else 0,
            str(r.get("ansatz_type", "")),
            str(r.get("optimizer", "")),
        )
    )

    export_json(basis_rows, str(basis_output_dir / "benchmark_rows_basis.json"))
    export_csv(to_dataframe(basis_rows), str(basis_output_dir / "benchmark_rows_basis.csv"))

    runtime_metadata = {
        "runtime_measurement_mode": "algorithm-primary-with-end-to-end-secondary",
        "algorithm_runtime_total_seconds": float(
            sum(float(r.get("algorithm_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in basis_rows if not r.get("error"))
        ),
        "end_to_end_runtime_total_seconds": float(
            sum(float(r.get("end_to_end_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in basis_rows if not r.get("error"))
        ),
    }
    (basis_output_dir / "runtime_metadata_basis.json").write_text(
        json.dumps(runtime_metadata, indent=2),
        encoding="utf-8",
    )

    return basis_rows


def run_serial_basis_matrix(
    *,
    run_output_dir: str | Path,
    basis_alias_to_pyscf: dict[str, str],
    basis_aliases: list[str],
    methods: list[str],
    molecules: list[str],
    seeds: list[int],
    ansatz_types: list[str],
    optimizers: list[str],
    max_iterations: int,
    progress_every: int = 2,
    heartbeat_seconds: float = 10.0,
    worker_progress: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Run basis sweeps in strict serial mode (one method at a time)."""
    output_dir = Path(run_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    runs_per_method = len(molecules) * len(seeds) * len(ansatz_types) * len(optimizers)
    est_total_rows = runs_per_method * len(methods) * len(basis_aliases)

    print("\n" + "-" * 140)
    print(_status_header(), flush=True)
    _print_status_row(
        basis="ALL",
        event="PLAN",
        method="-",
        cost="-",
        budget="0/1",
        running="0",
        queued=str(len(methods) * len(basis_aliases)),
        done=f"0/{len(methods) * len(basis_aliases)}",
        rows="0",
        elapsed="0.0s",
        info=f"execution_mode=serial est_rows={est_total_rows}",
    )

    rows_by_alias: dict[str, list[dict[str, Any]]] = {}
    for alias in basis_aliases:
        basis_set = basis_alias_to_pyscf[alias]
        rows_by_alias[alias] = _run_basis_serial(
            run_output_dir=output_dir,
            basis_alias=alias,
            basis_set=basis_set,
            methods=methods,
            molecules=molecules,
            seeds=seeds,
            ansatz_types=ansatz_types,
            optimizers=optimizers,
            max_iterations=max_iterations,
            progress_every=progress_every,
            heartbeat_seconds=heartbeat_seconds,
            worker_progress=worker_progress,
        )

    all_rows: list[dict[str, Any]] = []
    for alias in basis_aliases:
        all_rows.extend(rows_by_alias[alias])

    export_json(all_rows, str(output_dir / "benchmark_rows_parallel.json"))
    export_csv(to_dataframe(all_rows), str(output_dir / "benchmark_rows_parallel.csv"))

    runtime_metadata = {
        "runtime_measurement_mode": "algorithm-primary-with-end-to-end-secondary",
        "algorithm_runtime_total_seconds": float(
            sum(float(r.get("algorithm_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in all_rows if not r.get("error"))
        ),
        "end_to_end_runtime_total_seconds": float(
            sum(float(r.get("end_to_end_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in all_rows if not r.get("error"))
        ),
        "execution_mode": "serial",
        "max_threads": 1,
    }
    (output_dir / "runtime_metadata_parallel.json").write_text(
        json.dumps(runtime_metadata, indent=2),
        encoding="utf-8",
    )

    return all_rows, rows_by_alias, runtime_metadata


def _run_basis_resource_aware(
    *,
    run_output_dir: Path,
    basis_alias: str,
    basis_set: str,
    methods: list[str],
    molecules: list[str],
    seeds: list[int],
    ansatz_types: list[str],
    optimizers: list[str],
    max_iterations: int,
    method_resource_cost: dict[str, int],
    max_threads: int,
    resource_budget_units: int,
    mem_per_unit_gib: float,
    dynamic_memory_guard: bool,
    min_free_memory_gib: float,
    progress_every: int,
    heartbeat_seconds: float,
    worker_progress: bool,
) -> list[dict[str, Any]]:
    """Run all methods for one basis alias with smart resource gating."""
    basis_output_dir = run_output_dir / f"basis_{basis_alias}"
    basis_output_dir.mkdir(parents=True, exist_ok=True)

    shared_jsonl = basis_output_dir / "benchmark_rows_partial.jsonl"
    shared_csv = basis_output_dir / "benchmark_rows_partial.csv"
    shared_jsonl.write_text("", encoding="utf-8")
    shared_csv.write_text("", encoding="utf-8")

    basis_rows: list[dict[str, Any]] = []
    pending_methods = list(methods)
    write_csv_header = True
    total_methods = len(methods)
    completed_methods = 0

    print("\n" + "-" * 140)
    print(_status_header(), flush=True)
    _print_status_row(
        basis=basis_alias,
        event="BASIS",
        method="-",
        cost="-",
        budget=f"0/{resource_budget_units}",
        running="0",
        queued=str(len(pending_methods)),
        done=f"0/{total_methods}",
        rows="0",
        ok="0",
        err="0",
        elapsed="0.0s",
        info=f"start basis_set={basis_set}",
    )

    used_units = 0
    in_flight: dict[Any, tuple[str, int, float]] = {}
    basis_t0 = time.perf_counter()
    effective_mem_per_unit_gib = float(mem_per_unit_gib)
    memgate_stall_started_at: float | None = None
    memgate_relax_after_seconds = 120.0
    mem_per_unit_floor_gib = 0.5

    with ThreadPoolExecutor(max_workers=max_threads) as pool:
        while pending_methods or in_flight:
            submitted = False
            memory_gated = False
            lowest_blocked_cost: int | None = None
            last_mem_available_gib: float | None = None

            i = 0
            while i < len(pending_methods):
                method = pending_methods[i]
                cost = int(method_resource_cost.get(method, 2))

                if in_flight and used_units + cost > resource_budget_units:
                    i += 1
                    continue

                if dynamic_memory_guard:
                    mem_available_now = _read_mem_available_gib()
                    last_mem_available_gib = mem_available_now
                    if mem_available_now is not None:
                        projected_after_submit = mem_available_now - (float(cost) * effective_mem_per_unit_gib)
                        if projected_after_submit < min_free_memory_gib:
                            memory_gated = True
                            if lowest_blocked_cost is None or cost < lowest_blocked_cost:
                                lowest_blocked_cost = cost
                            i += 1
                            continue

                fut = pool.submit(
                    _run_single_method_batch,
                    basis_alias=basis_alias,
                    basis_set=basis_set,
                    method=method,
                    molecules=molecules,
                    seeds=seeds,
                    ansatz_types=ansatz_types,
                    optimizers=optimizers,
                    max_iterations=max_iterations,
                    progress=worker_progress,
                    progress_every=progress_every,
                )
                in_flight[fut] = (method, cost, time.perf_counter())
                used_units += cost
                pending_methods.pop(i)
                submitted = True

                _print_status_row(
                    basis=basis_alias,
                    event="SUBMIT",
                    method=method,
                    cost=str(cost),
                    budget=f"{used_units}/{resource_budget_units}",
                    running=str(len(in_flight)),
                    queued=str(len(pending_methods)),
                    done=f"{completed_methods}/{total_methods}",
                    rows=str(len(basis_rows)),
                    info="scheduled",
                )
                memgate_stall_started_at = None

            if not in_flight and pending_methods and not submitted:
                if dynamic_memory_guard and memory_gated:
                    now = time.perf_counter()
                    if memgate_stall_started_at is None:
                        memgate_stall_started_at = now

                    mem_now = _read_mem_available_gib()
                    if mem_now is not None:
                        last_mem_available_gib = mem_now

                    # If memory gate blocks all pending methods for too long,
                    # relax the per-unit estimate toward what current headroom can actually sustain.
                    stall_seconds = max(0.0, now - memgate_stall_started_at)
                    if (
                        stall_seconds >= memgate_relax_after_seconds
                        and last_mem_available_gib is not None
                        and pending_methods
                    ):
                        min_pending_cost = min(int(method_resource_cost.get(m, 2)) for m in pending_methods)
                        headroom = max(0.0, float(last_mem_available_gib) - float(min_free_memory_gib))
                        if min_pending_cost > 0 and headroom > 0.0:
                            target_mem_unit = max(
                                mem_per_unit_floor_gib,
                                0.95 * (headroom / float(min_pending_cost)),
                            )
                            if target_mem_unit < effective_mem_per_unit_gib:
                                old_mem_unit = effective_mem_per_unit_gib
                                effective_mem_per_unit_gib = target_mem_unit
                                _print_status_row(
                                    basis=basis_alias,
                                    event="MEMRELAX",
                                    method="-",
                                    cost="-",
                                    budget=f"{used_units}/{resource_budget_units}",
                                    running=str(len(in_flight)),
                                    queued=str(len(pending_methods)),
                                    done=f"{completed_methods}/{total_methods}",
                                    rows=str(len(basis_rows)),
                                    elapsed=_format_seconds(max(0.0, now - basis_t0)),
                                    info=(
                                        f"mem_unit {old_mem_unit:.2f}->"
                                        f"{effective_mem_per_unit_gib:.2f}GiB after "
                                        f"stall={_format_seconds(stall_seconds)}"
                                    ),
                                )
                                memgate_stall_started_at = now

                    required_for_lowest = (
                        float(lowest_blocked_cost) * effective_mem_per_unit_gib
                        if lowest_blocked_cost is not None
                        else 0.0
                    )
                    info = (
                        f"mem gate: avail={last_mem_available_gib:.2f}GiB "
                        f"need>={required_for_lowest + min_free_memory_gib:.2f}GiB "
                        f"free_floor={min_free_memory_gib:.2f}GiB"
                        if last_mem_available_gib is not None
                        else "mem gate: MemAvailable unavailable"
                    )
                    _print_status_row(
                        basis=basis_alias,
                        event="MEMGATE",
                        method="-",
                        cost="-",
                        budget=f"{used_units}/{resource_budget_units}",
                        running=str(len(in_flight)),
                        queued=str(len(pending_methods)),
                        done=f"{completed_methods}/{total_methods}",
                        rows=str(len(basis_rows)),
                        elapsed=_format_seconds(max(0.0, now - basis_t0)),
                        info=info,
                    )
                    time.sleep(min(max(1.0, heartbeat_seconds / 2.0), 5.0))
                    continue

                method = pending_methods.pop(0)
                cost = int(method_resource_cost.get(method, 2))
                fut = pool.submit(
                    _run_single_method_batch,
                    basis_alias=basis_alias,
                    basis_set=basis_set,
                    method=method,
                    molecules=molecules,
                    seeds=seeds,
                    ansatz_types=ansatz_types,
                    optimizers=optimizers,
                    max_iterations=max_iterations,
                    progress=worker_progress,
                    progress_every=progress_every,
                )
                in_flight[fut] = (method, cost, time.perf_counter())
                used_units += cost
                _print_status_row(
                    basis=basis_alias,
                    event="FORCE",
                    method=method,
                    cost=str(cost),
                    budget=f"{used_units}/{resource_budget_units}",
                    running=str(len(in_flight)),
                    queued=str(len(pending_methods)),
                    done=f"{completed_methods}/{total_methods}",
                    rows=str(len(basis_rows)),
                    info="forced submit",
                )

            if in_flight:
                done_set, _ = wait(
                    set(in_flight.keys()),
                    timeout=heartbeat_seconds,
                    return_when=FIRST_COMPLETED,
                )

                if not done_set:
                    now = time.perf_counter()
                    active_status: list[str] = []
                    for _, (method_name, method_cost, started_at) in in_flight.items():
                        active_status.append(
                            f"{method_name}(cost={method_cost},elapsed={_format_seconds(now-started_at)})"
                        )
                    _print_status_row(
                        basis=basis_alias,
                        event="HEARTBEAT",
                        method="-",
                        cost="-",
                        budget=f"{used_units}/{resource_budget_units}",
                        running=str(len(in_flight)),
                        queued=str(len(pending_methods)),
                        done=f"{completed_methods}/{total_methods}",
                        rows=str(len(basis_rows)),
                        elapsed=_format_seconds(max(0.0, now - basis_t0)),
                        info="; ".join(active_status),
                    )
                    continue

                for fut in done_set:
                    _, cost, _ = in_flight.pop(fut)
                    used_units -= cost

                    method_name, method_rows, elapsed = fut.result()
                    basis_rows.extend(method_rows)
                    completed_methods += 1
                    _append_jsonl(shared_jsonl, method_rows)
                    write_csv_header = _append_csv(shared_csv, method_rows, write_csv_header)

                    method_summary = _summarize_method_rows(method_rows)
                    success_count = int(method_summary["ok"] or 0)
                    error_count = int(method_summary["err"] or 0)

                    conv_rate_val = method_summary["convergence_rate"]
                    if isinstance(conv_rate_val, (int, float)):
                        conv_str = f"{100.0 * float(conv_rate_val):.0f}%"
                    else:
                        conv_str = "n/a"

                    mean_rt_val = method_summary["mean_runtime"]
                    mean_rt_str = _format_seconds(float(mean_rt_val)) if isinstance(mean_rt_val, (int, float)) else "n/a"

                    info = (
                        f"err(mean/best/worst)={_format_err(method_summary['mean_error'])}/"
                        f"{_format_err(method_summary['min_error'])}/"
                        f"{_format_err(method_summary['max_error'])} "
                        f"conv={conv_str} avg_rt={mean_rt_str}"
                    )

                    _print_status_row(
                        basis=basis_alias,
                        event="DONE",
                        method=method_name,
                        cost="-",
                        budget=f"{used_units}/{resource_budget_units}",
                        running=str(len(in_flight)),
                        queued=str(len(pending_methods)),
                        done=f"{completed_methods}/{total_methods}",
                        rows=str(len(basis_rows)),
                        ok=str(success_count),
                        err=str(error_count),
                        elapsed=_format_seconds(elapsed),
                        info=info,
                    )

    basis_elapsed = max(0.0, time.perf_counter() - basis_t0)
    _print_status_row(
        basis=basis_alias,
        event="COMPLETE",
        method="-",
        cost="-",
        budget=f"0/{resource_budget_units}",
        running="0",
        queued="0",
        done=f"{completed_methods}/{total_methods}",
        rows=str(len(basis_rows)),
        elapsed=_format_seconds(basis_elapsed),
        info="basis done",
    )

    method_order = {name: idx for idx, name in enumerate(methods)}
    basis_rows.sort(
        key=lambda r: (
            method_order.get(str(r.get("method", "")), 999),
            str(r.get("molecule", "")),
            int(r.get("seed", 0)) if isinstance(r.get("seed", None), int) else 0,
            str(r.get("ansatz_type", "")),
            str(r.get("optimizer", "")),
        )
    )

    # Final consolidated per-basis artifacts.
    export_json(basis_rows, str(basis_output_dir / "benchmark_rows_basis.json"))
    export_csv(to_dataframe(basis_rows), str(basis_output_dir / "benchmark_rows_basis.csv"))

    runtime_metadata = {
        "runtime_measurement_mode": "algorithm-primary-with-end-to-end-secondary",
        "algorithm_runtime_total_seconds": float(
            sum(float(r.get("algorithm_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in basis_rows if not r.get("error"))
        ),
        "end_to_end_runtime_total_seconds": float(
            sum(float(r.get("end_to_end_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in basis_rows if not r.get("error"))
        ),
    }
    (basis_output_dir / "runtime_metadata_basis.json").write_text(
        json.dumps(runtime_metadata, indent=2),
        encoding="utf-8",
    )

    return basis_rows


def run_basis_matrix(
    *,
    run_output_dir: str | Path,
    basis_alias_to_pyscf: dict[str, str],
    basis_aliases: list[str],
    methods: list[str],
    molecules: list[str],
    seeds: list[int],
    ansatz_types: list[str],
    optimizers: list[str],
    max_iterations: int,
    method_resource_cost: dict[str, int] | None = None,
    progress_every: int = 2,
    heartbeat_seconds: float = 20.0,
    worker_progress: bool = False,
    resource_cpu_fraction: float = 1.0,
    resource_mem_fraction: float = 1.0,
    resource_mem_per_unit_gib: float = 1.0,
    dynamic_memory_guard: bool = True,
    min_free_memory_gib: float | None = None,
    force_serial: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Run basis sweeps with adaptive scheduling.

    Returns:
        (all_rows, rows_by_alias, scheduler_metadata)
    """
    if force_serial:
        return run_serial_basis_matrix(
            run_output_dir=run_output_dir,
            basis_alias_to_pyscf=basis_alias_to_pyscf,
            basis_aliases=basis_aliases,
            methods=methods,
            molecules=molecules,
            seeds=seeds,
            ansatz_types=ansatz_types,
            optimizers=optimizers,
            max_iterations=max_iterations,
            progress_every=progress_every,
            heartbeat_seconds=heartbeat_seconds,
            worker_progress=worker_progress,
        )

    output_dir = Path(run_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    costs = dict(DEFAULT_METHOD_RESOURCE_COST)
    if method_resource_cost:
        costs.update(method_resource_cost)

    resource_plan = _detect_resource_plan(
        cpu_fraction=resource_cpu_fraction,
        mem_fraction=resource_mem_fraction,
        mem_per_unit_gib=resource_mem_per_unit_gib,
    )
    budget_units_raw = resource_plan.get("budget_units")
    max_threads_raw = resource_plan.get("max_threads")
    resource_budget_units = (
        int(budget_units_raw) if isinstance(budget_units_raw, (int, float)) else 2
    )
    max_threads = int(max_threads_raw) if isinstance(max_threads_raw, (int, float)) else 1
    min_free_memory_gib_effective = (
        float(min_free_memory_gib)
        if min_free_memory_gib is not None
        else max(1.5, float(resource_plan.get("mem_per_unit_gib") or 1.0))
    )

    runs_per_method = len(molecules) * len(seeds) * len(ansatz_types) * len(optimizers)
    est_total_rows = runs_per_method * len(methods) * len(basis_aliases)

    print("\n" + "-" * 140)
    print(_status_header(), flush=True)
    _print_status_row(
        basis="ALL",
        event="PLAN",
        method="-",
        cost="-",
        budget=f"0/{resource_budget_units}",
        running="0",
        queued=str(len(methods) * len(basis_aliases)),
        done=f"0/{len(methods) * len(basis_aliases)}",
        rows="0",
        elapsed="0.0s",
        info=(
            f"cpu={resource_plan['cpu_count']} mem_gib={resource_plan['mem_available_gib']} "
            f"threads={max_threads} est_rows={est_total_rows}"
        ),
    )
    _print_status_row(
        basis="ALL",
        event="PLAN",
        method="-",
        cost="-",
        budget=f"0/{resource_budget_units}",
        running="0",
        queued=str(len(methods) * len(basis_aliases)),
        done=f"0/{len(methods) * len(basis_aliases)}",
        rows="0",
        elapsed="0.0s",
        info=(
            f"fractions: cpu={resource_plan['cpu_fraction']:.2f} mem={resource_plan['mem_fraction']:.2f} "
            f"mem_unit={resource_plan['mem_per_unit_gib']:.2f}GiB"
        ),
    )
    _print_status_row(
        basis="ALL",
        event="PLAN",
        method="-",
        cost="-",
        budget=f"0/{resource_budget_units}",
        running="0",
        queued=str(len(methods) * len(basis_aliases)),
        done=f"0/{len(methods) * len(basis_aliases)}",
        rows="0",
        elapsed="0.0s",
        info=(
            f"dynamic_mem_guard={'on' if dynamic_memory_guard else 'off'} "
            f"min_free_mem={min_free_memory_gib_effective:.2f}GiB"
        ),
    )
    _print_status_row(
        basis="ALL",
        event="PLAN",
        method="-",
        cost="-",
        budget=f"0/{resource_budget_units}",
        running="0",
        queued=str(len(methods) * len(basis_aliases)),
        done=f"0/{len(methods) * len(basis_aliases)}",
        rows="0",
        elapsed="0.0s",
        info=f"execution_mode={'serial' if force_serial else 'parallel'}",
    )
    _print_status_row(
        basis="ALL",
        event="PLAN",
        method="-",
        cost="-",
        budget=f"0/{resource_budget_units}",
        running="0",
        queued=str(len(methods) * len(basis_aliases)),
        done=f"0/{len(methods) * len(basis_aliases)}",
        rows="0",
        elapsed="0.0s",
        info="policy: per-basis execution; shared append files; finalized basis/global exports",
    )

    rows_by_alias: dict[str, list[dict[str, Any]]] = {}
    for alias in basis_aliases:
        basis_set = basis_alias_to_pyscf[alias]
        rows_by_alias[alias] = _run_basis_resource_aware(
            run_output_dir=output_dir,
            basis_alias=alias,
            basis_set=basis_set,
            methods=methods,
            molecules=molecules,
            seeds=seeds,
            ansatz_types=ansatz_types,
            optimizers=optimizers,
            max_iterations=max_iterations,
            method_resource_cost=costs,
            max_threads=max_threads,
            resource_budget_units=resource_budget_units,
            mem_per_unit_gib=float(resource_plan.get("mem_per_unit_gib") or resource_mem_per_unit_gib),
            dynamic_memory_guard=dynamic_memory_guard,
            min_free_memory_gib=min_free_memory_gib_effective,
            progress_every=progress_every,
            heartbeat_seconds=heartbeat_seconds,
            worker_progress=worker_progress,
        )

    all_rows: list[dict[str, Any]] = []
    for alias in basis_aliases:
        all_rows.extend(rows_by_alias[alias])

    export_json(all_rows, str(output_dir / "benchmark_rows_parallel.json"))
    export_csv(to_dataframe(all_rows), str(output_dir / "benchmark_rows_parallel.csv"))

    runtime_metadata = {
        "runtime_measurement_mode": "algorithm-primary-with-end-to-end-secondary",
        "algorithm_runtime_total_seconds": float(
            sum(float(r.get("algorithm_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in all_rows if not r.get("error"))
        ),
        "end_to_end_runtime_total_seconds": float(
            sum(float(r.get("end_to_end_wall_time_seconds") or r.get("wall_time_seconds") or 0.0)
                for r in all_rows if not r.get("error"))
        ),
        "resource_plan": resource_plan,
        "resource_budget_units": resource_budget_units,
        "max_threads": max_threads,
        "dynamic_memory_guard": dynamic_memory_guard,
        "min_free_memory_gib": min_free_memory_gib_effective,
        "force_serial": force_serial,
    }
    (output_dir / "runtime_metadata_parallel.json").write_text(
        json.dumps(runtime_metadata, indent=2),
        encoding="utf-8",
    )

    return all_rows, rows_by_alias, runtime_metadata


def run_parallel_basis_matrix(
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Backward-compatible alias for run_basis_matrix."""
    return run_basis_matrix(**kwargs)
