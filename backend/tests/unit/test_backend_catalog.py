"""Unit tests for deterministic local backend catalog entries."""

from app.config import Settings
from app.models.enums import BackendTarget
from app.services.backend_catalog import local_backend_summaries


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
    )


def test_local_backend_summaries_expose_statevector_and_aer_contracts() -> None:
    summaries = local_backend_summaries(_settings())

    assert [summary.target for summary in summaries] == [
        BackendTarget.STATEVECTOR,
        BackendTarget.AER_SIMULATOR,
    ]
    assert [summary.name for summary in summaries] == ["statevector", "aer_simulator"]
    assert all(summary.available for summary in summaries)


def test_local_backend_summaries_keep_simulator_capabilities_distinct() -> None:
    statevector, aer = local_backend_summaries(_settings())

    assert statevector.supports_noise_profile is False
    assert statevector.supports_transpile_preview is False
    assert aer.supports_noise_profile is True
    assert aer.supports_transpile_preview is True
    assert aer.pending_jobs == 0
    assert aer.error_rate == 0.0
