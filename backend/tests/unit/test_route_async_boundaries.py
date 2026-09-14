"""Tests for endpoint-level sync and async ownership conventions."""

import inspect

from app.api.v1.endpoints import basis_sets, health, molecules


def test_metadata_and_health_routes_use_synchronous_handlers() -> None:
    synchronous_routes = (
        basis_sets.get_basis_sets,
        health.health_check,
        health.system_status,
    )

    assert all(not inspect.iscoroutinefunction(route) for route in synchronous_routes)


def test_sync_molecule_routes_use_synchronous_handlers() -> None:
    synchronous_routes = (
        molecules.preview_molecule_from_xyz,
        molecules.import_molecule_from_xyz,
        molecules.create_molecule,
        molecules.list_molecules,
        molecules.list_molecule_summaries,
        molecules.get_molecule,
        molecules.update_molecule,
        molecules.delete_molecule,
    )

    assert all(not inspect.iscoroutinefunction(route) for route in synchronous_routes)


def test_pubchem_routes_remain_async_for_external_http_calls() -> None:
    asynchronous_routes = (
        molecules.search_pubchem,
        molecules.preview_molecule_from_pubchem,
        molecules.import_molecule_from_pubchem,
    )

    assert all(inspect.iscoroutinefunction(route) for route in asynchronous_routes)
