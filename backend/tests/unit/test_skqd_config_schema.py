"""Schema tests for explicit SKQD execution modes."""

from app.models.enums import RunAlgorithm
from app.schemas.run_config import SKQDAdvancedConfig, SKQDSamplingParams


def _config(**overrides: object) -> SKQDAdvancedConfig:
    values: dict[str, object] = {
        "algorithm": RunAlgorithm.SKQD,
        "samples_per_state": 64,
        "base_sampling_options": SKQDSamplingParams(),
        "krylov_extension_dim": 2,
    }
    values.update(overrides)
    return SKQDAdvancedConfig(**values)


def test_skqd_schema_defaults_to_sample_union_mode() -> None:
    assert _config().sampling_mode == "sample_union_exact"


def test_skqd_schema_accepts_explicit_legacy_mode() -> None:
    assert _config(sampling_mode="legacy_statevector_extension").sampling_mode == (
        "legacy_statevector_extension"
    )
