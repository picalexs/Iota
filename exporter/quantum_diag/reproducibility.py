"""Seed management and experiment artifact handling."""

from __future__ import annotations

import json
import numpy as np
from dataclasses import dataclass, asdict
from typing import Any

from quantum_diag.config import ExperimentSpec
from quantum_diag.metrics import BenchmarkMetrics


class SeedManager:
    """Manager for reproducible random number generation.

    Ensures deterministic behavior across Python, NumPy, and random module.
    """

    _seed: int | None = None

    def set_global_seed(self, seed: int) -> None:
        """Set global seed for reproducibility.

        Args:
            seed: Random seed value.
        """
        self._seed = seed
        np.random.seed(seed)
        import random
        random.seed(seed)

    def get_seed(self) -> int | None:
        """Get current seed value.

        Returns:
            Current seed or None if not set.
        """
        return self._seed


@dataclass
class ExperimentArtifact:
    """Bundle of experiment configuration, metrics, and metadata.

    Attributes:
        config: ExperimentSpec with configuration.
        metrics: BenchmarkMetrics with results.
        metadata: Dictionary with additional metadata (e.g., timestamp, version).
    """

    config: ExperimentSpec
    metrics: BenchmarkMetrics
    metadata: dict[str, Any]


def artifact_to_json(artifact: ExperimentArtifact) -> str:
    """Export artifact to JSON string.

    Args:
        artifact: ExperimentArtifact to serialize.

    Returns:
        JSON string containing config, metrics, and metadata.
    """
    data = {
        "config": artifact.config.to_dict(),
        "metrics": artifact.metrics.to_dict(),
        "metadata": artifact.metadata,
    }
    return json.dumps(data, default=str)


def artifact_from_json(json_str: str) -> ExperimentArtifact:
    """Import artifact from JSON string.

    Args:
        json_str: JSON string containing artifact data.

    Returns:
        ExperimentArtifact reconstructed from JSON.
    """
    data = json.loads(json_str)
    config = ExperimentSpec(**data["config"])
    metrics = BenchmarkMetrics(**data["metrics"])
    metadata = data.get("metadata", {})
    return ExperimentArtifact(config=config, metrics=metrics, metadata=metadata)
