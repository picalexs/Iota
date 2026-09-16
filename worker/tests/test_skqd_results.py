from types import SimpleNamespace

import pytest

from worker.chemistry.algorithms.skqd.results import (
    add_skqd_solution_diagnostics,
    build_skqd_completion_payload,
    build_skqd_extension_diagnostics,
    build_sqd_core_summary,
    select_skqd_primary_solution,
)


def test_build_sqd_core_summary_preserves_nested_result_contract() -> None:
    result = SimpleNamespace(
        algorithm="sqd",
        primary_energy=-1.2,
        primary_iterations=3,
        converged=True,
        sci_result_package={"energy": -1.2},
        circuit_artifact_policy={"name": "all"},
    )

    assert build_sqd_core_summary(result) == {
        "algorithm": "sqd",
        "primary_energy": -1.2,
        "primary_iterations": 3,
        "converged": True,
        "sci_result_package": {"energy": -1.2},
        "circuit_artifact_policy": {"name": "all"},
    }


@pytest.mark.parametrize(
    ("sqd_energy", "extension_energy", "extension_converged", "expected"),
    [
        (-1.0, -1.2, True, (-1.2, "krylov_extension")),
        (-1.0, -1.2, False, (-1.0, "sqd_core")),
        (None, -1.2, False, (-1.2, "krylov_extension")),
        (None, None, False, (None, "none")),
    ],
)
def test_select_skqd_primary_solution_applies_convergence_guard(
    sqd_energy: float | None,
    extension_energy: float | None,
    extension_converged: bool,
    expected: tuple[float | None, str],
) -> None:
    assert (
        select_skqd_primary_solution(
            sqd_core_energy=sqd_energy,
            extension_energy=extension_energy,
            extension_converged=extension_converged,
        )
        == expected
    )


def test_build_skqd_extension_diagnostics_records_sector_and_ritz_metadata() -> None:
    plan = SimpleNamespace(
        operator_dimension=6,
        execution_mode="sector_matrix_free",
        operator=None,
        sector_action=SimpleNamespace(
            dimension=6,
            norb=2,
            nelec=(1, 1),
        ),
    )
    extension = SimpleNamespace(
        sqd_seed=None,
        seed_source="hf_sector_reference",
        basis_rank=3,
        residual_diagnostics={"relative_ritz_residual": 1e-7},
    )
    result = SimpleNamespace(primary_iterations=2, converged=True)

    diagnostics = build_skqd_extension_diagnostics(
        plan=plan,
        extension=extension,
        sqd_result=result,
        ritz_values=[-1.2, -0.4],
        krylov_extension_dim=4,
        sampling_time_step=0.2,
    )

    assert diagnostics["execution_mode"] == "sector_matrix_free"
    assert diagnostics["algorithm_variant"] == "local_statevector_krylov_extension"
    assert diagnostics["reference_policy"] == "hartree_fock_fallback"
    assert diagnostics["sector_dimension"] == 6.0
    assert diagnostics["min_ritz"] == -1.2
    assert diagnostics["max_ritz"] == -0.4


def test_build_skqd_extension_diagnostics_labels_selected_ci_seed_correctly() -> None:
    extension = SimpleNamespace(
        sqd_seed=object(),
        seed_source="sqd_best_selected_ci_coefficients",
        basis_rank=1,
        residual_diagnostics={},
    )

    diagnostics = build_skqd_extension_diagnostics(
        plan=SimpleNamespace(operator_dimension=2, execution_mode="dense_matrix", sector_action=None),
        extension=extension,
        sqd_result=SimpleNamespace(primary_iterations=1, converged=False),
        ritz_values=[],
        krylov_extension_dim=2,
        sampling_time_step=0.2,
    )

    assert diagnostics["seeded_from_sqd"] is True
    assert diagnostics["seeded_from_sqd_occupancies"] is False
    assert diagnostics["seed_source"] == "sqd_best_selected_ci_coefficients"


def test_build_skqd_extension_diagnostics_records_seed_iteration() -> None:
    extension = SimpleNamespace(
        sqd_seed=object(),
        seed_source="sqd_best_selected_ci_coefficients",
        basis_rank=1,
        residual_diagnostics={},
    )
    sqd_result = SimpleNamespace(
        primary_iterations=3,
        converged=True,
        sci_result_package={"best_iteration": 2, "iterations": 3},
    )

    diagnostics = build_skqd_extension_diagnostics(
        plan=SimpleNamespace(operator_dimension=2, execution_mode="dense_matrix", sector_action=None),
        extension=extension,
        sqd_result=sqd_result,
        ritz_values=[],
        krylov_extension_dim=2,
        sampling_time_step=0.2,
    )

    assert diagnostics["seed_source"] == "sqd_best_selected_ci_coefficients"
    assert diagnostics["sqd_seed_iteration"] == 2.0


def test_build_skqd_extension_diagnostics_records_seed_fallback_reason() -> None:
    extension = SimpleNamespace(
        sqd_seed=None,
        seed_source="hf_sector_reference",
        seed_fallback_reason="missing_sqd_selected_ci_state",
        basis_rank=1,
        residual_diagnostics={},
    )
    sqd_result = SimpleNamespace(
        primary_iterations=1,
        converged=True,
        sci_result_package={},
    )

    diagnostics = build_skqd_extension_diagnostics(
        plan=SimpleNamespace(
            operator_dimension=2, execution_mode="sector_operator", sector_action=None
        ),
        extension=extension,
        sqd_result=sqd_result,
        ritz_values=[],
        krylov_extension_dim=2,
        sampling_time_step=0.2,
    )

    assert diagnostics["seed_source"] == "hf_sector_reference"
    assert diagnostics["seed_fallback_reason"] == "missing_sqd_selected_ci_state"
    assert diagnostics["algorithm_variant"] == "local_statevector_krylov_extension"
    assert diagnostics["reference_policy"] == "hartree_fock_fallback"


def test_solution_diagnostics_and_completion_payload_share_selection_metadata() -> None:
    diagnostics: dict[str, object] = {}
    add_skqd_solution_diagnostics(
        diagnostics,
        sqd_core_energy=-1.0,
        extension_energy=-1.1,
        selected_solution="krylov_extension",
        selected_solution_converged=True,
    )
    payload = build_skqd_completion_payload(
        extension=SimpleNamespace(
            basis_rank=3,
            sqd_seed=None,
            seed_source="hf_reference",
            residual_diagnostics={"relative_ritz_residual": 1e-8},
        ),
        sqd_result=SimpleNamespace(primary_iterations=2, converged=True),
        skqd_config=SimpleNamespace(
            krylov_extension_dim=4,
            sampling_time_step=0.2,
            residual_tolerance=1e-6,
        ),
        primary_energy=-1.1,
        primary_iterations=5,
        selected_solution="krylov_extension",
        selected_solution_converged=True,
        krylov_converged=True,
        overall_converged=True,
        ritz_values=[-1.1, -0.5],
        execution_mode="dense_matrix",
        sampling_time_step=0.2,
    )

    assert diagnostics["extension_improved_sqd"] is True
    assert payload.selected_solution == diagnostics["selected_solution"]
    assert payload.relative_residual == pytest.approx(1e-8)
