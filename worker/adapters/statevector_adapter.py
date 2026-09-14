"""Statevector backend adapter implementation."""

from __future__ import annotations

from typing import Any

from worker.adapters.base import AdapterCapabilities, BackendAdapter, BackendExecutionContext


class StatevectorAdapter(BackendAdapter):
    """Active local adapter used for deterministic rollout phases."""

    _caps = AdapterCapabilities(
        backend_target="statevector",
        enabled=True,
        supports_noise_profile=False,
    )

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._caps

    def create_estimator(self, context: BackendExecutionContext | None = None) -> Any:
        del context
        from qiskit.primitives import StatevectorEstimator

        return StatevectorEstimator()

    def create_sampler(self, context: BackendExecutionContext | None = None) -> Any:
        del context
        from qiskit.primitives import StatevectorSampler

        return StatevectorSampler()

    def execution_metadata(self, context: BackendExecutionContext | None = None) -> dict[str, Any]:
        return {
            "backend_target": self.capabilities.backend_target,
            "requested_target": self.capabilities.backend_target,
            "actual_execution_target": "statevector",
            "execution_mode": "statevector_exact",
            "actual_path_class": "statevector_exact",
            "resolved_backend_name": "statevector",
            "selection_policy": context.selection_policy if context else "requested",
            "backend_primitives_used": True,
            "primitive_family": "qiskit_statevector",
            "shots": None,
            "requested_shots": context.requested_shots if context else None,
            "effective_shots": None,
            "requested_estimator_precision": (
                context.requested_estimator_precision if context else None
            ),
            "effective_estimator_precision": None,
            "measurement_mode": "exact",
            "uncertainty_policy": "statevector_exact",
            "noise_summary": {"enabled": False},
            "simulator_method": "statevector",
        }
