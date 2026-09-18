"""VQE objective bookkeeping and progress telemetry for the algorithm package."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from worker.chemistry.algorithms.vqe.callbacks import _emit_progress_event
from worker.chemistry.progress import ProgressCallback


class FunctionEvaluationLimitReached(RuntimeError):
    """Raised when VQE objective calls reach the configured cap."""


@dataclass
class VQEObjectiveState:
    """Track VQE objective evaluations independently from numerical execution."""

    energy_evaluator: Callable[[np.ndarray], float | tuple[float, float | None]]
    progress_callback: ProgressCallback | None
    ansatz_name: str
    optimizer_name: str
    optimizer_kind: str
    max_iterations: int
    max_function_evaluations: int | None
    parameter_count: int
    num_qubits: int
    shots: int | None = None
    convergence_trace: list[float] = field(default_factory=list)
    standard_error_trace: list[float | None] = field(default_factory=list)
    evaluation_count: int = 0
    previous_energy: float | None = None
    best_energy: float | None = None
    best_point: np.ndarray | None = None
    iter_start: list[float] = field(default_factory=lambda: [time.monotonic()])
    started_at: float = field(default_factory=time.monotonic)
    final_reevaluation_count: int = 0
    optimizer_started_at: float | None = None
    optimizer_finished_at: float | None = None

    def __call__(self, parameter_values: np.ndarray) -> float:
        if (
            self.max_function_evaluations is not None
            and self.evaluation_count >= self.max_function_evaluations
        ):
            raise FunctionEvaluationLimitReached(
                f"VQE reached max_function_evaluations={self.max_function_evaluations}"
            )
        observation = self.energy_evaluator(parameter_values)
        standard_error: float | None = None
        if isinstance(observation, tuple) and len(observation) == 2:
            raw_energy, raw_standard_error = observation
            if raw_standard_error is not None:
                standard_error = float(raw_standard_error)
                if not np.isfinite(standard_error) or standard_error < 0.0:
                    standard_error = None
        else:
            raw_energy = observation
        energy = float(raw_energy)
        if not np.isfinite(energy):
            raise ValueError("VQE objective returned a non-finite energy")
        self._record_evaluation(energy, parameter_values, standard_error=standard_error)
        return energy

    def _record_evaluation(
        self,
        energy: float,
        parameter_values: np.ndarray,
        *,
        standard_error: float | None = None,
    ) -> None:
        self.evaluation_count += 1
        self.convergence_trace.append(float(energy))
        self.standard_error_trace.append(standard_error)
        if self.best_energy is None or float(energy) < self.best_energy:
            self.best_energy = float(energy)
            self.best_point = np.asarray(parameter_values, dtype=float).copy()
        self.previous_energy = _emit_progress_event(
            progress_callback=self.progress_callback,
            evaluation_count=self.evaluation_count,
            previous_energy=self.previous_energy,
            iter_start=self.iter_start,
            ansatz_name=self.ansatz_name,
            optimizer_name=self.optimizer_name,
            optimizer_kind=self.optimizer_kind,
            max_iterations=self.max_iterations,
            max_function_evaluations=self.max_function_evaluations,
            parameter_count=self.parameter_count,
            num_qubits=self.num_qubits,
            energy=energy,
            parameter_values=parameter_values,
        )

    def wall_time_seconds(self) -> float:
        """Return elapsed wall time for this objective state."""
        return max(0.0, time.monotonic() - self.started_at)
