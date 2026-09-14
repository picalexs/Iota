"""VQE-specific circuit-artifact composition for the algorithm package."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from worker.chemistry.circuit_artifacts import serialize_circuit_artifact

logger = logging.getLogger(__name__)


def build_vqe_circuit_artifacts(
    *,
    ansatz: Any,
    ansatz_name: str,
    optimizer_name: str,
    reps: int,
    optimal_point: np.ndarray,
    final_point: np.ndarray | None = None,
    reported_energy_source: str | None = None,
) -> list[dict[str, Any]]:
    """Build typed ansatz, reported, and optional optimizer-final artifacts."""
    parameter_count = int(getattr(ansatz, "num_parameters", 0) or 0)
    artifacts = [
        serialize_circuit_artifact(
            ansatz,
            artifact_id="vqe.ansatz",
            algorithm="vqe",
            role="ansatz",
            phase="optimization",
            representative=False,
            label=f"{ansatz_name} ansatz",
            parameters={
                "ansatz_name": ansatz_name,
                "optimizer_name": optimizer_name,
                "reps": reps,
                "parameter_count": parameter_count,
                "bound": False,
            },
        )
    ]

    def _bind_circuit(parameter_values: np.ndarray, *, label: str) -> Any:
        try:
            return ansatz.assign_parameters(parameter_values.tolist())
        except Exception:
            logger.debug("Failed to bind %s VQE circuit artifact", label, exc_info=True)
            return ansatz

    reported_label = (
        "Best observed VQE circuit"
        if reported_energy_source == "best_observed_optimizer_evaluation"
        else "Final VQE circuit"
    )
    reported_source = (
        "best_observed_parameters"
        if reported_energy_source == "best_observed_optimizer_evaluation"
        else "optimized_parameters"
    )
    final_circuit = _bind_circuit(optimal_point, label="reported")

    artifacts.append(
        serialize_circuit_artifact(
            final_circuit,
            artifact_id="vqe.final",
            algorithm="vqe",
            role="final",
            phase="optimization",
            representative=True,
            label=reported_label,
            source=reported_source,
            parameters={
                "ansatz_name": ansatz_name,
                "optimizer_name": optimizer_name,
                "reps": reps,
                "parameter_count": parameter_count,
                "bound": True,
            },
        )
    )

    if final_point is not None and not np.allclose(
        optimal_point, final_point, atol=1e-12, rtol=0.0
    ):
        optimizer_final_circuit = _bind_circuit(final_point, label="optimizer final")
        artifacts.append(
            serialize_circuit_artifact(
                optimizer_final_circuit,
                artifact_id="vqe.optimizer_final",
                algorithm="vqe",
                role="optimizer_final",
                phase="optimization",
                label="Last optimizer circuit",
                source="optimizer_final_parameters",
                parameters={
                    "ansatz_name": ansatz_name,
                    "optimizer_name": optimizer_name,
                    "reps": reps,
                    "parameter_count": parameter_count,
                    "bound": True,
                },
            )
        )
    return artifacts
