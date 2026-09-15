"""Tests for the SQD configuration and Hamiltonian-input boundary."""

from types import SimpleNamespace

import numpy as np
import pytest

from worker.chemistry.algorithms.sqd import config as sqd_config
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def _hamiltonian(*, norb: int = 2, num_elec_a: int = 1, num_elec_b: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        one_body_tensor=np.zeros((norb, norb), dtype=float),
        two_body_tensor=np.zeros((norb, norb, norb, norb), dtype=float),
        constant=-0.25,
        num_spatial_orbitals=norb,
        num_electrons_alpha=num_elec_a,
        num_electrons_beta=num_elec_b,
    )


def test_solver_keeps_configuration_names_as_compatibility_aliases() -> None:
    assert sqd_solver._SQDOptions is sqd_config.SQDOptions
    assert sqd_solver._resolve_sqd_options is sqd_config.resolve_sqd_options
    assert sqd_solver._resolve_sqd_hamiltonian_inputs is sqd_config.resolve_sqd_hamiltonian_inputs


def test_resolve_sqd_options_applies_runtime_bounds_and_hamiltonian_defaults() -> None:
    options = sqd_config.resolve_sqd_options(
        {
            "algorithm": "sqd",
            "max_iterations": 9_999,
            "samples_per_batch": 9_999,
            "num_batches": 0,
            "seed": 0,
            "sci_solver_options": {"max_cycle": 80},
        },
        _hamiltonian(),
    )

    assert options.max_iterations == 5_000
    assert options.samples_per_batch == 2_000
    assert options.num_batches == 1
    assert options.total_samples == 2_000
    assert options.num_elec_a == 1
    assert options.num_elec_b == 1
    assert options.hamiltonian_constant == -0.25
    assert options.seed == 0
    assert options.sci_solver_options == {"max_cycle": 80}


def test_resolve_sqd_options_maps_backend_sample_budget_when_unspecified() -> None:
    options = sqd_config.resolve_sqd_options(
        {"algorithm": "sqd"},
        _hamiltonian(),
        sample_budget=256,
    )

    assert options.samples_per_batch == 256
    assert options.num_batches == 1
    assert options.total_samples == 256


def test_resolve_sqd_options_keeps_explicit_sample_budget() -> None:
    options = sqd_config.resolve_sqd_options(
        {"algorithm": "sqd", "samples_per_batch": 64},
        _hamiltonian(),
        sample_budget=256,
    )

    assert options.samples_per_batch == 64
    assert options.num_batches == 8
    assert options.total_samples == 512


def test_resolve_sqd_hamiltonian_inputs_rejects_incompatible_tensor_shapes() -> None:
    hamiltonian = _hamiltonian()
    hamiltonian.one_body_tensor = np.zeros((3, 3), dtype=float)

    with pytest.raises(ValueError, match="one_body_tensor shape"):
        sqd_config.resolve_sqd_hamiltonian_inputs(hamiltonian)


def test_resolve_sqd_options_rejects_asymmetric_symmetrized_limits() -> None:
    with pytest.raises(ValueError, match="identical alpha and beta max_dim"):
        sqd_config.resolve_sqd_options(
            {
                "algorithm": "sqd",
                "symmetrize_spin": True,
                "max_dim": [2, 3],
            },
            _hamiltonian(),
        )
