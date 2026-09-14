"""Historical-run matching used to improve initial runtime estimates."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, selectinload

from app.models.enums import BackendTarget, RunAlgorithm, RunMode, RunStatus
from app.models.molecule import Molecule
from app.models.run import Run
from app.models.run_result import RunResult
from app.schemas.run_requests import RunCreate

from . import features, similarity

_ESTIMATION_HISTORY_LIMIT = 200
_ESTIMATION_MAX_MATCHES = 12
_HISTORY_MIN_SIMILARITY = 0.18


def history_algorithm_config(run: Run) -> dict[str, Any]:
    config_snapshot = features.as_dict(run.config_json)
    if run.mode == RunMode.EASY:
        easy_mode_metadata = features.as_dict(features.as_dict(run.run_metadata).get("easy_mode"))
        expanded = easy_mode_metadata.get("expanded_advanced_config")
        if isinstance(expanded, dict):
            config_payload = dict(expanded)
            catalog_version = easy_mode_metadata.get("catalog_version")
            if isinstance(catalog_version, str) and catalog_version.strip():
                config_payload.setdefault(
                    "easy_mode_catalog_version",
                    catalog_version.strip().lower(),
                )
            basis_override = config_snapshot.get("basis_set_override") or config_snapshot.get(
                "basis_set"
            )
            if isinstance(basis_override, str) and basis_override.strip():
                config_payload.setdefault("basis_set_override", basis_override.strip())
            return config_payload

    advanced_config = config_snapshot.get("advanced_config")
    if isinstance(advanced_config, dict):
        return dict(advanced_config)
    return dict(config_snapshot)


def history_backend_options(run: Run) -> dict[str, Any]:
    config_snapshot = features.as_dict(run.config_json)
    backend_options = config_snapshot.get("backend_options")
    return dict(backend_options) if isinstance(backend_options, dict) else {}


def history_noise_profile(run: Run) -> dict[str, Any] | None:
    config_snapshot = features.as_dict(run.config_json)
    noise_profile = config_snapshot.get("noise_profile")
    return dict(noise_profile) if isinstance(noise_profile, dict) else None


def history_runtime_seconds(run: Run) -> float | None:
    metadata = features.as_dict(run.run_metadata)
    runtime_seconds = metadata.get("runtime_seconds")
    if isinstance(runtime_seconds, bool) or not isinstance(runtime_seconds, (int, float)):
        return None
    numeric = float(runtime_seconds)
    return numeric if math.isfinite(numeric) and numeric >= 0.0 else None


def history_completed_iterations(run: Run) -> int | None:
    latest_estimate = features.as_dict(run.latest_estimate)
    total_iterations = features.coerce_non_negative_int(
        latest_estimate.get("estimated_total_iterations")
    )
    remaining_iterations = features.coerce_non_negative_int(
        latest_estimate.get("estimated_remaining_iterations")
    )
    if total_iterations is not None and remaining_iterations is not None:
        completed_iterations = max(total_iterations - remaining_iterations, 0)
        if completed_iterations > 0:
            return completed_iterations
        if run.status == RunStatus.COMPLETED and total_iterations > 0:
            return total_iterations

    if run.result is not None and run.result.iterations > 0:
        return int(run.result.iterations)

    initial_estimate = features.as_dict(run.initial_estimate)
    initial_total = features.coerce_non_negative_int(
        initial_estimate.get("estimated_total_iterations")
    )
    if run.status == RunStatus.COMPLETED and initial_total is not None and initial_total > 0:
        return initial_total

    return None


def history_quality_weight(
    run: Run, completed_iterations: int, total_iterations: int | None
) -> float:
    if run.status == RunStatus.COMPLETED:
        base = 1.0
    elif run.status == RunStatus.FAILED:
        base = 0.6
    else:
        base = 0.45

    if total_iterations is None or total_iterations <= 0:
        return base

    coverage = min(max(completed_iterations / total_iterations, 0.0), 1.0)
    return base * (0.6 + 0.4 * coverage)


def history_recency_weight(run: Run) -> float:
    created_at = run.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    else:
        created_at = created_at.astimezone(UTC)
    age_days = max((datetime.now(UTC) - created_at).total_seconds() / 86_400.0, 0.0)
    return 0.75 + 0.25 * math.exp(-age_days / 45.0)


def request_feature_set(
    *,
    run_in: RunCreate,
    molecule: Molecule | None,
    config_payload: dict[str, Any],
    backend_target: BackendTarget,
) -> tuple[dict[str, float], dict[str, str]]:
    return features.build_feature_set(
        mode=run_in.mode,
        backend_target=backend_target,
        basis_set=run_in.effective_basis_set("sto-3g"),
        molecule=molecule,
        config_payload=config_payload,
        backend_options=run_in.backend_options.model_dump(mode="json"),
        noise_profile=(
            run_in.noise_profile.model_dump(mode="json") if run_in.noise_profile else None
        ),
    )


def history_match(
    historical_run: Run,
    *,
    request_numeric: dict[str, float],
    request_categorical: dict[str, str],
) -> tuple[float, float, float, int | None] | None:
    if historical_run.status != RunStatus.COMPLETED:
        return None

    runtime_seconds = history_runtime_seconds(historical_run)
    completed_iterations = history_completed_iterations(historical_run)
    if runtime_seconds is None or completed_iterations is None or completed_iterations <= 0:
        return None

    history_numeric, history_categorical = features.build_feature_set(
        mode=historical_run.mode or RunMode.ADVANCED,
        backend_target=historical_run.backend_target or BackendTarget.STATEVECTOR,
        basis_set=historical_run.basis_set or "sto-3g",
        molecule=historical_run.molecule,
        config_payload=history_algorithm_config(historical_run),
        backend_options=history_backend_options(historical_run),
        noise_profile=history_noise_profile(historical_run),
    )
    if not similarity.passes_scale_guard(request_numeric, history_numeric):
        return None
    if not similarity.passes_version_guard(request_categorical, history_categorical):
        return None
    if not similarity.passes_backend_guard(request_categorical, history_categorical):
        return None

    score = similarity.similarity_score(
        request_numeric,
        request_categorical,
        history_numeric,
        history_categorical,
    )
    if score < _HISTORY_MIN_SIMILARITY:
        return None

    total_iterations = features.coerce_non_negative_int(
        features.as_dict(historical_run.latest_estimate).get("estimated_total_iterations")
    )
    weight = score
    weight *= history_quality_weight(historical_run, completed_iterations, total_iterations)
    weight *= history_recency_weight(historical_run)
    return weight, runtime_seconds / completed_iterations, score, completed_iterations


def summarize_history_matches(
    matches: list[tuple[float, float, float, int | None]],
) -> tuple[float | None, float | None, int | None, dict[str, Any]]:
    if not matches:
        return None, None, None, {}

    matches.sort(key=lambda item: item[0], reverse=True)
    selected = matches[:_ESTIMATION_MAX_MATCHES]
    total_weight = sum(weight for weight, _, _, _ in selected)
    if total_weight <= 0.0:
        return None, None, None, {}

    weighted_seconds_per_iteration = (
        sum(weight * seconds_per_iteration for weight, seconds_per_iteration, _, _ in selected)
        / total_weight
    )
    weighted_similarity = (
        sum(weight * similarity for weight, _, similarity, _ in selected) / total_weight
    )
    match_count = len(selected)
    support = min(total_weight / 2.5, 1.0)
    confidence = min(
        0.87,
        0.42 + 0.28 * weighted_similarity + 0.08 * min(match_count / 4.0, 1.0) + 0.09 * support,
    )
    completed_iteration_matches = [
        (weight, completed_iterations)
        for weight, _, _, completed_iterations in selected
        if completed_iterations is not None
    ]
    expected_total_iterations: int | None = None
    if completed_iteration_matches:
        completed_iteration_weight = sum(weight for weight, _ in completed_iteration_matches)
        if completed_iteration_weight > 0.0:
            expected_total_iterations = max(
                1,
                int(
                    round(
                        sum(
                            weight * completed_iterations
                            for weight, completed_iterations in completed_iteration_matches
                        )
                        / completed_iteration_weight
                    )
                ),
            )
    return (
        weighted_seconds_per_iteration,
        confidence,
        expected_total_iterations,
        {
            "historical_match_count": match_count,
            "historical_similarity": round(weighted_similarity, 4),
            "historical_weight": round(total_weight, 4),
            **(
                {"historical_completed_iterations": expected_total_iterations}
                if expected_total_iterations is not None
                else {}
            ),
        },
    )


def infer_history_seconds_per_iteration(
    *,
    db: Session,
    run_in: RunCreate,
    molecule: Molecule | None,
    algorithm: RunAlgorithm,
    config_payload: dict[str, Any],
    backend_target: BackendTarget,
) -> tuple[float | None, float | None, int | None, dict[str, Any]]:
    request_numeric, request_categorical = request_feature_set(
        run_in=run_in,
        molecule=molecule,
        config_payload=config_payload,
        backend_target=backend_target,
    )

    matches: list[tuple[float, float, float, int | None]] = []
    for historical_run in db.scalars(history_runs_statement(algorithm)).all():
        match = history_match(
            historical_run,
            request_numeric=request_numeric,
            request_categorical=request_categorical,
        )
        if match is not None:
            matches.append(match)
    return summarize_history_matches(matches)


def history_runs_statement(algorithm: RunAlgorithm):
    return (
        select(Run)
        .options(
            load_only(
                Run.id,
                Run.algorithm,
                Run.status,
                Run.mode,
                Run.backend_target,
                Run.config_json,
                Run.basis_set,
                Run.run_metadata,
                Run.initial_estimate,
                Run.latest_estimate,
                Run.created_at,
            ),
            selectinload(Run.molecule).load_only(
                Molecule.id,
                Molecule.atoms,
                Molecule.charge,
                Molecule.multiplicity,
                Molecule.active_space,
            ),
            selectinload(Run.result).load_only(
                RunResult.run_id,
                RunResult.iterations,
            ),
        )
        .where(
            Run.algorithm == algorithm,
            Run.status.in_((RunStatus.COMPLETED,)),
        )
        .order_by(Run.created_at.desc())
        .limit(_ESTIMATION_HISTORY_LIMIT)
    )


# Private aliases preserve the old flat module names during the migration.
_history_algorithm_config = history_algorithm_config
_history_backend_options = history_backend_options
_history_noise_profile = history_noise_profile
_history_runtime_seconds = history_runtime_seconds
_history_completed_iterations = history_completed_iterations
_history_quality_weight = history_quality_weight
_history_recency_weight = history_recency_weight
_request_feature_set = request_feature_set
_history_match = history_match
_summarize_history_matches = summarize_history_matches
_history_runs_statement = history_runs_statement
_infer_history_seconds_per_iteration = infer_history_seconds_per_iteration


__all__ = ["history_runs_statement", "infer_history_seconds_per_iteration"]
