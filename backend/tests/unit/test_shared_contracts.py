"""Tests for service-independent contract ownership."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from app.models.enums import BackendTarget, EasyGoal, RunAlgorithm, RunEventType, RunMode, RunStatus
from app.schemas.run_config import EasyOptions
from app.schemas.run_requests import RunCreate
from app.services.run_config_metadata import get_run_config_metadata

from shared.contracts import DEFAULT_QUEUE_NAME
from shared.contracts.catalog import CATALOG_VERSION, PUBLIC_LIMITS, get_public_catalog
from shared.contracts.identifiers import BackendTarget as SharedBackendTarget
from shared.contracts.identifiers import EasyGoal as SharedEasyGoal
from shared.contracts.identifiers import RunAlgorithm as SharedRunAlgorithm
from shared.contracts.registry_metadata import (
    resolve_ansatz_id,
    resolve_optimizer_id,
    supported_ansatz_aliases,
    supported_ansatz_metadata,
    supported_optimizer_aliases,
    supported_optimizer_metadata,
)


def _identifier_fixture() -> dict[str, Any]:
    fixture_path = Path(__file__).resolve().parents[3] / "shared/contracts/identifier-fixtures.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _run_request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "molecule_id": str(UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")),
        "algorithm": RunAlgorithm.VQE.value,
        "mode": RunMode.EASY.value,
        "backend_target": BackendTarget.STATEVECTOR.value,
    }
    payload.update(overrides)
    return payload


def test_backend_enum_exports_are_shared_contracts():
    assert RunStatus.__module__ == "shared.contracts.identifiers"
    assert RunAlgorithm.__module__ == "shared.contracts.identifiers"
    assert BackendTarget.__module__ == "shared.contracts.identifiers"
    assert RunEventType.__module__ == "shared.contracts.identifiers"


def test_backend_identifier_membership_matches_shared_contract():
    assert {item.value for item in RunAlgorithm} == {item.value for item in SharedRunAlgorithm}
    assert {item.value for item in BackendTarget} == {item.value for item in SharedBackendTarget}
    assert {item.value for item in EasyGoal} == {item.value for item in SharedEasyGoal}


def test_shared_identifiers_match_cross_language_fixture():
    fixture = _identifier_fixture()

    assert {item.value for item in RunStatus} == set(fixture["run_statuses"])
    assert {item.value for item in RunAlgorithm} == set(fixture["algorithms"])
    assert {item.value for item in RunMode} == {"easy", "advanced"}
    assert {item.value for item in BackendTarget} == set(fixture["backend_targets"])
    assert {item.value for item in EasyGoal} == set(fixture["easy_goals"])
    assert {item.value for item in RunEventType} == set(fixture["run_event_types"])


def test_backend_acceptance_sets_match_shared_contract():
    accepted_algorithms = {
        RunCreate.model_validate(_run_request_payload(algorithm=algorithm.value)).algorithm.value
        for algorithm in SharedRunAlgorithm
    }
    accepted_backends = {
        RunCreate.model_validate(
            _run_request_payload(backend_target=backend_target.value)
        ).backend_target.value
        for backend_target in SharedBackendTarget
    }
    accepted_goals = {
        EasyOptions.model_validate({"goal": goal.value}).goal.value for goal in SharedEasyGoal
    }

    assert accepted_algorithms == {algorithm.value for algorithm in SharedRunAlgorithm}
    assert accepted_backends == {backend.value for backend in SharedBackendTarget}
    assert accepted_goals == {goal.value for goal in SharedEasyGoal}


def test_backend_metadata_exposes_shared_identifier_membership():
    metadata = get_run_config_metadata()

    assert {algorithm.value for algorithm in metadata.algorithms} == {
        algorithm.value for algorithm in SharedRunAlgorithm
    }
    assert {backend.value for backend in metadata.backend_targets} == {
        backend.value for backend in SharedBackendTarget
    }
    assert {goal.value for goal in metadata.easy_goals} == {goal.value for goal in SharedEasyGoal}
    assert [
        preset.model_dump(mode="json") for preset in metadata.easy_goal_presets
    ] == get_public_catalog()["easy_goal_presets"]


def test_shared_registry_metadata_is_defensive():
    ansatzes = supported_ansatz_metadata()
    optimizers = supported_optimizer_metadata()

    ansatzes["efficientsu2"]["aliases"].clear()
    optimizers["COBYLA"]["allowed_options"].clear()

    assert supported_ansatz_metadata()["efficientsu2"]["aliases"]
    assert supported_optimizer_metadata()["COBYLA"]["allowed_options"]
    assert DEFAULT_QUEUE_NAME == "quantum"


def test_shared_registry_aliases_classify_canonical_and_legacy_names():
    ansatz_aliases = supported_ansatz_aliases()
    optimizer_aliases = supported_optimizer_aliases()

    assert ansatz_aliases["efficientsu2"] == "efficientsu2"
    assert ansatz_aliases["efficient_su2"] == "efficientsu2"
    assert ansatz_aliases["real_amplitudes"] == "realamplitudes"
    assert optimizer_aliases["L-BFGS-B"] == "L_BFGS_B"
    assert optimizer_aliases["COBYLA"] == "COBYLA"
    assert resolve_ansatz_id(" Efficient_Su2 ") == "efficientsu2"
    assert resolve_ansatz_id("Real-Amplitudes") == "realamplitudes"
    assert resolve_optimizer_id("l-bfgs-b") == "L_BFGS_B"
    assert resolve_ansatz_id("unknown_ansatz") is None


def test_public_catalog_is_complete_and_defensive():
    catalog = get_public_catalog()

    assert catalog["catalog_version"] == CATALOG_VERSION
    assert catalog["algorithms"] == ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"]
    assert catalog["backend_targets"] == ["statevector", "aer_simulator", "ibm_runtime"]
    assert catalog["easy_goals"] == ["fastest", "balanced", "best_accuracy"]
    assert catalog["easy_goal_presets"] == [
        {"goal": "fastest", "label": "5.0 mHa", "chemical_accuracy_target_ha": 5e-3},
        {"goal": "balanced", "label": "1.6 mHa", "chemical_accuracy_target_ha": 1.6e-3},
        {"goal": "best_accuracy", "label": "0.5 mHa", "chemical_accuracy_target_ha": 5e-4},
    ]
    assert catalog["recommendations"]["qse"]["balanced"]["max_subspace_dim"] == 8
    assert catalog["limits"]["advanced_config.max_iterations"]["maximum"] == 5000

    catalog["limits"]["advanced_config.max_iterations"]["maximum"] = 1
    catalog["defaults"]["ansatz_name"] = "changed"
    catalog["recommendations"]["qse"]["balanced"]["max_subspace_dim"] = 1
    fresh_catalog = get_public_catalog()
    assert fresh_catalog["limits"] == PUBLIC_LIMITS
    assert fresh_catalog["defaults"]["ansatz_name"] == "NumberPreserving"
    assert fresh_catalog["recommendations"]["qse"]["balanced"]["max_subspace_dim"] == 8


def test_public_catalog_matches_cross_language_fixture():
    fixture = _identifier_fixture()
    catalog_keys = {
        "catalog_version",
        "algorithms",
        "backend_targets",
        "easy_goals",
        "easy_goal_presets",
        "ansatzes",
        "optimizers",
        "limits",
        "defaults",
        "capabilities",
        "recommendations",
    }

    assert {key: fixture[key] for key in catalog_keys} == get_public_catalog()


def test_metadata_response_preserves_registry_aliases_and_options():
    metadata = get_run_config_metadata()
    shared_ansatzes = supported_ansatz_metadata()
    shared_optimizers = supported_optimizer_metadata()

    ansatz_by_worker_id = {
        choice.metadata["canonical_worker_id"]: choice for choice in metadata.ansatzes
    }
    assert set(ansatz_by_worker_id) == set(shared_ansatzes)
    for worker_id, shared in shared_ansatzes.items():
        choice = ansatz_by_worker_id[worker_id]
        assert choice.aliases == shared["aliases"]
        assert choice.label == shared["label"]
        assert choice.metadata["default_reps"] == shared["default_reps"]
        assert choice.supported_algorithms == [RunAlgorithm.VQE, RunAlgorithm.QSE]

    optimizer_by_id = {choice.id: choice for choice in metadata.optimizers}
    assert set(optimizer_by_id) == set(shared_optimizers)
    for optimizer_id, shared in shared_optimizers.items():
        choice = optimizer_by_id[optimizer_id]
        assert choice.aliases == shared["aliases"]
        assert choice.metadata["kind"] == shared["kind"]
        assert choice.metadata["scipy_method"] == shared["scipy_method"]
        assert choice.metadata["allowed_options"] == shared["allowed_options"]
        assert (
            choice.metadata["supports_max_function_evaluations"]
            == shared["supports_max_function_evaluations"]
        )
