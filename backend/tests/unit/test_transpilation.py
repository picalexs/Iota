"""Unit tests for deterministic transpile-preview orchestration."""

from app.config import Settings
from app.models.enums import BackendTarget
from app.schemas.backend import TranspilePreviewRequest
from app.schemas.run_config import BackendOptions
from app.services.transpilation import transpile_preview


def test_transpile_preview_uses_local_resolution_and_metadata() -> None:
    response = transpile_preview(
        TranspilePreviewRequest(
            target=BackendTarget.STATEVECTOR,
            backend_options=BackendOptions(),
            num_qubits=2,
            circuit_depth=4,
        ),
        settings=Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost:6379/0",
        ),
    )

    assert response.feasible is True
    assert response.backend_name == "statevector"
    assert response.metadata["input_depth"] == 4
