"""Tests for bounded CPU thread controls."""

from __future__ import annotations

import os

import pytest

from worker.chemistry.thread_controls import configure_thread_limits


def test_configure_thread_limits_applies_worker_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        monkeypatch.delenv(name, raising=False)

    result = configure_thread_limits({}, default_limit=4)

    assert result["cpu_thread_limit"] == 4
    assert result["source"] == "worker_default"
    for name in result["environment_variables"]:
        assert os.environ[name] == "4"


def test_configure_thread_limits_uses_requested_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    result = configure_thread_limits(
        {
            "max_parallel_threads": 3,
            "max_parallel_experiments": 2,
            "max_parallel_shots": 1,
        },
        default_limit=8,
    )

    assert result["cpu_thread_limit"] == 3
    assert result["source"] == "backend_options"
    assert result["aer_thread_options"] == {
        "max_parallel_threads": 3,
        "max_parallel_experiments": 2,
        "max_parallel_shots": 1,
    }


def test_configure_thread_limits_reads_worker_default_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QSS_CPU_THREAD_LIMIT", "5")

    result = configure_thread_limits({}, default_limit=8)

    assert result["cpu_thread_limit"] == 5


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "4"])
def test_configure_thread_limits_rejects_invalid_requested_limit(value: object) -> None:
    with pytest.raises(ValueError, match="max_parallel_threads"):
        configure_thread_limits({"max_parallel_threads": value})
