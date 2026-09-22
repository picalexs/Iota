"""Unit tests for worker setup and result metadata assembly."""

from types import SimpleNamespace

import pytest

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.types import ChemistryInput
from worker.jobs.execution_metadata import (
    apply_result_metadata,
    branch_matrix_execution_metadata,
    build_hamiltonian_message,
    build_setup_payload,
)


def _adapter(metadata: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        capabilities=SimpleNamespace(backend_target="statevector"),
        execution_metadata=lambda _context: dict(metadata or {}),
    )


def _bundle(**metadata: object) -> SimpleNamespace:
    return SimpleNamespace(
        num_qubits=4,
        num_spatial_orbitals=2,
        metadata={"active_space": [2, 2], "pipeline": "test", **metadata},
    )


def _manifest() -> dict[str, object]:
    return {"manifest_sha256": "manifest-test", "sector": {"full_target_sector_dimension": 4}}


def test_setup_payload_combines_chemistry_and_backend_metadata() -> None:
    payload = build_setup_payload(
        algorithm="vqe",
        mode="advanced",
        backend_context=BackendExecutionContext(
            backend_target="statevector",
            selection_policy="requested",
            shots=123,
        ),
        backend_adapter=_adapter({"resolved_backend_name": "statevector"}),
        hamiltonian_bundle=_bundle(hf_energy=-1.0),
    )

    assert payload["stage"] == "setup"
    assert payload["num_qubits"] == 4
    assert payload["shots"] == 123
    assert payload["resolved_backend_name"] == "statevector"
    assert payload["hf_energy"] == -1.0
    assert payload["execution_plan"]["execution_lane"] == "local_exact"
    assert payload["execution_plan"]["plan_is_runtime_proof"] is False
    assert payload["gpu_options"] == {}


def test_result_metadata_keeps_gpu_capability_separate_from_execution_proof() -> None:
    result = {"raw_result": {}, "algorithm_metrics": {}}
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"device": "GPU"},
    )

    apply_result_metadata(
        result,
        algorithm="vqe",
        mode="advanced",
        backend_target="aer_simulator",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "available_devices": ["CPU", "GPU"],
                "actual_device": None,
                "device_verified": False,
            }
        ),
        backend_context=context,
    )

    state_stage = next(
        stage
        for stage in result["backend_execution"]["execution_plan"]["stage_paths"]
        if stage["stage_name"] == "state_generation_or_sampling"
    )
    assert state_stage["planned_device"] == "GPU"
    assert state_stage["actual_device"] is None
    assert state_stage["device_verified"] is False


def test_setup_payload_preserves_problem_manifest() -> None:
    payload = build_setup_payload(
        algorithm="vqe",
        mode="advanced",
        backend_context=BackendExecutionContext(backend_target="statevector"),
        backend_adapter=_adapter(),
        hamiltonian_bundle=_bundle(problem_manifest=_manifest()),
    )

    assert payload["problem_manifest"]["manifest_sha256"] == "manifest-test"


def test_result_metadata_preserves_problem_manifest() -> None:
    manifest = _manifest()
    result = {
        "raw_result": {"problem_manifest": manifest},
        "algorithm_metrics": {},
    }

    apply_result_metadata(
        result,
        algorithm="vqe",
        mode="advanced",
        backend_target="statevector",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(),
        backend_context=BackendExecutionContext(backend_target="statevector"),
    )

    assert result["problem_manifest"] == manifest
    assert result["algorithm_metrics"]["problem_manifest"] == manifest


def test_branch_matrix_metadata_describes_aer_estimator_execution() -> None:
    payload = branch_matrix_execution_metadata("qfd", "aer_simulator")

    assert payload["execution_mode"] == "aer_branch_estimator"
    assert payload["actual_execution_target"] == "aer_simulator"
    assert payload["actual_path_class"] == "aer_branch_estimator"
    assert payload["backend_primitives_used"] is True
    assert payload["primitive_family"] == "qiskit_aer.EstimatorV2"


def test_conditional_setup_metadata_does_not_claim_primitive_execution() -> None:
    for algorithm in ("kqd", "qfd", "qse"):
        payload = build_setup_payload(
            algorithm=algorithm,
            mode="advanced",
            backend_context=BackendExecutionContext(
                backend_target="ibm_runtime",
            ),
            backend_adapter=_adapter(
                {
                    "backend_primitives_used": True,
                    "primitive_family": "qiskit_ibm_runtime.EstimatorV2",
                }
            ),
            hamiltonian_bundle=_bundle(),
        )

        assert payload["execution_mode"] == f"{algorithm}_path_pending"
        assert payload["backend_primitives_used"] is False
        assert payload["primitive_family"] is None


def test_result_metadata_enrichment_preserves_algorithm_payload() -> None:
    result = {
        "raw_result": {},
        "algorithm_metrics": {
            "matrix_element_summary": {"matrix_element_strategy": "branch_estimator"}
        },
    }

    apply_result_metadata(
        result,
        algorithm="qfd",
        mode="advanced",
        backend_target="aer_simulator",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(),
        backend_context=BackendExecutionContext(backend_target="aer_simulator"),
    )

    assert result["basis_set"] == "6-31g"
    assert result["raw_result"]["basis_set"] == "6-31g"
    assert result["backend_execution"]["execution_mode"] == "aer_branch_estimator"
    assert result["algorithm_metrics"]["backend_execution"] == result["backend_execution"]


