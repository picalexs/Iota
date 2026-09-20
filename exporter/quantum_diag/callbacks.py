"""Iteration-level metrics collection callback."""

from __future__ import annotations

from typing import Optional
import numpy as np


class IterationCallback:
    """Callback to track iteration metrics during VQE optimization.

    Stores energy values, iteration counts, and parameters at each step
    to build convergence history.
    """

    def __init__(self, reference_energy: float) -> None:
        """Initialize callback with reference energy.

        Args:
            reference_energy: Reference energy (e.g., ground truth) for comparison.
        """
        self.reference_energy = reference_energy
        self.iteration_history: list[int] = []
        self.energy_history: list[float] = []
        self.parameter_history: list[np.ndarray] = []

    def __call__(
        self,
        iteration: int,
        parameters: np.ndarray,
        energy: float,
        metadata: Optional[dict] = None,
    ) -> None:
        """Log iteration metrics.

        Args:
            iteration: Current iteration number.
            parameters: Current parameter values.
            energy: Current energy value.
            metadata: Optional metadata dictionary.
        """
        self.iteration_history.append(iteration)
        self.energy_history.append(energy)
        self.parameter_history.append(parameters.copy())

    def convergence_reached(self, tolerance: float = 1e-3) -> bool:
        """Check if convergence criterion is met.

        Checks if last 3 energy values are within tolerance of each other.

        Args:
            tolerance: Energy difference tolerance.

        Returns:
            True if last 3 energies are within tolerance, False otherwise.
        """
        if len(self.energy_history) < 3:
            return False

        last_3 = self.energy_history[-3:]
        energy_range = max(last_3) - min(last_3)
        return energy_range <= tolerance
