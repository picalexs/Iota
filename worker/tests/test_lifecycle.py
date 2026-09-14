"""Unit tests for repository-backed worker lifecycle helpers."""

from unittest.mock import MagicMock

import pytest

from worker.jobs.lifecycle import load_chemistry_input, parse_molecule_atoms

from .execute_run_test_helpers import MOLECULE_ROW


def test_parse_molecule_atoms_accepts_json_and_rejects_empty_payloads() -> None:
    assert parse_molecule_atoms('[{"symbol": "H"}]') == [{"symbol": "H"}]

    with pytest.raises(ValueError, match="non-empty list"):
        parse_molecule_atoms([])


def test_parse_molecule_atoms_reports_invalid_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_molecule_atoms("not-json")


def test_load_chemistry_input_maps_repository_row_to_worker_type() -> None:
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = MOLECULE_ROW

    chemistry_input = load_chemistry_input(
        session,
        run_id="run-1",
        config_snapshot={},
    )

    assert chemistry_input.atoms == MOLECULE_ROW[0]
    assert chemistry_input.charge == 0
    assert chemistry_input.multiplicity == 1
    assert chemistry_input.basis == "sto-3g"
    assert chemistry_input.active_space == (2, 2)
