"""Direct tests for VQE circuit-artifact composition."""

import numpy as np

from worker.chemistry.algorithms.vqe import circuit_artifacts as vqe_circuit_artifacts


class _FakeAnsatz:
    num_parameters = 2

    def assign_parameters(self, values: list[float]) -> tuple[str, list[float]]:
        return ("bound", values)


def test_build_vqe_circuit_artifacts_preserves_reported_and_optimizer_provenance(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        vqe_circuit_artifacts,
        "serialize_circuit_artifact",
        lambda _circuit, **kwargs: kwargs,
    )

    artifacts = vqe_circuit_artifacts.build_vqe_circuit_artifacts(
        ansatz=_FakeAnsatz(),
        ansatz_name="EfficientSU2",
        optimizer_name="COBYLA",
        reps=1,
        optimal_point=np.array([0.1, 0.2]),
        final_point=np.array([0.3, 0.4]),
        reported_energy_source="best_observed_optimizer_evaluation",
    )

    assert [artifact["artifact_id"] for artifact in artifacts] == [
        "vqe.ansatz",
        "vqe.final",
        "vqe.optimizer_final",
    ]
    assert artifacts[1]["label"] == "Best observed VQE circuit"
    assert artifacts[1]["source"] == "best_observed_parameters"
    assert artifacts[2]["source"] == "optimizer_final_parameters"
    assert artifacts[0]["parameters"]["parameter_count"] == 2


def test_build_vqe_circuit_artifacts_omits_duplicate_optimizer_final_point(monkeypatch) -> None:
    monkeypatch.setattr(
        vqe_circuit_artifacts,
        "serialize_circuit_artifact",
        lambda _circuit, **kwargs: kwargs,
    )

    artifacts = vqe_circuit_artifacts.build_vqe_circuit_artifacts(
        ansatz=_FakeAnsatz(),
        ansatz_name="RealAmplitudes",
        optimizer_name="SPSA",
        reps=2,
        optimal_point=np.array([0.1, 0.2]),
        final_point=np.array([0.1, 0.2]),
    )

    assert [artifact["role"] for artifact in artifacts] == ["ansatz", "final"]
    assert artifacts[1]["label"] == "Final VQE circuit"
    assert artifacts[1]["source"] == "optimized_parameters"
