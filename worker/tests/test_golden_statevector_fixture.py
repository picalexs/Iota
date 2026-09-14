"""Tests for golden statevector fixture contract."""

from __future__ import annotations

import json
from pathlib import Path


def test_golden_statevector_fixture_contains_h2_and_lih() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "golden_statevector.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert payload["catalog_version"] == "v1-statevector"
    assert payload["solver"]["algorithm"] == "vqe"
    assert payload["solver"]["backend_target"] == "statevector"

    molecules = payload["molecules"]
    assert "H2" in molecules
    assert "LiH" in molecules

    for key in ("H2", "LiH"):
        expected = molecules[key]["expected"]
        assert isinstance(expected["primary_energy"], float)
        assert isinstance(expected["primary_iterations"], int)
        assert expected["primary_iterations"] >= 1
