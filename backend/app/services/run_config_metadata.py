"""Registry-backed metadata for run configuration controls."""

from __future__ import annotations

from app.schemas.run_metadata import RunConfigMetadataResponse
from shared.contracts.catalog import get_public_catalog


def get_run_config_metadata() -> RunConfigMetadataResponse:
    """Return the shared selector catalog without importing worker code."""
    return RunConfigMetadataResponse.model_validate(get_public_catalog())
