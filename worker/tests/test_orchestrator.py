"""Focused tests for the ordered worker dispatch and finalization seam."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.types import ChemistryInput
from worker.jobs.execution_context import PreparedRunContext, StartedRunContext
from worker.jobs.orchestrator import dispatch_and_finalize_run


def _contexts() -> tuple[StartedRunContext, PreparedRunContext]:
    started = StartedRunContext(
        expected_generation=2,
        algorithm="vqe",
        mode="easy",
        backend_target="statevector",
        config_snapshot={"algorithm": "vqe"},
        algorithm_config={"max_iterations": 2},
        backend_options_runtime={},
        chemistry_input=ChemistryInput(atoms=["H"]),
        eta_seed_seconds_per_iteration=None,
        eta_seed_confidence=None,
    )
    prepared = PreparedRunContext(
        backend_adapter=object(),
        backend_context=BackendExecutionContext(backend_target="statevector"),
        hamiltonian_bundle=SimpleNamespace(num_qubits=2, metadata={"pipeline": "test"}),
    )
    return started, prepared


def test_orchestrator_keeps_estimate_dispatch_and_finalization_order() -> None:
    started, prepared = _contexts()
    started = started._replace(
        algorithm="kqd",
        backend_target="aer_simulator",
        config_snapshot={"algorithm": "kqd", "noise_profile": None},
        algorithm_config={"algorithm": "kqd", "krylov_dim": 2},
    )
    prepared = prepared._replace(
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            noise_profile=None,
        ),
        hamiltonian_bundle=SimpleNamespace(num_qubits=14, metadata={"pipeline": "test"}),
    )
    session = MagicMock()
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False
    order: list[str] = []
    progress_state: dict[str, object] = {}
    estimate_projected_paths: list[bool | None] = []

    def estimate_total_iterations(*_args: object, **kwargs: object) -> int:
        estimate_projected_paths.append(kwargs.get("projected_branch_path"))
        return 2

    def emit_progress_update(*_: object, **__: object) -> None:
        order.append("progress")

    def dispatch_algorithm(**kwargs: object) -> dict[str, object]:
        order.append("dispatch")
        progress_callback = kwargs["progress_callback"]
        assert callable(progress_callback)
        progress_callback({"iteration": 1})
        return {"raw": True}

    def apply_result_metadata(result: dict[str, object], **_: object) -> None:
        order.append("metadata")
        result["metadata_applied"] = True

    result = dispatch_and_finalize_run(
        run_id_str="run-1",
        started=started,
        prepared=prepared,
        progress_state=progress_state,
        run_wall_start=0.0,
        estimate_total_iterations=estimate_total_iterations,
        emit_progress_update=emit_progress_update,
        build_telemetry_estimate=lambda **_: (
            order.append("estimate") or {"estimated_total_iterations": 2}
        ),
        persist_latest_estimate=lambda *_args: order.append("persist_estimate"),
        insert_run_event=lambda *_args: order.append("event"),
        dispatch_algorithm=dispatch_algorithm,
        pause_after_dispatch=lambda *_args, **_kwargs: order.append("pause_check"),
        normalize_result=lambda *_args: (
            order.append("normalize")
            or {"algorithm": "vqe", "primary_energy": -1.0, "iterations": 1}
        ),
        apply_result_metadata=apply_result_metadata,
        reconcile_reported_iterations=lambda *_args, **_kwargs: order.append("reconcile"),
        uses_branch_matrix_elements=lambda _: order.append("branch_check") or False,
        emit_fallback_completion_progress=lambda *_args, **_kwargs: order.append("fallback"),
        session_factory=lambda: session_context,
        commit_transaction=lambda _: order.append("commit"),
    )

    assert result["metadata_applied"] is True
    assert isinstance(result["runtime_seconds"], float)
    assert result["execution_timing"]["timing_basis"] == (
        "worker_execution_segment_monotonic"
    )
    assert result["execution_timing"]["algorithm_dispatch_seconds"] >= 0.0
    assert result["execution_timing"]["total_wall_seconds"] == result["runtime_seconds"]
    assert result["execution_timing"]["timing_ledger_version"] == 1
    assert result["execution_timing"]["stage_wall_seconds"]["projected_solve"] is None
    assert result["execution_timing"]["worker_wall_seconds"] >= 0.0
    assert result["execution_timing"]["idle_gap_status"] == "unavailable_without_stage_markers"
    assert result["execution_timing"]["unattributed_worker_seconds"] >= 0.0
    assert isinstance(result["run_finished_at"], str)
    assert estimate_projected_paths == [True]
    assert order == [
        "estimate",
        "persist_estimate",
        "event",
        "commit",
        "dispatch",
        "progress",
        "pause_check",
        "normalize",
        "metadata",
        "branch_check",
        "reconcile",
        "fallback",
    ]
    session.commit.assert_not_called()
