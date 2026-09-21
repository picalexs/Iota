"""Tests for optional chemistry accelerator resolution."""

from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.accelerators import (
    normalize_chemistry_device,
    resolve_gpu4pyscf,
)


def test_normalize_chemistry_device_defaults_to_cpu() -> None:
    assert normalize_chemistry_device(None) == "CPU"
    assert normalize_chemistry_device("auto") == "AUTO"


def test_gpu4pyscf_auto_falls_back_when_provider_is_missing() -> None:
    resolution, provider = resolve_gpu4pyscf("AUTO")

    assert provider is None
    assert resolution.requested_device == "AUTO"
    assert resolution.actual_device == "CPU"
    assert resolution.provider == "pyscf"
    assert resolution.fallback_reason == "gpu4pyscf is not installed on this worker"


def test_gpu4pyscf_explicit_request_fails_closed_when_provider_is_missing() -> None:
    with pytest.raises(RuntimeError, match="GPU4PySCF is not installed"):
        resolve_gpu4pyscf("GPU")


def test_invalid_chemistry_device_is_rejected() -> None:
    with pytest.raises(ValueError, match="Chemistry device"):
        normalize_chemistry_device("TPU")


def test_selected_ci_auto_falls_back_when_sbd_has_no_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    sbd = types.ModuleType("sbd")
    sbd.available_backends = lambda: ["cpu"]
    device_config = types.ModuleType("sbd.device_config")
    device_config.DeviceConfig = object
    monkeypatch.setitem(sys.modules, "sbd", sbd)
    monkeypatch.setitem(sys.modules, "sbd.device_config", device_config)

    from worker.chemistry.algorithms.sqd.selected_ci_backend import resolve_selected_ci_solver

    def cpu_solver(*_args, **_kwargs):
        return 0.0, None, ([], []), 0.0

    resolution = resolve_selected_ci_solver(cpu_solver, "AUTO")

    assert resolution.actual_device == "CPU"
    assert resolution.provider == "qiskit_addon_sqd"
    assert resolution.fallback_reason == "SBD with a compiled GPU backend is not installed"


def test_selected_ci_gpu_request_fails_when_sbd_has_no_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    sbd = types.ModuleType("sbd")
    sbd.available_backends = lambda: ["cpu"]
    device_config = types.ModuleType("sbd.device_config")
    device_config.DeviceConfig = object
    monkeypatch.setitem(sys.modules, "sbd", sbd)
    monkeypatch.setitem(sys.modules, "sbd.device_config", device_config)

    from worker.chemistry.algorithms.sqd.selected_ci_backend import resolve_selected_ci_solver

    with pytest.raises(RuntimeError, match="GPU selected-CI was requested"):
        resolve_selected_ci_solver(lambda *_args, **_kwargs: (0.0, None, ([], []), 0.0), "GPU")


def test_selected_ci_sbd_adapter_preserves_sqd_solver_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    class FakeDeviceConfig:
        @staticmethod
        def gpu() -> str:
            return "gpu-config"

    class FakeState:
        amplitudes = None
        ci_strs_a = None
        ci_strs_b = None

        @staticmethod
        def spin_square() -> float:
            return 0.75

    class FakeResult:
        energy = -1.25
        sci_state = FakeState()
        orbital_occupancies = ([0.9, 0.1], [0.9, 0.1])

    calls: list[dict[str, object]] = []

    sbd = types.ModuleType("sbd")
    sbd.available_backends = lambda: ["cpu", "gpu"]
    device_config = types.ModuleType("sbd.device_config")
    device_config.DeviceConfig = FakeDeviceConfig
    solver_module = types.ModuleType("sbd.sbd_solver")

    def solve_sci_batch(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return [FakeResult()]

    solver_module.solve_sci_batch = solve_sci_batch
    monkeypatch.setitem(sys.modules, "sbd", sbd)
    monkeypatch.setitem(sys.modules, "sbd.device_config", device_config)
    monkeypatch.setitem(sys.modules, "sbd.sbd_solver", solver_module)

    from worker.chemistry.algorithms.sqd.selected_ci_backend import resolve_selected_ci_solver

    monkeypatch.setattr(
        "worker.chemistry.algorithms.sqd.selected_ci_backend._sbd_addon_compatibility_error",
        lambda: None,
    )
    resolution = resolve_selected_ci_solver(
        lambda *_args, **_kwargs: (0.0, None, ([], []), 0.0),
        "GPU",
    )
    result = resolution.solve_fermion(
        (np.asarray([1], dtype=np.int64), np.asarray([1], dtype=np.int64)),
        np.zeros((2, 2)),
        np.zeros((2, 2, 2, 2)),
        max_cycle=7,
    )

    assert result[:1] == (-1.25,)
    assert result[3] == 0.75
    assert calls[0]["kwargs"]["device_config"] == "gpu-config"
    assert calls[0]["kwargs"]["sbd_config"] == {
        "method": 0,
        "eps": 1e-8,
        "max_it": 7,
    }
