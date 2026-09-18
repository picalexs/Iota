"""Unit tests for API-side run estimation heuristics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.models.enums import BackendTarget, RunAlgorithm, RunEventType, RunMode, RunStatus
from app.models.molecule import Molecule
from app.models.run import Run
from app.models.run_event import RunEvent
from app.models.run_result import RunResult
from app.schemas.run import RunCreate
from app.services.easy_mode_presets import EASY_MODE_CATALOG_VERSION
from app.services.estimation.history import history_runs_statement, history_runtime_seconds
from app.services.run_estimation import (
    build_initial_estimate_for_persisted_run,
    build_initial_estimate_for_run_request,
    estimate_total_iterations,
    seed_initial_estimate_for_run,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, sessionmaker


def _h2_molecule() -> Molecule:
    return Molecule(
        name="H2",
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.7414},
        ],
        charge=0,
        multiplicity=1,
        active_space={"n_electrons": 2, "n_orbitals": 2},
    )


def test_history_runtime_ignores_lifecycle_timestamp_fallback() -> None:
    run = Run(
        run_metadata={
            "run_started_at": "2026-09-10T10:00:00Z",
            "run_finished_at": "2026-09-10T12:00:00Z",
        }
    )

    assert history_runtime_seconds(run) is None


def test_history_runtime_uses_persisted_non_negative_worker_runtime() -> None:
    run = Run(run_metadata={"runtime_seconds": 0.0})

    assert history_runtime_seconds(run) == 0.0


def test_vqe_spsa_estimate_counts_objective_evaluations() -> None:
    iterations = estimate_total_iterations(
        algorithm=RunAlgorithm.VQE,
        config_payload={
            "algorithm": "vqe",
            "optimizer_name": "SPSA",
            "max_iterations": 12,
        },
    )

    assert iterations == 40


def test_vqe_lbfgsb_estimate_counts_function_evaluations() -> None:
    iterations = estimate_total_iterations(
        algorithm=RunAlgorithm.VQE,
        config_payload={
            "algorithm": "vqe",
            "optimizer_name": "L_BFGS_B",
            "max_iterations": 100,
            "initial_point_candidates": 1,
        },
    )

    assert iterations == 500


def test_qse_vqe_reference_estimate_includes_reference_budget() -> None:
    iterations = estimate_total_iterations(
        algorithm=RunAlgorithm.QSE,
        config_payload={
            "algorithm": "qse",
            "reference_method": "vqe",
            "max_subspace_dim": 6,
            "vqe_reference_max_iterations": 80,
        },
    )

    assert iterations == 88


def test_qse_vqe_reference_default_matches_worker_budget() -> None:
    iterations = estimate_total_iterations(
        algorithm=RunAlgorithm.QSE,
        config_payload={
            "algorithm": "qse",
            "reference_method": "vqe",
            "max_subspace_dim": 6,
        },
    )

    assert iterations == 308


def test_sqd_vqe_estimate_reports_nested_sampling_workload() -> None:
    run_in = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.SQD,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.SQD,
                "samples_per_batch": 512,
                "num_batches": 8,
                "max_iterations": 8,
                "sampling_state_source": "vqe",
                "sampling_vqe_ansatz_name": "NumberPreserving",
                "sampling_vqe_optimizer_name": "COBYLA",
                "sampling_vqe_max_iterations": 448,
                "sampling_vqe_reps": 2,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=_h2_molecule(),
    )

    assert estimate is not None
    assert estimate["estimated_total_iterations"] == 8
    assert estimate["estimated_primary_iterations"] == 8
    assert estimate["estimated_reference_iterations"] == 450
    assert estimate["estimated_total_work_units"] == 458
    assert estimate["work_unit_policy"] == (
        "sqd_recovery_rounds_plus_sampling_vqe_objective_evaluations"
    )
    assert estimate["reference_workload"] == "sampling_vqe"


def test_initial_estimate_scales_with_backend_and_active_space() -> None:
    run_in = RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.KQD,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.AER_SIMULATOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.KQD,
                "krylov_dim": 8,
                "time_step": 0.1,
                "evolution_method": "trotter",
                "trotter_steps": 4,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(run_in=run_in, molecule=_h2_molecule())

    assert estimate is not None
    assert estimate["source"] == "config_projection"
    assert estimate["estimated_total_iterations"] == 44
    assert estimate["estimated_primary_iterations"] == 8
    assert estimate["estimated_matrix_element_pairs"] == 36
    assert estimate["estimated_total_work_units"] == 44
    assert estimate["work_unit_policy"] == "projected_state_pairs_plus_projected_solve"
    assert estimate["estimated_total_seconds"] is None
    assert estimate["estimated_remaining_seconds"] is None
    assert estimate["confidence"] is None


def test_build_initial_estimate_for_persisted_run_reconstructs_easy_contract(
    test_db: Session,
) -> None:
    molecule = _h2_molecule()
    test_db.add(molecule)
    test_db.commit()

    run = Run(
        molecule_id=molecule.id,
        basis_set="sto-3g",
        algorithm=RunAlgorithm.KQD,
        mode=RunMode.EASY,
        backend_target=BackendTarget.AER_SIMULATOR,
        status=RunStatus.CREATED,
        config_json={
            "algorithm": "kqd",
            "mode": "easy",
            "backend_target": "aer_simulator",
            "backend_options": {
                "selection_policy": "manual",
                "backend_name": "aer_simulator",
                "shots": 4096,
                "optimization_level": 1,
                "aer_method": "automatic",
            },
            "basis_set_override": "sto-3g",
            "easy_options": {"goal": "balanced"},
            "noise_profile": None,
            "ibm_runtime_confirmed": False,
        },
    )
    run.molecule = molecule

    estimate = build_initial_estimate_for_persisted_run(run=run, db=test_db)

    assert estimate is not None
    assert estimate["algorithm"] == "kqd"
    assert estimate["estimated_total_iterations"] == 44
    assert estimate["estimated_total_seconds"] is None


def test_seed_initial_estimate_for_run_persists_estimates_and_event(test_db: Session) -> None:
    molecule = _h2_molecule()
    test_db.add(molecule)
    test_db.commit()

    run = Run(
        molecule_id=molecule.id,
        basis_set="sto-3g",
        algorithm=RunAlgorithm.KQD,
        mode=RunMode.EASY,
        backend_target=BackendTarget.AER_SIMULATOR,
        status=RunStatus.QUEUED,
        config_json={
            "algorithm": "kqd",
            "mode": "easy",
            "backend_target": "aer_simulator",
            "backend_options": {
                "selection_policy": "manual",
                "backend_name": "aer_simulator",
                "shots": 4096,
                "optimization_level": 1,
                "aer_method": "automatic",
            },
            "basis_set_override": "sto-3g",
            "easy_options": {"goal": "balanced"},
            "noise_profile": None,
            "ibm_runtime_confirmed": False,
        },
        initial_estimate=None,
        latest_estimate=None,
    )
    test_db.add(run)
    test_db.commit()

    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db.get_bind(),
    )
    seed_initial_estimate_for_run(run_id=run.id, session_factory=session_factory)
    test_db.expire_all()

    updated_run = test_db.get(Run, run.id)
    assert updated_run is not None
    assert updated_run.initial_estimate is not None
    assert updated_run.latest_estimate is not None
    assert updated_run.latest_estimate["source"] == "config_projection"

    estimate_events = list(
        test_db.query(RunEvent)
        .filter(RunEvent.run_id == run.id, RunEvent.type == RunEventType.ESTIMATE_UPDATED)
        .all()
    )
    assert len(estimate_events) == 1
    assert estimate_events[0].payload == updated_run.latest_estimate


def test_seed_initial_estimate_for_run_does_not_overwrite_latest_telemetry(
    test_db: Session,
) -> None:
    molecule = _h2_molecule()
    test_db.add(molecule)
    test_db.commit()

    telemetry_estimate = {
        "source": "telemetry",
        "algorithm": "kqd",
        "estimated_total_iterations": 8,
        "estimated_remaining_iterations": 4,
        "estimated_total_seconds": 80.0,
        "estimated_remaining_seconds": 40.0,
        "confidence": 0.72,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    run = Run(
        molecule_id=molecule.id,
        basis_set="sto-3g",
        algorithm=RunAlgorithm.KQD,
        mode=RunMode.EASY,
        backend_target=BackendTarget.AER_SIMULATOR,
        status=RunStatus.RUNNING,
        config_json={
            "algorithm": "kqd",
            "mode": "easy",
            "backend_target": "aer_simulator",
            "backend_options": {
                "selection_policy": "manual",
                "backend_name": "aer_simulator",
                "shots": 4096,
                "optimization_level": 1,
                "aer_method": "automatic",
            },
            "basis_set_override": "sto-3g",
            "easy_options": {"goal": "balanced"},
            "noise_profile": None,
            "ibm_runtime_confirmed": False,
        },
        initial_estimate=None,
        latest_estimate=telemetry_estimate,
    )
    test_db.add(run)
    test_db.commit()

    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db.get_bind(),
    )
    seed_initial_estimate_for_run(run_id=run.id, session_factory=session_factory)
    test_db.expire_all()

    updated_run = test_db.get(Run, run.id)
    assert updated_run is not None
    assert updated_run.initial_estimate is not None
    assert updated_run.latest_estimate == telemetry_estimate

    estimate_events = list(
        test_db.query(RunEvent)
        .filter(RunEvent.run_id == run.id, RunEvent.type == RunEventType.ESTIMATE_UPDATED)
        .all()
    )
    assert estimate_events == []


def _persist_historical_kqd_run(
    test_db: Session,
    *,
    molecule: Molecule,
    runtime_seconds: float,
    krylov_dim: int,
    time_step: float,
    created_at: datetime,
) -> None:
    run = Run(
        molecule_id=molecule.id,
        basis_set="sto-3g",
        algorithm=RunAlgorithm.KQD,
        mode=RunMode.ADVANCED,
        backend_target=BackendTarget.STATEVECTOR,
        status=RunStatus.COMPLETED,
        config_json={
            "algorithm": "kqd",
            "mode": "advanced",
            "backend_target": "statevector",
            "backend_options": {
                "selection_policy": "manual",
                "shots": 4096,
                "optimization_level": 1,
                "aer_method": "automatic",
            },
            "advanced_config": {
                "algorithm": "kqd",
                "krylov_dim": krylov_dim,
                "time_step": time_step,
                "evolution_method": "trotter",
                "trotter_steps": 2,
            },
        },
        run_metadata={
            "algorithm": "kqd",
            "mode": "advanced",
            "backend_target": "statevector",
            "runtime_seconds": runtime_seconds,
            "run_started_at": (created_at - timedelta(seconds=runtime_seconds)).isoformat(),
            "run_finished_at": created_at.isoformat(),
        },
        initial_estimate={
            "source": "history",
            "algorithm": "kqd",
            "estimated_total_iterations": krylov_dim,
            "estimated_remaining_iterations": krylov_dim,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": runtime_seconds,
            "confidence": 0.82,
            "updated_at": created_at.isoformat(),
            "estimated_seconds_per_iteration": runtime_seconds / krylov_dim,
        },
        latest_estimate={
            "source": "telemetry",
            "algorithm": "kqd",
            "estimated_total_iterations": krylov_dim,
            "estimated_remaining_iterations": 0,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": 0.0,
            "estimated_seconds_per_iteration": runtime_seconds / krylov_dim,
            "confidence": 0.9,
            "updated_at": created_at.isoformat(),
        },
        created_at=created_at,
        updated_at=created_at,
    )
    test_db.add(run)
    test_db.flush()
    test_db.add(
        RunResult(
            run_id=run.id,
            energy=-1.0,
            iterations=krylov_dim,
            optimal_parameters=[],
            converged=True,
            algorithm_metrics={"krylov_rank": krylov_dim},
        )
    )
    test_db.commit()


def _persist_historical_qfd_run(
    test_db: Session,
    *,
    molecule: Molecule,
    backend_target: BackendTarget,
    runtime_seconds: float,
    num_time_points: int,
    latest_total_iterations: int,
    max_time: float,
    created_at: datetime,
) -> None:
    backend_target_value = backend_target.value
    backend_name = "ibm_oslo" if backend_target == BackendTarget.IBM_RUNTIME else None
    run = Run(
        molecule_id=molecule.id,
        basis_set="sto-3g",
        algorithm=RunAlgorithm.QFD,
        mode=RunMode.ADVANCED,
        backend_target=backend_target,
        status=RunStatus.COMPLETED,
        config_json={
            "algorithm": "qfd",
            "mode": "advanced",
            "backend_target": backend_target_value,
            "backend_options": {
                "selection_policy": "manual",
                "backend_name": backend_name,
                "shots": 4096,
                "optimization_level": 1,
                "aer_method": "automatic",
            },
            "advanced_config": {
                "algorithm": "qfd",
                "max_time": max_time,
                "num_time_points": num_time_points,
                "time_grid_type": "geometric",
                "trotter_steps": 2,
                "residual_tolerance": 1e-6,
            },
        },
        run_metadata={
            "algorithm": "qfd",
            "mode": "advanced",
            "backend_target": backend_target_value,
            "runtime_seconds": runtime_seconds,
            "run_started_at": (created_at - timedelta(seconds=runtime_seconds)).isoformat(),
            "run_finished_at": created_at.isoformat(),
        },
        initial_estimate={
            "source": "history",
            "algorithm": "qfd",
            "estimated_total_iterations": num_time_points,
            "estimated_remaining_iterations": num_time_points,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": runtime_seconds,
            "confidence": 0.82,
            "updated_at": created_at.isoformat(),
            "estimated_seconds_per_iteration": runtime_seconds / latest_total_iterations,
        },
        latest_estimate={
            "source": "telemetry",
            "algorithm": "qfd",
            "estimated_total_iterations": latest_total_iterations,
            "estimated_remaining_iterations": 0,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": 0.0,
            "estimated_seconds_per_iteration": runtime_seconds / latest_total_iterations,
            "confidence": 0.9,
            "updated_at": created_at.isoformat(),
        },
        created_at=created_at,
        updated_at=created_at,
    )
    test_db.add(run)
    test_db.flush()
    test_db.add(
        RunResult(
            run_id=run.id,
            energy=-1.0,
            iterations=num_time_points,
            optimal_parameters=[],
            converged=True,
            algorithm_metrics={"time_grid_points": num_time_points},
        )
    )
    test_db.commit()


def _persist_historical_vqe_run(
    test_db: Session,
    *,
    molecule: Molecule,
    runtime_seconds: float,
    max_function_evaluations: int,
    completed_iterations: int,
    created_at: datetime,
    status: RunStatus = RunStatus.COMPLETED,
) -> None:
    run = Run(
        molecule_id=molecule.id,
        basis_set="sto-3g",
        algorithm=RunAlgorithm.VQE,
        mode=RunMode.ADVANCED,
        backend_target=BackendTarget.STATEVECTOR,
        status=status,
        config_json={
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "statevector",
            "backend_options": {
                "selection_policy": "manual",
                "shots": 4096,
                "optimization_level": 1,
                "aer_method": "automatic",
            },
            "advanced_config": {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 350,
                "max_function_evaluations": max_function_evaluations,
                "initial_point_strategy": "zero_plus_seeded_random",
                "initial_point_candidates": 3,
                "reps": 2,
            },
        },
        run_metadata={
            "algorithm": "vqe",
            "mode": "advanced",
            "backend_target": "statevector",
            "runtime_seconds": runtime_seconds,
            "run_started_at": (created_at - timedelta(seconds=runtime_seconds)).isoformat(),
            "run_finished_at": created_at.isoformat(),
        },
        initial_estimate={
            "source": "history",
            "algorithm": "vqe",
            "estimated_total_iterations": max_function_evaluations,
            "estimated_remaining_iterations": max_function_evaluations,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": runtime_seconds,
            "confidence": 0.82,
            "updated_at": created_at.isoformat(),
            "estimated_seconds_per_iteration": runtime_seconds / completed_iterations,
        },
        latest_estimate={
            "source": "telemetry",
            "algorithm": "vqe",
            "estimated_total_iterations": completed_iterations,
            "estimated_remaining_iterations": 0,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": 0.0,
            "estimated_seconds_per_iteration": runtime_seconds / completed_iterations,
            "confidence": 0.9,
            "updated_at": created_at.isoformat(),
        },
        created_at=created_at,
        updated_at=created_at,
    )
    test_db.add(run)
    test_db.flush()
    if status == RunStatus.COMPLETED:
        test_db.add(
            RunResult(
                run_id=run.id,
                energy=-1.0,
                iterations=completed_iterations,
                optimal_parameters=[],
                converged=True,
                algorithm_metrics={"objective_evaluations": completed_iterations},
            )
        )
    test_db.commit()


def _persist_historical_easy_sqd_run(
    test_db: Session,
    *,
    molecule: Molecule,
    runtime_seconds: float,
    max_iterations: int,
    samples_per_batch: int,
    num_batches: int,
    max_dim: int | None,
    catalog_version: str,
    created_at: datetime,
) -> None:
    expanded_config = {
        "algorithm": "sqd",
        "samples_per_batch": samples_per_batch,
        "num_batches": num_batches,
        "max_iterations": max_iterations,
        "energy_tol": 7.5e-5,
        "occupancies_tol": 7.5e-5,
        "min_selected_configurations": 2,
        "num_elec_a": 1,
        "num_elec_b": 1,
    }
    if max_dim is not None:
        expanded_config["max_dim"] = max_dim

    run = Run(
        molecule_id=molecule.id,
        basis_set="sto-3g",
        algorithm=RunAlgorithm.SQD,
        mode=RunMode.EASY,
        backend_target=BackendTarget.STATEVECTOR,
        status=RunStatus.COMPLETED,
        config_json={
            "algorithm": "sqd",
            "mode": "easy",
            "backend_target": "statevector",
            "easy_options": {"goal": "balanced"},
            "backend_options": {
                "selection_policy": "manual",
                "shots": 4096,
                "optimization_level": 1,
                "aer_method": "automatic",
            },
            "basis_set_override": "sto-3g",
        },
        run_metadata={
            "algorithm": "sqd",
            "mode": "easy",
            "backend_target": "statevector",
            "runtime_seconds": runtime_seconds,
            "run_started_at": (created_at - timedelta(seconds=runtime_seconds)).isoformat(),
            "run_finished_at": created_at.isoformat(),
            "easy_mode": {
                "goal": "balanced",
                "catalog_version": catalog_version,
                "expanded_advanced_config": expanded_config,
            },
        },
        initial_estimate={
            "source": "history",
            "algorithm": "sqd",
            "estimated_total_iterations": max_iterations,
            "estimated_remaining_iterations": max_iterations,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": runtime_seconds,
            "confidence": 0.82,
            "updated_at": created_at.isoformat(),
            "estimated_seconds_per_iteration": runtime_seconds / max_iterations,
        },
        latest_estimate={
            "source": "telemetry",
            "algorithm": "sqd",
            "estimated_total_iterations": max_iterations,
            "estimated_remaining_iterations": 0,
            "estimated_total_seconds": runtime_seconds,
            "estimated_remaining_seconds": 0.0,
            "estimated_seconds_per_iteration": runtime_seconds / max_iterations,
            "confidence": 0.82,
            "updated_at": created_at.isoformat(),
        },
        created_at=created_at,
        updated_at=created_at,
    )
    test_db.add(run)
    test_db.commit()


def test_initial_estimate_blends_history_for_similar_runs(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    historical_molecule = Molecule(
        name="LiH_history",
        atoms=[
            {"symbol": "Li", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 1.6},
        ],
        charge=0,
        multiplicity=1,
        active_space={"n_electrons": 2, "n_orbitals": 2},
    )
    test_db.add(historical_molecule)
    test_db.commit()
    test_db.refresh(historical_molecule)

    created_at = datetime.now(UTC) - timedelta(hours=6)
    _persist_historical_kqd_run(
        test_db,
        molecule=historical_molecule,
        runtime_seconds=120.0,
        krylov_dim=6,
        time_step=0.12,
        created_at=created_at,
    )
    _persist_historical_kqd_run(
        test_db,
        molecule=historical_molecule,
        runtime_seconds=132.0,
        krylov_dim=6,
        time_step=0.15,
        created_at=created_at + timedelta(minutes=15),
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.KQD,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.KQD,
                "krylov_dim": 6,
                "time_step": 0.14,
                "evolution_method": "trotter",
                "trotter_steps": 2,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "history"
    assert estimate["confidence"] > 0.65
    assert estimate["estimated_total_iterations"] == 6
    assert estimate["estimated_total_seconds"] > 90.0


def test_initial_estimate_rejects_large_history_for_small_request(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    large_history_molecule = Molecule(
        name="Large_history",
        atoms=[
            {"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 1.0},
            {"symbol": "H", "x": 0.0, "y": 1.0, "z": 0.0},
            {"symbol": "H", "x": 1.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": -1.0, "z": 0.0},
            {"symbol": "O", "x": 1.2, "y": 1.2, "z": 0.0},
            {"symbol": "N", "x": -1.2, "y": 1.2, "z": 0.0},
            {"symbol": "F", "x": 1.2, "y": -1.2, "z": 0.0},
        ],
        charge=0,
        multiplicity=1,
        active_space={"n_electrons": 12, "n_orbitals": 10},
    )
    test_db.add(large_history_molecule)
    test_db.commit()
    test_db.refresh(large_history_molecule)

    _persist_historical_kqd_run(
        test_db,
        molecule=large_history_molecule,
        runtime_seconds=800.0,
        krylov_dim=6,
        time_step=0.14,
        created_at=datetime.now(UTC) - timedelta(hours=3),
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.KQD,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": RunAlgorithm.KQD,
                "krylov_dim": 6,
                "time_step": 0.14,
                "evolution_method": "trotter",
                "trotter_steps": 2,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "config_projection"
    assert estimate["estimated_total_seconds"] is None
    assert estimate["estimated_remaining_seconds"] is None


def test_easy_mode_history_ignores_mismatched_catalog_versions(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    created_at = datetime.now(UTC) - timedelta(minutes=30)
    _persist_historical_easy_sqd_run(
        test_db,
        molecule=sample_molecule,
        runtime_seconds=960.0,
        max_iterations=48,
        samples_per_batch=320,
        num_batches=6,
        max_dim=None,
        catalog_version="2026-06-05-v4",
        created_at=created_at,
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.SQD,
            "mode": RunMode.EASY,
            "backend_target": BackendTarget.STATEVECTOR,
            "easy_options": {"goal": "balanced"},
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "config_projection"
    assert estimate["estimated_total_iterations"] == 8
    assert estimate["estimated_total_seconds"] is None
    assert estimate["estimated_remaining_seconds"] is None


def test_easy_mode_history_uses_matching_catalog_versions(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    created_at = datetime.now(UTC) - timedelta(minutes=20)
    _persist_historical_easy_sqd_run(
        test_db,
        molecule=sample_molecule,
        runtime_seconds=720.0,
        max_iterations=48,
        samples_per_batch=320,
        num_batches=6,
        max_dim=24,
        catalog_version=EASY_MODE_CATALOG_VERSION,
        created_at=created_at,
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.SQD,
            "mode": RunMode.EASY,
            "backend_target": BackendTarget.STATEVECTOR,
            "easy_options": {"goal": "balanced"},
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "history"
    assert estimate["confidence"] > 0.65
    assert estimate["estimated_total_iterations"] == 48
    assert estimate["estimated_total_seconds"] == pytest.approx(720.0)


def test_initial_estimate_uses_completed_iterations_from_reliable_history(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    created_at = datetime.now(UTC) - timedelta(minutes=10)
    _persist_historical_vqe_run(
        test_db,
        molecule=sample_molecule,
        runtime_seconds=18.0,
        max_function_evaluations=3500,
        completed_iterations=353,
        created_at=created_at,
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 350,
                "max_function_evaluations": 3500,
                "initial_point_strategy": "zero_plus_seeded_random",
                "initial_point_candidates": 3,
                "reps": 2,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "history"
    assert estimate["estimated_total_iterations"] == 353
    assert estimate["historical_completed_iterations"] == 353
    assert estimate["estimated_total_seconds"] == pytest.approx(18.0)


def test_initial_estimate_ignores_failed_history_even_when_runtime_exists(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    created_at = datetime.now(UTC) - timedelta(minutes=10)
    _persist_historical_vqe_run(
        test_db,
        molecule=sample_molecule,
        runtime_seconds=12_000.0,
        max_function_evaluations=420,
        completed_iterations=12,
        created_at=created_at,
        status=RunStatus.FAILED,
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.VQE,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.STATEVECTOR,
            "advanced_config": {
                "algorithm": "vqe",
                "ansatz_name": "EfficientSU2",
                "optimizer_name": "COBYLA",
                "max_iterations": 420,
                "max_function_evaluations": 420,
                "initial_point_strategy": "zero_plus_seeded_random",
                "initial_point_candidates": 4,
                "reps": 1,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "config_projection"
    assert estimate["estimated_total_iterations"] == 420
    assert estimate["estimated_total_seconds"] is None


def test_ibm_history_ignores_local_backend_matches(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    created_at = datetime.now(UTC) - timedelta(minutes=12)
    _persist_historical_qfd_run(
        test_db,
        molecule=sample_molecule,
        backend_target=BackendTarget.AER_SIMULATOR,
        runtime_seconds=72.0,
        num_time_points=8,
        latest_total_iterations=44,
        max_time=2.0,
        created_at=created_at,
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.QFD,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.IBM_RUNTIME,
            "advanced_config": {
                "algorithm": "qfd",
                "max_time": 2.0,
                "num_time_points": 8,
                "time_grid_type": "geometric",
                "trotter_steps": 2,
                "residual_tolerance": 1e-6,
            },
            "backend_options": {
                "backend_name": "ibm_oslo",
                "selection_policy": "manual",
                "shots": 4096,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "config_projection"
    assert estimate["estimated_total_iterations"] == 44
    assert estimate["estimated_total_seconds"] is None


def test_ibm_history_uses_matching_backend_completed_iterations(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    created_at = datetime.now(UTC) - timedelta(minutes=8)
    _persist_historical_qfd_run(
        test_db,
        molecule=sample_molecule,
        backend_target=BackendTarget.IBM_RUNTIME,
        runtime_seconds=72.0,
        num_time_points=8,
        latest_total_iterations=44,
        max_time=2.0,
        created_at=created_at,
    )

    run_in = RunCreate.model_validate(
        {
            "molecule_id": sample_molecule.id,
            "algorithm": RunAlgorithm.QFD,
            "mode": RunMode.ADVANCED,
            "backend_target": BackendTarget.IBM_RUNTIME,
            "advanced_config": {
                "algorithm": "qfd",
                "max_time": 2.0,
                "num_time_points": 8,
                "time_grid_type": "geometric",
                "trotter_steps": 2,
                "residual_tolerance": 1e-6,
            },
            "backend_options": {
                "backend_name": "ibm_oslo",
                "selection_policy": "manual",
                "shots": 4096,
            },
        }
    )

    estimate = build_initial_estimate_for_run_request(
        run_in=run_in,
        molecule=sample_molecule,
        db=test_db,
    )

    assert estimate is not None
    assert estimate["source"] == "history"
    assert estimate["estimated_total_iterations"] == 44
    assert estimate["historical_completed_iterations"] == 44
    assert estimate["estimated_total_seconds"] == pytest.approx(72.0)


def test_history_query_leaves_large_result_payloads_unloaded(
    test_db: Session,
    sample_molecule: Molecule,
) -> None:
    created_at = datetime.now(UTC) - timedelta(hours=1)
    _persist_historical_kqd_run(
        test_db,
        molecule=sample_molecule,
        runtime_seconds=120.0,
        krylov_dim=6,
        time_step=0.14,
        created_at=created_at,
    )
    historical_run = (
        test_db.query(Run)
        .filter(Run.algorithm == RunAlgorithm.KQD)
        .order_by(Run.created_at.desc())
        .first()
    )
    assert historical_run is not None
    assert historical_run.result is not None
    historical_run.result.raw_result = {"payload": "x" * 10_000}
    test_db.commit()
    test_db.expire_all()

    loaded_runs = test_db.scalars(history_runs_statement(RunAlgorithm.KQD)).all()

    assert loaded_runs
    loaded_result = loaded_runs[0].result
    assert loaded_result is not None
    assert "algorithm_metrics" in sa_inspect(loaded_result).unloaded
    assert "raw_result" in sa_inspect(loaded_result).unloaded
