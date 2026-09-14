"""Shared mocks and SQL markers for execute_run tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

SAMPLE_RUN_ID = "00000000-0000-0000-0000-000000000001"
SELECT_MOLECULE_SQL = "SELECT m.atoms, m.charge, m.multiplicity, m.active_space, r.basis_set"
SELECT_STATUS_SQL = "SELECT status"
SELECT_STATUS_WITH_GENERATION_SQL = "SELECT status, execution_generation FROM runs"
SELECT_RUN_CONTEXT_WITH_PROFILE_SQL = (
    "SELECT config_json, metadata, latest_estimate, initial_estimate, credential_profile_id "
    "FROM runs"
)
SELECT_RUN_CONTEXT_SQL = "SELECT config_json, metadata, latest_estimate, initial_estimate FROM runs"
SELECT_CONFIG_AND_METADATA_SQL = "SELECT config_json, metadata FROM runs"
GET_DB_SESSION_PATCH_TARGET = "worker.jobs.execute_run.get_db_session"
DISPATCH_ALGORITHM_PATCH_TARGET = "worker.jobs.execute_run.dispatch_algorithm"
SELECT_BACKEND_PATCH_TARGET = "worker.jobs.execute_run.select_backend"
INJECT_PROFILE_CREDENTIALS_PATCH_TARGET = "worker.jobs.execute_run.inject_profile_credentials"
MOLECULE_ROW = (
    [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}],
    0,
    1,
    {"n_electrons": 2, "n_orbitals": 2},
    "sto-3g",
)


def _make_session(status: str = "RUNNING") -> MagicMock:
    """Return a mock session whose execute behaves correctly for all query types."""
    session = MagicMock()

    def execute_side_effect(query, params=None):
        sql = str(query)
        mock_result = MagicMock()
        if "COALESCE" in sql:
            # _next_sequence query: must return an integer at index 0
            mock_result.fetchone.return_value = (1,)
        elif SELECT_MOLECULE_SQL in sql:
            mock_result.fetchone.return_value = MOLECULE_ROW
        elif SELECT_STATUS_SQL in sql:
            # Cancellation check: return the status string at index 0
            mock_result.fetchone.return_value = (status, 1)
        elif SELECT_RUN_CONTEXT_WITH_PROFILE_SQL in sql:
            mock_result.fetchone.return_value = ({}, {}, None, None, None)
        elif SELECT_RUN_CONTEXT_SQL in sql:
            mock_result.fetchone.return_value = ({}, {}, None, None)
        elif SELECT_CONFIG_AND_METADATA_SQL in sql:
            mock_result.fetchone.return_value = ({}, {})
        else:
            # FOR UPDATE, UPDATE, INSERT: generic mock with integer at index 0
            mock_result.fetchone.return_value = (1,)
        return mock_result

    session.execute.side_effect = execute_side_effect
    return session


def _build_pause_after_ibm_job_execute_side_effect(
    *,
    status_rows: list[tuple[str, int]],
    status_generation_rows: list[tuple[str, int]],
    config_snapshot: dict[str, Any],
    metadata: dict[str, Any],
):
    def execute_side_effect(query, params=None):
        del params
        sql = str(query)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        if "COALESCE" in sql:
            mock_result.fetchone.return_value = (1,)
        elif "SELECT execution_generation FROM runs" in sql:
            mock_result.fetchone.return_value = (1,)
        elif SELECT_STATUS_WITH_GENERATION_SQL in sql:
            row = status_generation_rows.pop(0) if status_generation_rows else ("PAUSING", 1)
            mock_result.fetchone.return_value = row
        elif SELECT_RUN_CONTEXT_WITH_PROFILE_SQL in sql:
            mock_result.fetchone.return_value = (config_snapshot, metadata, None, None, None)
        elif SELECT_MOLECULE_SQL in sql:
            mock_result.fetchone.return_value = MOLECULE_ROW
        elif f"{SELECT_STATUS_SQL} FROM runs" in sql:
            row = status_rows.pop(0) if status_rows else ("PAUSING", 1)
            mock_result.fetchone.return_value = row
        elif SELECT_CONFIG_AND_METADATA_SQL in sql:
            mock_result.fetchone.return_value = (config_snapshot, metadata)
        else:
            mock_result.fetchone.return_value = (1,)
        return mock_result

    return execute_side_effect


def _collected_event_payloads(session_mock: MagicMock) -> list[dict]:
    """Parse INSERT run_events payloads from a session mock's execute calls."""
    payloads = []
    for c in session_mock.execute.call_args_list:
        if len(c.args) < 2:
            continue
        params = c.args[1]
        if isinstance(params, dict) and "payload" in params:
            try:
                payloads.append(json.loads(params["payload"]))
            except (json.JSONDecodeError, TypeError):
                pass
    return payloads


def _collected_event_types(session_mock: MagicMock) -> list[str]:
    """Parse INSERT run_events event types from a session mock's execute calls."""
    types = []
    for c in session_mock.execute.call_args_list:
        if len(c.args) < 2:
            continue
        params = c.args[1]
        if isinstance(params, dict) and "type" in params and "payload" in params:
            types.append(params["type"])
    return types


def _all_event_types(sessions: list[MagicMock]) -> list[str]:
    """Collect event types emitted across all mock sessions."""
    types: list[str] = []
    for s in sessions:
        types.extend(_collected_event_types(s))
    return types


def _all_event_payloads(sessions: list[MagicMock]) -> list[dict]:
    """Collect event payloads emitted across all mock sessions."""
    payloads: list[dict] = []
    for s in sessions:
        payloads.extend(_collected_event_payloads(s))
    return payloads


def _make_session_with_run_context(
    *,
    config_snapshot: dict,
    metadata: dict,
    status: str = "RUNNING",
    credential_profile_id: str | None = None,
) -> MagicMock:
    """Return a mock session that can serve run context plus status checks."""
    session = MagicMock()

    def execute_side_effect(query, params=None):
        sql = str(query)
        mock_result = MagicMock()
        if "COALESCE" in sql:
            mock_result.fetchone.return_value = (1,)
        elif SELECT_MOLECULE_SQL in sql:
            mock_result.fetchone.return_value = MOLECULE_ROW
        elif SELECT_RUN_CONTEXT_WITH_PROFILE_SQL in sql:
            mock_result.fetchone.return_value = (
                config_snapshot,
                metadata,
                None,
                None,
                credential_profile_id,
            )
        elif SELECT_RUN_CONTEXT_SQL in sql:
            mock_result.fetchone.return_value = (config_snapshot, metadata, None, None)
        elif SELECT_CONFIG_AND_METADATA_SQL in sql:
            mock_result.fetchone.return_value = (config_snapshot, metadata)
        elif SELECT_STATUS_SQL in sql:
            mock_result.fetchone.return_value = (status, 1)
        else:
            mock_result.fetchone.return_value = (1,)
        return mock_result

    session.execute.side_effect = execute_side_effect
    return session
