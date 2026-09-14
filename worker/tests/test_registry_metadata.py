"""Tests for worker registry metadata ownership."""

from shared.contracts.identifiers import BackendTarget
from shared.contracts.registry_metadata import (
    supported_ansatz_metadata as shared_ansatz_metadata,
)
from shared.contracts.registry_metadata import (
    supported_optimizer_metadata as shared_optimizer_metadata,
)
from worker.chemistry.ansatz_registry import (
    _supported_ansatz_aliases,
    supported_ansatz_metadata,
)
from worker.chemistry.backend_selector import (
    _BACKEND_REGISTRY,
    get_backend_capabilities,
    select_backend,
)
from worker.chemistry.optimizer_registry import (
    _supported_optimizer_aliases,
    supported_optimizer_metadata,
)


def test_worker_ansatz_metadata_matches_shared_contract():
    assert supported_ansatz_metadata() == shared_ansatz_metadata()


def test_worker_optimizer_metadata_matches_shared_contract():
    assert supported_optimizer_metadata() == shared_optimizer_metadata()


def test_worker_backend_registry_matches_shared_contract():
    expected_backends = {backend.value for backend in BackendTarget}

    assert set(_BACKEND_REGISTRY) == expected_backends
    assert {
        get_backend_capabilities(backend.value).backend_target for backend in BackendTarget
    } == expected_backends
    assert all(select_backend(backend.value).capabilities.enabled for backend in BackendTarget)


def test_worker_alias_maps_derive_from_shared_registry_metadata():
    ansatz_metadata = shared_ansatz_metadata()
    optimizer_metadata = shared_optimizer_metadata()

    expected_ansatz_aliases = {
        alias.strip().lower(): canonical_id
        for canonical_id, metadata in ansatz_metadata.items()
        for alias in {canonical_id, *metadata["aliases"]}
    }
    expected_optimizer_aliases = {
        alias.strip().upper(): canonical_id
        for canonical_id, metadata in optimizer_metadata.items()
        for alias in {canonical_id, *metadata["aliases"]}
    }

    assert _supported_ansatz_aliases() == expected_ansatz_aliases
    assert _supported_optimizer_aliases() == expected_optimizer_aliases
