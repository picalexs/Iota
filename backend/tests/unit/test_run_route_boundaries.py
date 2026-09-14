"""Tests for synchronous and asynchronous run-route ownership."""

import inspect

from app.api.v1.endpoints import runs
from app.schemas.run_responses import ExportBundle


def test_sync_run_routes_do_not_wrap_synchronous_services_as_async_handlers() -> None:
    synchronous_routes = (
        runs.list_runs,
        runs.list_run_summaries,
        runs.get_config_metadata,
        runs.get_run,
        runs.delete_run,
        runs.cancel_run,
        runs.pause_run,
        runs.resume_run,
        runs.restart_run,
        runs.create_run_checkpoint,
        runs.list_run_checkpoints,
        runs.get_run_result,
        runs.get_run_events,
        runs.export_run,
    )

    assert all(not inspect.iscoroutinefunction(route) for route in synchronous_routes)


def test_routes_that_need_async_work_remain_async() -> None:
    assert inspect.iscoroutinefunction(runs.create_run)
    assert inspect.iscoroutinefunction(runs.stream_run_events)


def test_export_route_declares_the_reproducibility_bundle_contract() -> None:
    export_route = next(route for route in runs.router.routes if route.path == "/{run_id}/export")

    assert export_route.response_model is ExportBundle
