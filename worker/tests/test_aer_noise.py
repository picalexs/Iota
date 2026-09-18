from types import SimpleNamespace

import pytest

from worker.adapters.aer_noise import (
    normalize_noise_profile,
    resolve_aer_noise_profile,
)
from worker.exceptions import NoiseConfigurationError


class _FakeNoiseModel:
    basis_gates = ["rz", "sx", "x", "cx"]

    def to_dict(self):
        return {"basis_gates": list(self.basis_gates), "errors": []}

    @classmethod
    def from_backend(cls, backend, **kwargs):
        cls.backend = backend
        cls.kwargs = kwargs
        return cls()


def test_backend_derived_noise_uses_live_reference_temperature_and_topology(monkeypatch) -> None:
    backend = SimpleNamespace(
        name="ibm_test",
        backend_version="1.2",
        coupling_map=[(0, 1), (1, 2)],
    )
    calls: list[tuple[str, dict[str, object]]] = []

    def load_backend(name, options):
        calls.append((name, dict(options)))
        return backend

    monkeypatch.setattr("qiskit_aer.noise.NoiseModel", _FakeNoiseModel)

    resolved = resolve_aer_noise_profile(
        {
            "source": "backend_derived",
            "reference_backend": "ibm_test",
            "temperature_mk": 18.0,
        },
        {"token": "secret", "instance": "instance"},
        backend_loader=load_backend,
    )

    assert calls == [("ibm_test", {"token": "secret", "instance": "instance"})]
    assert _FakeNoiseModel.kwargs == {
        "gate_error": True,
        "readout_error": True,
        "thermal_relaxation": True,
        "temperature": 18.0,
    }
    assert resolved.simulator_options()["noise_model"] is resolved.noise_model
    assert resolved.simulator_options()["basis_gates"] == ["rz", "sx", "x", "cx"]
    assert resolved.simulator_options()["coupling_map"] == [[0, 1], [1, 2]]
    assert resolved.summary["requested_reference_backend"] == "ibm_test"
    assert resolved.summary["resolved_reference_backend"] == "ibm_test"
    assert resolved.summary["temperature_mk"] == 18.0
    assert resolved.summary["backend_version"] == "1.2"
    assert len(resolved.summary["model_fingerprint_sha256"]) == 64
    assert "secret" not in str(resolved.summary)


def test_backend_derived_noise_rejects_simulator_reference() -> None:
    with pytest.raises(NoiseConfigurationError, match="not a simulator"):
        normalize_noise_profile(
            {"source": "backend_derived", "reference_backend": "aer_simulator"}
        )


def test_custom_zero_depolarizing_profile_is_ideal() -> None:
    resolved = resolve_aer_noise_profile(
        {"source": "custom_preset", "preset": "depolarizing_cx", "strength": 0.0}
    )

    assert resolved.noise_model is None
    assert resolved.summary["enabled"] is False
    assert resolved.summary["strength"] == 0.0


def test_custom_readout_profile_preserves_asymmetric_probabilities() -> None:
    resolved = resolve_aer_noise_profile(
        {
            "source": "custom_preset",
            "preset": "readout_bias",
            "p01": 0.02,
            "p10": 0.07,
        }
    )

    assert resolved.summary["p01"] == 0.02
    assert resolved.summary["p10"] == 0.07
    assert resolved.noise_model is not None
    assert resolved.noise_model.to_dict()["errors"][0]["operations"] == ["measure"]


def test_custom_profile_rejects_parameters_for_another_preset() -> None:
    with pytest.raises(NoiseConfigurationError, match="requires exactly"):
        normalize_noise_profile(
            {
                "source": "custom_preset",
                "preset": "readout_bias",
                "p01": 0.02,
                "p10": 0.07,
                "strength": 0.01,
            }
        )


@pytest.mark.parametrize(
    "profile",
    [
        {"source": "custom_preset", "preset": "thermal_relaxation"},
        {
            "source": "custom_preset",
            "preset": "thermal_relaxation",
            "t1_us": 100.0,
            "t2_us": 250.0,
            "gate_time_us": 0.1,
        },
    ],
)
def test_custom_thermal_profile_requires_physical_parameters(profile) -> None:
    with pytest.raises(NoiseConfigurationError):
        normalize_noise_profile(profile)


def test_custom_thermal_profile_records_explicit_microsecond_parameters() -> None:
    resolved = resolve_aer_noise_profile(
        {
            "source": "custom_preset",
            "preset": "thermal_relaxation",
            "t1_us": 100.0,
            "t2_us": 80.0,
            "gate_time_us": 0.1,
        }
    )

    assert resolved.summary["units"] == "microseconds"
    assert resolved.summary["t1_us"] == 100.0
    assert resolved.summary["t2_us"] == 80.0
    assert resolved.summary["gate_time_us"] == 0.1
    assert {"id", "sx", "x", "cx"}.issubset(set(resolved.summary["basis_gates"]))