def test_direct_aer_kqd_path_is_not_reclassified_as_local_classical() -> None:
    result = {
        "raw_result": {},
        "algorithm_metrics": {
            "matrix_element_summary": {
                "matrix_element_strategy": "dense_classical",
                "implemented_evolution_method": "aer_pauli_lie_trotter",
            }
        },
    }
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"device": "CPU"},
    )

    apply_result_metadata(
        result,
        algorithm="kqd",
        mode="advanced",
        backend_target="aer_simulator",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "available_devices": ["CPU", "GPU"],
                "actual_execution_target": "aer_simulator",
                "actual_path_class": "aer_primitive",
                "aer_simulator_used": True,
                "backend_primitives_used": False,
            }
        ),
        backend_context=context,
    )

    metadata = result["backend_execution"]
    assert metadata["actual_path_class"] == "aer_statevector_evolution"
    assert metadata["actual_execution_target"] == "aer_simulator"
    assert metadata["aer_capability"]["status"] == "supported"


def test_measured_qse_metadata_preserves_aer_estimator_path() -> None:
    result = {
        "raw_result": {},
        "algorithm_metrics": {"execution_mode": "measured_matrix_elements"},
    }
    context = BackendExecutionContext(
        backend_target="aer_simulator",
        backend_options={"device": "GPU"},
    )

    apply_result_metadata(
        result,
        algorithm="qse",
        mode="advanced",
        backend_target="aer_simulator",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "available_devices": ["CPU", "GPU"],
                "actual_execution_target": "aer_simulator",
                "actual_path_class": "aer_primitive",
                "actual_device": "GPU",
                "device_verified": True,
                "backend_primitives_used": True,
                "primitive_family": "qiskit_aer.EstimatorV2",
            }
        ),
        backend_context=context,
    )

    metadata = result["backend_execution"]
    assert metadata["actual_path_class"] == "measured_matrix_elements"
    assert metadata["measured_projected_matrix_elements"] is True
    assert metadata["aer_capability"]["status"] == "supported"


@pytest.mark.parametrize("algorithm", ("vqe", "sqd", "skqd", "kqd", "qfd", "qse"))
def test_explicit_aer_gpu_requires_result_level_device_evidence(algorithm: str) -> None:
    metrics: dict[str, object] = {}
    if algorithm in {"kqd", "qfd"}:
        metrics["matrix_element_summary"] = {
            "matrix_element_strategy": "branch_estimator"
        }
    elif algorithm == "qse":
        metrics["execution_mode"] = "measured_matrix_elements"

    result = {"raw_result": {}, "algorithm_metrics": metrics}
    apply_result_metadata(
        result,
        algorithm=algorithm,
        mode="advanced",
        backend_target="aer_simulator",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "available_devices": ["CPU", "GPU"],
                "actual_execution_target": "aer_simulator",
                "actual_path_class": "aer_primitive",
                "backend_primitives_used": True,
            }
        ),
        backend_context=BackendExecutionContext(
            backend_target="aer_simulator",
            backend_options={"device": "GPU"},
        ),
    )

    capability = result["backend_execution"]["aer_capability"]
    assert capability["status"] == "rejected"
    assert capability["reason"] == f"{algorithm}_aer_gpu_execution_not_verified"


def test_projected_result_metadata_marks_sector_path_local() -> None:
    for algorithm in ("kqd", "qfd"):
        result = {
            "raw_result": {},
            "algorithm_metrics": {
                "matrix_element_summary": {"matrix_element_strategy": "sector_matrix_free"}
            },
        }

        apply_result_metadata(
            result,
            algorithm=algorithm,
            mode="advanced",
            backend_target="aer_simulator",
            chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
            backend_adapter=_adapter(
                {
                    "backend_primitives_used": True,
                    "primitive_family": "qiskit_aer.EstimatorV2",
                }
            ),
            backend_context=BackendExecutionContext(backend_target="aer_simulator"),
        )

        metadata = result["backend_execution"]
        assert metadata["execution_mode"] == "sector_matrix_free"
        assert metadata["aer_simulator_used"] is False
        assert metadata["backend_primitives_used"] is False
        assert metadata["primitive_family"] is None
        assert metadata["actual_execution_target"] == "local_classical"
        assert metadata["actual_path_class"] == "sector_matrix_free"
        assert metadata["fallback_reason"] == f"{algorithm}_uses_local_sector_matrix_free_solver"


