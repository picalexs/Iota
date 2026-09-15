"""Compatibility checks for the extracted VQE configuration boundary."""

from __future__ import annotations

from worker.chemistry.algorithms.vqe import workflow as vqe_solver
from worker.chemistry.algorithms.vqe.config import (
    VQEConfig,
    bounded_optional_positive_int,
    positive_float_or_default,
    resolve_parameter_bounds,
    resolve_vqe_config,
    select_vqe_optimizer_name,
)


def test_vqe_solver_keeps_legacy_configuration_aliases() -> None:
    assert vqe_solver._VQEConfig is VQEConfig
    assert vqe_solver._bounded_optional_positive_int is bounded_optional_positive_int
    assert vqe_solver._positive_float_or_default is positive_float_or_default
    assert vqe_solver._resolve_parameter_bounds is resolve_parameter_bounds
    assert vqe_solver._resolve_vqe_config is resolve_vqe_config
    assert vqe_solver._select_vqe_optimizer_name is select_vqe_optimizer_name
