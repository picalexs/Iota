"""Tests for the SQD result-normalization boundary."""

from worker.chemistry import sqd_solver
from worker.chemistry.algorithms.sqd import results as sqd_result


def test_solver_keeps_result_helpers_as_compatibility_aliases() -> None:
    assert sqd_solver._serialize_circuit_preview is sqd_result.serialize_sqd_circuit_preview
    assert sqd_solver._build_sqd_circuit_artifacts is sqd_result.build_sqd_circuit_artifacts
    assert sqd_solver._build_sqd_result is sqd_result.build_sqd_result


def test_selected_ci_regime_distinguishes_full_and_partial_sector() -> None:
    assert sqd_result._selected_ci_regime(
        {"full_sci_dimension": 36, "selected_ci_dimension": 36}
    ) == {
        "selected_ci_regime": "full_sector",
        "full_sector_dimension": 36,
        "selected_determinant_count": 36,
        "selected_fraction": 1.0,
        "classical_diagonalization_dimension": 36,
        "selected_space_equals_full_sector": True,
    }
    assert sqd_result._selected_ci_regime(
        {"full_sci_dimension": 36, "selected_ci_dimension": 4}
    )["selected_ci_regime"] == "partial_sector"
