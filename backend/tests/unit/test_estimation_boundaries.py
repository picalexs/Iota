"""Tests for the focused run-estimation module boundaries."""

from __future__ import annotations

from app.models.enums import BackendTarget, RunMode
from app.services.estimation.features import build_feature_set
from app.services.estimation.history import history_runs_statement
from app.services.estimation.similarity import (
    passes_backend_guard,
    passes_scale_guard,
    passes_version_guard,
    similarity_score,
)
from app.services.run_estimation import (
    build_initial_estimate_for_run_request,
    estimate_total_iterations,
)


def test_pure_estimation_responsibilities_live_in_focused_modules() -> None:
    assert build_feature_set.__module__ == "app.services.estimation.features"
    assert similarity_score.__module__ == "app.services.estimation.similarity"
    assert history_runs_statement.__module__ == "app.services.estimation.history"
    assert build_initial_estimate_for_run_request.__module__ == "app.services.run_estimation"
    assert estimate_total_iterations.__module__ == "app.services.run_estimation"


def test_feature_extraction_ignores_volatile_values() -> None:
    numeric, categorical = build_feature_set(
        mode=RunMode.ADVANCED,
        backend_target=BackendTarget.STATEVECTOR,
        basis_set=" STO-3G ",
        molecule=None,
        config_payload={"max_iterations": 12, "token": "must-not-match"},
        backend_options={"backend_name": "local", "url": "https://secret.invalid"},
        noise_profile=None,
    )

    assert categorical["basis_set"] == "sto-3g"
    assert numeric["config.max_iterations"] == 12.0
    assert "config.token" not in categorical
    assert "backend_options.url" not in categorical


def test_similarity_score_is_one_for_matching_feature_sets() -> None:
    numeric = {"molecule.num_qubits": 4.0, "config.max_iterations": 12.0}
    categorical = {"backend_target": "statevector", "mode": "advanced"}

    assert similarity_score(numeric, categorical, numeric, categorical) == 1.0


def test_similarity_guards_reject_unsafe_history_matches() -> None:
    assert not passes_backend_guard(
        {"backend_target": "ibm_runtime"},
        {"backend_target": "statevector"},
    )
    assert not passes_scale_guard(
        {"molecule.num_qubits": 4.0},
        {"molecule.num_qubits": 16.0},
    )
    assert not passes_version_guard(
        {"config.easy_mode_catalog_version": "v2"},
        {"config.easy_mode_catalog_version": "v1"},
    )
