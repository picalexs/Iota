"""Unit tests for pure worker execution-config normalization."""

from uuid import uuid4

from worker.jobs.execution_config import (
    _backend_options_from_config,
    _estimate_seed_from_snapshot,
    _extract_run_context,
    _resolve_basis_set,
)


def test_extract_run_context_defaults_missing_snapshot() -> None:
    context = _extract_run_context(None)

    assert context.algorithm == "vqe"
    assert context.mode == "advanced"
    assert context.backend_target == "statevector"
    assert context.config_snapshot == {}


def test_extract_run_context_expands_easy_mode_and_legacy_backend() -> None:
    context = _extract_run_context(
        {
            "config_snapshot": {
                "mode": "easy",
                "backend": "ibm_brisbane",
                "basis_set": "6-31g",
            },
            "metadata": {
                "easy_mode": {
                    "expanded_advanced_config": {
                        "algorithm": "vqe",
                        "max_iterations": 3,
                    }
                }
            },
        }
    )

    assert context.algorithm == "vqe"
    assert context.mode == "easy"
    assert context.backend_target == "ibm_runtime"
    assert context.config_snapshot["max_iterations"] == 3
    assert context.config_snapshot["basis_set"] == "6-31g"


def test_estimate_seed_uses_latest_telemetry_before_initial_history() -> None:
    seconds, confidence = _estimate_seed_from_snapshot(
        {
            "latest_estimate": {
                "source": "telemetry",
                "estimated_seconds_per_iteration": 1.5,
                "confidence": 0.4,
            },
            "initial_estimate": {
                "source": "history",
                "estimated_seconds_per_iteration": 4.0,
                "confidence": 0.9,
            },
        }
    )

    assert seconds == 1.5
    assert confidence == 0.4


def test_backend_options_fill_persisted_profile_without_overwriting_explicit_value() -> None:
    profile_id = uuid4()

    assert _backend_options_from_config({}, credential_profile_id=profile_id) == {
        "credential_profile_id": str(profile_id)
    }
    assert _backend_options_from_config(
        {"backend_options": {"credential_profile_id": "saved-profile"}},
        credential_profile_id=profile_id,
    ) == {"credential_profile_id": "saved-profile"}
    assert _resolve_basis_set({"basis_set_override": "  6-31g  "}, "sto-3g") == "6-31g"
