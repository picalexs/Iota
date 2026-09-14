"""
Unit tests for Run/RunEvent ORM contract guarantees.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.models.enums import BackendTarget, RunAlgorithm, RunMode
from app.models.molecule import Molecule
from app.models.run import Run, RunStatus
from app.models.run_event import RunEvent, RunEventType
from app.models.run_result import RunResult
from app.schemas.run import (
    CircuitArtifact,
    RunResponse,
    RunSummaryResponse,
    RunValidationErrorDetail,
    RunValidationResponse,
)
from sqlalchemy import inspect
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session


def _sample_config() -> dict[str, object]:
    return {
        "basis_set": "sto-3g",
        "ansatz": "UCC",
        "optimizer": "COBYLA",
        "max_iterations": 100,
        "backend": "aer_simulator",
    }


def test_circuit_artifact_schema_accepts_algorithm_metrics_shape() -> None:
    artifact = CircuitArtifact.model_validate(
        {
            "schema_version": "2.0",
            "artifact_type": "quantum_circuit",
            "id": "vqe.final",
            "artifact_id": "vqe.final",
            "algorithm": "vqe",
            "role": "final",
            "phase": "optimization",
            "representative": True,
            "label": "Final VQE circuit",
            "qubits": 4,
            "operation_counts": {"ry": 4, "cx": 2},
            "logical": {
                "qubits": 4,
                "classical_bits": 0,
                "style": "iqp",
                "qasm": "OPENQASM 3.0;",
            },
            "transpiled": {
                "qubits": 4,
                "classical_bits": 0,
                "style": "iqp",
                "diagram_svg": "<svg></svg>",
            },
            "backend_target": "ibm_runtime",
            "primitive_family": "sampler_v2",
            "job_ids": ["job-1"],
            "pub_count": 1,
            "shots": 4096,
        }
    )

    assert artifact.artifact_type == "quantum_circuit"
    assert artifact.logical is not None
    assert artifact.logical.qasm == "OPENQASM 3.0;"
    assert artifact.transpiled is not None
    assert artifact.id == "vqe.final"


def test_run_status_enum_rejects_invalid_value(test_db: Session, sample_molecule: Molecule) -> None:
    """Run.status should only accept configured enum values."""
    run = Run(
        molecule_id=sample_molecule.id,
        status="INVALID_STATUS",
        config_json=_sample_config(),
    )
    test_db.add(run)

    with pytest.raises(StatementError):
        test_db.commit()

    test_db.rollback()


def test_run_event_type_enum_rejects_invalid_value(
    test_db: Session, sample_molecule: Molecule
) -> None:
    """RunEvent.type should only accept configured enum values."""
    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.CREATED,
        config_json=_sample_config(),
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    event = RunEvent(
        run_id=run.id,
        sequence=1,
        type="unknown_event_type",
        payload={"status": "RUNNING"},
    )
    test_db.add(event)

    with pytest.raises(StatementError):
        test_db.commit()

    test_db.rollback()


def test_run_json_fields_round_trip(test_db: Session, sample_molecule: Molecule) -> None:
    """Run JSON contract fields should preserve values on round-trip."""
    expected_versions = {"python": "3.12.3", "qiskit": "2.3.0"}
    expected_metadata = {"source": "unit-test", "tags": ["contract", "orm"]}
    expected_payload = {"iteration": 1, "energy": -1.042}

    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.SUBMITTED_TO_IBM,
        config_json=_sample_config(),
        versions=expected_versions,
        run_metadata=expected_metadata,
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    event = RunEvent(
        run_id=run.id,
        sequence=1,
        type=RunEventType.ITERATION_UPDATE,
        payload=expected_payload,
    )
    test_db.add(event)
    test_db.commit()
    test_db.refresh(event)

    assert run.status == RunStatus.SUBMITTED_TO_IBM
    assert run.versions == expected_versions
    assert run.run_metadata == expected_metadata
    assert event.payload == expected_payload


def test_run_response_includes_ibm_profile_name_snapshot(
    test_db: Session, sample_molecule: Molecule
) -> None:
    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.CREATED,
        config_json=_sample_config(),
        credential_profile_id=uuid4(),
        credential_profile_name="Main IBM",
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    response = RunResponse.model_validate(run)

    assert response.credential_profile_name == "Main IBM"


def test_run_responses_ignore_incomplete_legacy_estimate(
    test_db: Session, sample_molecule: Molecule
) -> None:
    """Incomplete historical estimates must not break run list responses."""
    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.COMPLETED,
        config_json=_sample_config(),
        latest_estimate={"estimated_remaining_iterations": 2},
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    response = RunResponse.model_validate(run)
    summary = RunSummaryResponse.from_run(run)

    assert response.latest_estimate is None
    assert summary.latest_estimate is None


def test_run_delete_cascades_to_events_and_result(
    test_db: Session, sample_molecule: Molecule
) -> None:
    """Deleting a run should remove child events and result rows."""
    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.RUNNING,
        config_json=_sample_config(),
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    event = RunEvent(
        run_id=run.id,
        sequence=1,
        type=RunEventType.STATUS_CHANGED,
        payload={"status": "RUNNING"},
    )
    result = RunResult(
        run_id=run.id,
        energy=-1.1372,
        iterations=42,
        optimal_parameters=[0.1587, -0.2201],
        converged=True,
    )
    test_db.add_all([event, result])
    test_db.commit()

    run_id = run.id
    test_db.delete(run)
    test_db.commit()

    assert test_db.query(RunEvent).filter(RunEvent.run_id == run_id).count() == 0
    assert test_db.query(RunResult).filter(RunResult.run_id == run_id).count() == 0


def test_run_tables_expose_required_indexes_and_constraints(test_db: Session) -> None:
    """Index/constraint contract should match expected query paths."""
    bind = test_db.bind
    assert bind is not None
    inspector = inspect(bind)

    run_indexes = {index["name"]: index for index in inspector.get_indexes("runs")}
    assert "idx_runs_status" in run_indexes
    assert run_indexes["idx_runs_status"]["column_names"] == ["status"]
    assert "idx_runs_molecule_status" in run_indexes
    assert run_indexes["idx_runs_molecule_status"]["column_names"] == ["molecule_id", "status"]

    event_indexes = {index["name"]: index for index in inspector.get_indexes("run_events")}
    assert "idx_run_events_run_id" in event_indexes
    assert event_indexes["idx_run_events_run_id"]["column_names"] == ["run_id"]
    assert "idx_run_events_type" in event_indexes
    assert event_indexes["idx_run_events_type"]["column_names"] == ["type"]

    unique_constraints = inspector.get_unique_constraints("run_events")
    assert any(
        uc["name"] == "uq_run_events_run_id_sequence"
        and uc["column_names"] == ["run_id", "sequence"]
        for uc in unique_constraints
    )


def test_run_metadata_mapping_and_cascade_configuration() -> None:
    """Model-level mapping should keep metadata and FK cascade configuration."""
    assert "metadata" in Run.__table__.c
    assert "run_metadata" in Run.__mapper__.attrs
    assert "algorithm" in Run.__table__.c
    assert "mode" in Run.__table__.c
    assert "backend_target" in Run.__table__.c
    assert "initial_estimate" in Run.__table__.c
    assert "latest_estimate" in Run.__table__.c
    assert "algorithm_metrics" in RunResult.__table__.c

    run_event_fk = next(iter(RunEvent.__table__.c.run_id.foreign_keys))
    run_result_fk = next(iter(RunResult.__table__.c.run_id.foreign_keys))
    assert run_event_fk.ondelete == "CASCADE"
    assert run_result_fk.ondelete == "CASCADE"


def test_run_validation_response_uses_isolated_default_lists() -> None:
    """RunValidationResponse list defaults should not be shared across instances."""
    first = RunValidationResponse(valid=False)
    second = RunValidationResponse(valid=False)

    first.errors.append(RunValidationErrorDetail(field="backend", message="Unsupported backend"))
    first.warnings.append("Fallback optimizer will be used")

    assert second.errors == []
    assert second.warnings == []


def test_run_result_algorithm_metrics_column_round_trips() -> None:
    """RunResult should persist algorithm_metrics as a dedicated column."""
    run_result = RunResult(
        run_id=uuid4(),
        energy=-1.0,
        iterations=5,
        optimal_parameters=[],
        converged=True,
        algorithm_metrics={"batches": 3},
        raw_result={"other": "value"},
    )

    assert run_result.algorithm_metrics == {"batches": 3}
    assert run_result.raw_result == {"other": "value"}


def test_run_model_exposes_algorithm_columns_on_orm_instances(
    test_db: Session, sample_molecule: Molecule
) -> None:
    """Run ORM instances should keep algorithm, mode, and backend target values."""
    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.CREATED,
        config_json=_sample_config(),
        algorithm=RunAlgorithm.VQE,
        mode=RunMode.EASY,
        backend_target=BackendTarget.STATEVECTOR,
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    assert run.algorithm == RunAlgorithm.VQE
    assert run.mode == RunMode.EASY
    assert run.backend_target == BackendTarget.STATEVECTOR


def test_run_response_preserves_easy_mode_metadata_snapshot(
    test_db: Session, sample_molecule: Molecule
) -> None:
    """RunResponse should round-trip nested easy-mode metadata snapshots."""
    easy_mode_metadata = {
        "algorithm": "skqd",
        "mode": "easy",
        "backend_target": "statevector",
        "easy_mode": {
            "catalog_version": "2026-04-09-v1",
            "goal": "balanced",
            "expanded_advanced_config": {
                "algorithm": "skqd",
                "base_sampling_options": {
                    "samples_per_batch": 256,
                    "num_batches": 8,
                    "max_iterations": 50,
                    "num_elec_a": 1,
                    "num_elec_b": 1,
                },
                "krylov_extension_dim": 4,
            },
        },
    }

    run = Run(
        molecule_id=sample_molecule.id,
        status=RunStatus.CREATED,
        config_json=_sample_config(),
        algorithm=RunAlgorithm.SKQD,
        mode=RunMode.EASY,
        backend_target=BackendTarget.STATEVECTOR,
        run_metadata=easy_mode_metadata,
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    response = RunResponse.model_validate(run)
    metadata = response.metadata
    assert metadata is not None

    assert metadata == easy_mode_metadata
    assert metadata["easy_mode"]["catalog_version"] == "2026-04-09-v1"
    assert metadata["easy_mode"]["expanded_advanced_config"]["krylov_extension_dim"] == 4


def test_molecule_table_has_no_basis_set_column(test_db: Session) -> None:
    """molecules table must NOT have a basis_set column (moved to runs in 20260227_0003)."""
    bind = test_db.bind
    assert bind is not None
    inspector = inspect(bind)
    molecule_columns = {col["name"] for col in inspector.get_columns("molecules")}

    assert "basis_set" not in molecule_columns


def test_run_table_has_basis_set_column(test_db: Session) -> None:
    """runs table must have a basis_set column (added in 20260227_0003)."""
    bind = test_db.bind
    assert bind is not None
    inspector = inspect(bind)
    run_columns = {col["name"] for col in inspector.get_columns("runs")}

    assert "basis_set" in run_columns


def test_molecules_unique_by_name_only(test_db: Session, sample_molecule: Molecule) -> None:
    """molecules unique constraint must be on 'name' alone, not (name, basis_set)."""
    bind = test_db.bind
    assert bind is not None
    inspector = inspect(bind)
    unique_constraints = inspector.get_unique_constraints("molecules")
    name_uq = next(
        (uc for uc in unique_constraints if "name" in uc["column_names"]),
        None,
    )

    assert name_uq is not None, "Expected a unique constraint involving 'name'"
    assert name_uq["column_names"] == ["name"], (
        f"Unique constraint should be on ['name'] only, got {name_uq['column_names']}"
    )
