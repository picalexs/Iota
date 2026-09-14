"""Regression tests for the current local-only QSE contract."""

from __future__ import annotations

from uuid import uuid4

from app.models.enums import BackendTarget, RunAlgorithm, RunMode
from app.schemas.run import CustomNoisePreset, NoiseModelSource, RunCreate
from app.services.validation_service import validate_run_request


def _qse_run(
    *,
    excitation_level: str = "singles",
    backend_target: BackendTarget = BackendTarget.STATEVECTOR,
    noise_profile: dict[str, object] | None = None,
) -> RunCreate:
    return RunCreate.model_validate(
        {
            "molecule_id": uuid4(),
            "algorithm": RunAlgorithm.QSE,
            "mode": RunMode.ADVANCED,
            "backend_target": backend_target,
            "noise_profile": noise_profile,
            "advanced_config": {
                "algorithm": RunAlgorithm.QSE,
                "reference_method": "hf",
                "excitation_level": excitation_level,
                "max_subspace_dim": 4,
            },
        }
    )


def test_h2_hf_singles_preflight_reports_local_scope_and_accuracy_limit() -> None:
    result = validate_run_request(
        _qse_run(),
        molecule_active_space_n_electrons=2,
        molecule_active_space_n_orbitals=2,
    )

    assert result.valid
    assert any("local exact or sector emulation" in warning for warning in result.warnings)
    assert any("not accuracy-capable for the H2 benchmark" in warning for warning in result.warnings)


def test_h2_hf_singles_doubles_removes_configuration_limit_warning() -> None:
    result = validate_run_request(
        _qse_run(excitation_level="singles_doubles"),
        molecule_active_space_n_electrons=2,
        molecule_active_space_n_orbitals=2,
    )

    assert result.valid
    assert any("local exact or sector emulation" in warning for warning in result.warnings)
    assert not any("not accuracy-capable for the H2 benchmark" in warning for warning in result.warnings)


def test_noisy_qse_now_validates_via_measured_path() -> None:
    result = validate_run_request(
        _qse_run(
            backend_target=BackendTarget.AER_SIMULATOR,
            noise_profile={
                "source": NoiseModelSource.CUSTOM_PRESET,
                "preset": CustomNoisePreset.DEPOLARIZING_CX,
                "strength": 0.01,
            },
        ),
        molecule_active_space_n_electrons=2,
        molecule_active_space_n_orbitals=2,
    )

    assert result.valid
    assert not any(
        "Noisy QSE measured matrix elements are not implemented" in error.message
        for error in result.errors
    )
    assert any("measured QSE" in warning for warning in result.warnings)