def test_kqd_exact_evolution_on_aer_target_reports_local_provenance() -> None:
    result = {
        "raw_result": {},
        "algorithm_metrics": {
            "matrix_element_summary": {
                "matrix_element_strategy": "dense_classical",
                "implemented_evolution_method": "exact_matrix_evolution",
            }
        },
    }

    apply_result_metadata(
        result,
        algorithm="kqd",
        mode="advanced",
        backend_target="aer_simulator",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "resolved_backend_name": "aer_simulator",
                "optimization_level": 3,
                "job_ids": ["stale-aer-job"],
                "pub_count": 1,
                "noise_summary": {
                    "enabled": True,
                    "model_source": "backend_derived",
                    "fingerprint": "requested-noise-profile",
                },
                "transpilation_summary": {"preview": "requested Aer circuit path"},
                "backend_primitives_used": True,
                "primitive_family": "qiskit_aer.EstimatorV2",
            }
        ),
        backend_context=BackendExecutionContext(backend_target="aer_simulator"),
    )

    metadata = result["backend_execution"]
    assert metadata["backend_target"] == "aer_simulator"
    assert metadata["requested_target"] == "aer_simulator"
    assert metadata["requested_resolved_backend_name"] == "aer_simulator"
    assert metadata["resolved_backend_name"] is None
    assert metadata["requested_optimization_level"] == 3
    assert metadata["optimization_level"] is None
    assert "job_ids" not in metadata
    assert "pub_count" not in metadata
    assert metadata["requested_noise_summary"] == {
        "enabled": True,
        "model_source": "backend_derived",
        "fingerprint": "requested-noise-profile",
    }
    assert metadata["noise_summary"] == {"enabled": False}
    assert metadata["execution_mode"] == "exact_matrix_evolution"
    assert metadata["actual_path_class"] == "dense_classical"
    assert metadata["actual_execution_target"] == "local_classical"
    assert metadata["aer_simulator_used"] is False
    assert metadata["backend_primitives_used"] is False
    assert metadata["primitive_family"] is None
    assert metadata["effective_shots"] is None
    assert metadata["actual_noise_applied"] is False
    assert "transpilation_summary" not in metadata


def test_qse_result_metadata_marks_local_reference_without_primitive() -> None:
    result = {
        "raw_result": {},
        "algorithm_metrics": {
            "reference_method": "hf",
            "execution_mode": "sector_matrix_free",
        },
    }

    apply_result_metadata(
        result,
        algorithm="qse",
        mode="advanced",
        backend_target="ibm_runtime",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "resolved_backend_name": "ibm_brisbane",
                "backend_primitives_used": True,
                "primitive_family": "qiskit_ibm_runtime.EstimatorV2",
            }
        ),
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    metadata = result["backend_execution"]
    assert metadata["execution_mode"] == "sector_matrix_free"
    assert metadata["backend_primitives_used"] is False
    assert metadata["primitive_family"] is None
    assert metadata["fallback_reason"] == "qse_local_reference_and_projected_solver"


def test_qse_result_metadata_marks_vqe_reference_backend_use() -> None:
    result = {
        "raw_result": {},
        "algorithm_metrics": {
            "reference_method": "vqe",
            "execution_mode": "dense_exact_emulation",
        },
    }

    apply_result_metadata(
        result,
        algorithm="qse",
        mode="advanced",
        backend_target="ibm_runtime",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "resolved_backend_name": "ibm_brisbane",
                "backend_primitives_used": True,
                "primitive_family": "qiskit_ibm_runtime.EstimatorV2",
            }
        ),
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    metadata = result["backend_execution"]
    assert metadata["execution_mode"] == "qse_dense_exact_emulation"
    assert metadata["actual_execution_target"] == "local_classical"
    assert metadata["backend_primitives_used"] is False
    assert metadata["primitive_family"] is None
    assert metadata["fallback_reason"] == "qse_declared_exact_emulation_reference"


def test_qse_result_metadata_never_claims_measured_reference() -> None:
    result = {
        "raw_result": {},
        "algorithm_metrics": {"reference_method": "vqe"},
    }

    apply_result_metadata(
        result,
        algorithm="qse",
        mode="advanced",
        backend_target="ibm_runtime",
        chemistry_input=ChemistryInput(atoms=[], basis="6-31g"),
        backend_adapter=_adapter(
            {
                "actual_execution_target": "ibm_runtime",
                "backend_primitives_used": True,
                "primitive_family": "qiskit_ibm_runtime.EstimatorV2",
            }
        ),
        backend_context=BackendExecutionContext(backend_target="ibm_runtime"),
    )

    metadata = result["backend_execution"]
    assert metadata["execution_mode"] == "qse_projected_local"
    assert metadata["actual_execution_target"] == "local_classical"
    assert metadata["backend_primitives_used"] is False
    assert metadata["primitive_family"] is None
    assert metadata["execution_scope"] == "local_exact_emulation"
    assert metadata["measured_projected_matrix_elements"] is False


def test_hamiltonian_message_describes_explicit_or_automatic_active_space() -> None:
    assert build_hamiltonian_message(ChemistryInput(atoms=[], active_space=(2, 3))) == (
        "Building Hamiltonian for active_space=2e/3o."
    )
    assert build_hamiltonian_message(ChemistryInput(atoms=[])) == (
        "Building Hamiltonian with automatic active-space selection."
    )
